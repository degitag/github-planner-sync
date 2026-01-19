#!/usr/bin/env python3
import os
import sqlite3
import time
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv
import requests
import msal

load_dotenv()

sqlite3.register_adapter(datetime, lambda d: d.isoformat())
sqlite3.register_converter("TIMESTAMP", lambda d: datetime.fromisoformat(d.decode()))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
PLAN_ID = os.getenv("PLAN_ID")
BUCKET_ID = os.getenv("BUCKET_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_MINUTES", "15")) * 60

DB_FILE = "sync_mappings.db"

GITHUB_API = "https://api.github.com"


def get_graph_token():
    config = {
        "authority": f"https://login.microsoftonline.com/{os.getenv('GRAPH_TENANT_ID')}",
        "client_id": os.getenv("GRAPH_CLIENT_ID"),
        "client_secret": os.getenv("GRAPH_CLIENT_SECRET"),
        "scope": ["https://graph.microsoft.com/.default"],
    }
    app = msal.ConfidentialClientApplication(
        config["client_id"],
        authority=config["authority"],
        client_credential=config["client_secret"],
    )
    result = app.acquire_token_for_client(scopes=config["scope"])
    if "access_token" in result:
        return result["access_token"]
    print(f"Token error: {result.get('error_description')}")
    return None


def normalize_value(value):
    return value if value else ""


def get_percent_complete_from_labels(labels):
    label_map = {
        "backlog": 0,
        "ideas": 0,
        "todo": 20,
        "ready": 30,
        "in progress": 50,
        "in review": 75,
        "done": 100,
    }
    label_names = [label.get("name", "").lower() for label in labels]
    for label_name, percent in label_map.items():
        if label_name in label_names:
            return percent
    return 0


