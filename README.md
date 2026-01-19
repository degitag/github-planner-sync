# GitHub ↔ Microsoft Planner Sync

Bidirectional synchronization between GitHub Issues and Microsoft Planner tasks.

## Setup

1. **Create virtual environment and install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Get your tokens:**

   **GitHub Personal Access Token:**
   - Go to https://github.com/settings/tokens
   - Generate new token (classic)
   - Check `repo` scope
   - Copy the token

    **Microsoft Graph Client Credentials:**
    - Go to https://portal.azure.com → App registrations
    - Click **New registration**
    - Enter a name, choose **Accounts in this organizational directory only**
    - After registration, copy the **Application (client) ID**
    - Go to **Certificates & secrets** → New client secret → copy the value
    - Copy the **Directory (tenant) ID** from the Overview
    - Go to **API permissions** → Add permission → Microsoft Graph → Application permissions
    - Search for and add `Tasks.ReadWrite.All`
    - Click **Grant admin consent for [your organization]**

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

    Edit `.env` and fill in:
    - `GITHUB_TOKEN` - Your GitHub PAT
    - `GRAPH_CLIENT_ID` - Your Azure AD Application (client) ID
    - `GRAPH_CLIENT_SECRET` - Your Azure AD client secret value
    - `GRAPH_TENANT_ID` - Your Azure AD Directory (tenant) ID
    - `PLAN_ID` and `BUCKET_ID` are already set

## Running

1. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

2. **Start the sync service:**
   ```bash
   python sync.py
   ```

The service will:
- Poll every 15 minutes (configurable)
- Sync open GitHub issues ↔ active Planner tasks
- Skip closed/completed items
- Create ID mappings in `sync_mappings.db`
- Sync title and description both directions

To stop the service, press `Ctrl+C`. To exit the virtual environment, run:
```bash
deactivate
```

## Note on Authentication

- GitHub PATs don't expire but you can rotate them
- Microsoft Graph tokens are automatically refreshed using MSAL (no manual refresh needed)
- If you get 403 errors, verify that the Azure AD app has `Tasks.ReadWrite.All` permission and admin consent