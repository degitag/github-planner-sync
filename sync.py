#!/usr/bin/env python3
import os
import sqlite3
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

sqlite3.register_adapter(datetime, lambda d: d.isoformat())
sqlite3.register_converter("TIMESTAMP", lambda d: datetime.fromisoformat(d.decode()))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GRAPH_TOKEN = os.getenv("GRAPH_TOKEN")
PLAN_ID = os.getenv("PLAN_ID")
BUCKET_ID = os.getenv("BUCKET_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_MINUTES", "15")) * 60

DB_FILE = "sync_mappings.db"

GITHUB_API = "https://api.github.com"


def normalize_value(value):
    return value if value else ""


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
        "Authorization": f"Bearer {GRAPH_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.get(
        f"{GRAPH_API}/planner/buckets/{BUCKET_ID}/tasks", headers=headers
    )
    if response.status_code == 200:
        tasks = response.json().get("value", [])
        return [t for t in tasks if not t.get("percentComplete", 0) == 100]
    print(f"Graph API error: {response.status_code}")
    return []


def get_planner_task(task_id):
    headers = {
        "Authorization": f"Bearer {GRAPH_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.get(f"{GRAPH_API}/planner/tasks/{task_id}", headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def create_planner_task(title, description=None):
    headers = {
        "Authorization": f"Bearer {GRAPH_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {"planId": PLAN_ID, "bucketId": BUCKET_ID, "title": title}
    if description:
        data["description"] = description
    response = requests.post(f"{GRAPH_API}/planner/tasks", headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    print(f"Failed to create Planner task: {response.status_code}")
    return None


def update_planner_task(task_id, title=None, description=None):
    headers = {
        "Authorization": f"Bearer {GRAPH_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {}
    if title:
        data["title"] = title
    if description:
        data["description"] = description
    response = requests.patch(
        f"{GRAPH_API}/planner/tasks/{task_id}", headers=headers, json=data
    )
    return response.status_code == 200


def sync_github_to_planner():
    issues = get_github_issues()
    print(f"Found {len(issues)} open GitHub issues")

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

        if not planner_id:
            task = create_planner_task(issue["title"], description)
            if task:
                save_mapping(github_id, task["id"])
                print(
                    f"Created Planner task {task['id']} for GitHub issue #{issue['number']}"
                )
        else:
            task = get_planner_task(planner_id)
            if task:
                if normalize_value(task.get("title")) != normalize_value(
                    issue["title"]
                ) or normalize_value(task.get("description")) != normalize_value(
                    description
                ):
                    update_planner_task(planner_id, issue["title"], description)
                    update_sync_time(github_id=github_id, source="github")
                    print(
                        f"Updated Planner task {planner_id} for GitHub issue #{issue['number']}"
                    )


def sync_planner_to_github():
    tasks = get_planner_tasks()
    print(f"Found {len(tasks)} active Planner tasks")

    for task in tasks:
        planner_id = task["id"]
        github_id = get_mapping(planner_id=planner_id)

        if not github_id:
            issue = create_github_issue(task["title"], task.get("description"))
            if issue:
                save_mapping(str(issue["id"]), planner_id)
                print(
                    f"Created GitHub issue #{issue['number']} for Planner task {planner_id}"
                )
        else:
            issue = get_github_issue(int(github_id))
            if issue:
                if normalize_value(issue["title"]) != normalize_value(
                    task["title"]
                ) or normalize_value(issue.get("body")) != normalize_value(
                    task.get("description")
                ):
                    update_github_issue(
                        issue["number"], task["title"], task.get("description")
                    )
                update_sync_time(planner_id=planner_id, source="planner")
                print(
                    f"Updated GitHub issue #{issue['number']} for Planner task {planner_id}"
                )


def main():
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

        print(f"Next sync in {POLL_INTERVAL} seconds...\n")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