GRAPH_API = "https://graph.microsoft.com/v1.0"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS mappings
                 (github_issue_id TEXT PRIMARY KEY, planner_task_id TEXT,
                  last_synced_github TIMESTAMP, last_synced_planner TIMESTAMP)""")
    conn.commit()
    conn.close()


def get_mapping(github_id=None, planner_id=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if github_id:
        c.execute(
            "SELECT planner_task_id FROM mappings WHERE github_issue_id = ?",
            (github_id,),
        )
    elif planner_id:
        c.execute(
            "SELECT github_issue_id FROM mappings WHERE planner_task_id = ?",
            (planner_id,),
        )
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def save_mapping(github_id, planner_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """INSERT OR REPLACE INTO mappings
                 (github_issue_id, planner_task_id, last_synced_github, last_synced_planner)
                 VALUES (?, ?, ?, ?)""",
        (github_id, planner_id, datetime.now(), datetime.now()),
    )
    conn.commit()
    conn.close()


def update_sync_time(github_id=None, planner_id=None, source=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if source == "github":
        c.execute(
            "UPDATE mappings SET last_synced_github = ? WHERE github_issue_id = ?",
            (datetime.now(), github_id),
        )
    elif source == "planner":
        c.execute(
            "UPDATE mappings SET last_synced_planner = ? WHERE planner_task_id = ?",
            (datetime.now(), planner_id),
        )
    conn.commit()
    conn.close()


def get_github_issues():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/issues?state=open", headers=headers
    )
    if response.status_code == 200:
        return response.json()
    print(f"GitHub API error: {response.status_code}")
    return []


def get_github_issue(issue_number):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/issues/{issue_number}", headers=headers
    )
    if response.status_code == 200:
        return response.json()
    return None


def get_all_github_issues():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/issues?state=all", headers=headers
    )
    if response.status_code == 200:
        return response.json()
    print(f"GitHub API error: {response.status_code}")
    return []


def create_github_issue(title, body, labels=None):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {"title": title, "body": body}
    if labels:
        data["labels"] = labels
    response = requests.post(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/issues", headers=headers, json=data
    )
    if response.status_code == 201:
        return response.json()
    print(f"Failed to create GitHub issue: {response.status_code}")
    return None


def update_github_issue(issue_number, title=None, body=None, state=None):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {}
    if title:
        data["title"] = title
    if body:
        data["body"] = body
    if state:
        data["state"] = state
    response = requests.patch(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/issues/{issue_number}",
        headers=headers,
        json=data,
    )
    return response.status_code == 200


def get_planner_tasks():
    headers = {
        "Authorization": f"Bearer {get_graph_token()}",
        "Content-Type": "application/json",
    }
    response = requests.get(
        f"{GRAPH_API}/planner/buckets/{BUCKET_ID}/tasks", headers=headers
    )
    if response.status_code == 200:
        return response.json().get("value", [])
    print(f"Graph API error: {response.status_code}")
    return []


def get_planner_task(task_id):
    headers = {
        "Authorization": f"Bearer {get_graph_token()}",
        "Content-Type": "application/json",
    }
    response = requests.get(f"{GRAPH_API}/planner/tasks/{task_id}", headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def create_planner_task(title):
    headers = {
        "Authorization": f"Bearer {get_graph_token()}",
        "Content-Type": "application/json",
    }
    data = {"planId": PLAN_ID, "bucketId": BUCKET_ID, "title": title}
    response = requests.post(f"{GRAPH_API}/planner/tasks", headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    print(f"Failed to create Planner task: {response.status_code}")
    return None


def update_planner_task(task_id, title=None, percent_complete=None):
    headers = {
        "Authorization": f"Bearer {get_graph_token()}",
        "Content-Type": "application/json",
    }

    data = {}
    if title:
        data["title"] = title
    if percent_complete is not None:
        data["percentComplete"] = percent_complete

    if not data:
        return False

    get_response = requests.get(f"{GRAPH_API}/planner/tasks/{task_id}", headers=headers)
    if get_response.status_code == 200:
        etag = get_response.json().get("@odata.etag")
        if etag:
            headers["If-Match"] = etag

    response = requests.patch(
        f"{GRAPH_API}/planner/tasks/{task_id}", headers=headers, json=data
    )
    return response.status_code in [200, 204]


def update_planner_task_details(task_id, description=None):
    headers = {
        "Authorization": f"Bearer {get_graph_token()}",
        "Content-Type": "application/json",
    }

    data = {}
    if description:
        data["description"] = description

    get_response = requests.get(
        f"{GRAPH_API}/planner/tasks/{task_id}/details", headers=headers
    )
    if get_response.status_code == 200:
        etag = get_response.json().get("@odata.etag")
        if etag:
            headers["If-Match"] = etag

    response = requests.patch(
        f"{GRAPH_API}/planner/tasks/{task_id}/details", headers=headers, json=data
    )
    return response.status_code in [200, 204]


def sync_github_to_planner():
    issues = get_all_github_issues()
    print(f"Found {len(issues)} total GitHub issues")

    for issue in issues:
        github_id = str(issue["id"])
        planner_id = get_mapping(github_id=github_id)

        issue_url = issue["html_url"]
        body = issue.get("body", "")
        description = (
            f"{body}\n\n---\n**GitHub URL:** {issue_url}"
            if body
            else f"**GitHub URL:** {issue_url}"
        )

        issue_state = issue.get("state", "open")
        if issue_state == "closed":
            percent_complete = 100
        else:
            percent_complete = get_percent_complete_from_labels(issue.get("labels", []))

        if not planner_id:
            if issue_state == "open":
                task = create_planner_task(issue["title"])
                if task:
                    update_planner_task(task["id"], percent_complete=percent_complete)
                    update_planner_task_details(task["id"], description)
                    save_mapping(github_id, task["id"])
                    print(
                        f"Created Planner task {task['id']} for GitHub issue #{issue['number']} ({percent_complete}%)"
                    )
        else:
            task = get_planner_task(planner_id)
            if task:
                title_changed = normalize_value(task.get("title")) != normalize_value(
                    issue["title"]
                )
                percent_changed = task.get("percentComplete", 0) != percent_complete
                description_changed = True

                if title_changed or percent_changed or description_changed:
                    update_planner_task(planner_id, issue["title"], percent_complete)
                    update_planner_task_details(planner_id, description)
                    update_sync_time(github_id=github_id, source="github")
                    print(
                        f"Updated Planner task {planner_id} for GitHub issue #{issue['number']} ({percent_complete}%)"
                    )


def sync_planner_to_github():
    tasks = get_planner_tasks()
    print(f"Found {len(tasks)} total Planner tasks")

    for task in tasks:
        planner_id = task["id"]
        github_id = get_mapping(planner_id=planner_id)

        task_complete = task.get("percentComplete", 0) == 100

        if not github_id:
            if not task_complete:
                issue = create_github_issue(task["title"], task.get("description"))
                if issue:
                    save_mapping(str(issue["id"]), planner_id)
                    print(
                        f"Created GitHub issue #{issue['number']} for Planner task {planner_id}"
                    )
        else:
            issue = get_github_issue(int(github_id))
            if issue:
                issue_state = issue.get("state", "open")
                new_state = "closed" if task_complete else "open"
                title_changed = normalize_value(issue["title"]) != normalize_value(
                    task["title"]
                )
                description_changed = normalize_value(
                    issue.get("body")
                ) != normalize_value(task.get("description"))
                state_changed = new_state != issue_state

                if title_changed or description_changed or state_changed:
                    update_github_issue(
                        issue["number"],
                        task["title"],
                        task.get("description"),
                        new_state,
                    )
                update_sync_time(planner_id=planner_id, source="planner")
                print(
                    f"Updated GitHub issue #{issue['number']} for Planner task {planner_id} (state: {new_state})"
                )


def main():
    parser = argparse.ArgumentParser(
        description="Sync GitHub Issues with Microsoft Planner tasks"
    )
    parser.add_argument("--oneshot", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    init_db()
    print("Starting sync service...")
    print(f"Polling interval: {POLL_INTERVAL} seconds")

    while True:
        print(f"\nSync cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            sync_github_to_planner()
            sync_planner_to_github()
            print("Sync cycle completed")
        except Exception as e:
            print(f"Error during sync: {e}")

        if args.oneshot:
            print("\nOneshot mode - exiting after one sync cycle")
            break

        print(f"Next sync in {POLL_INTERVAL} seconds...\n")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
