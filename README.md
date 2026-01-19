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

   **Microsoft Graph Bearer Token:**
   - Open your browser's DevTools (F12)
   - Go to **Network** tab
   - Filter for `graph.microsoft.com`
   - Navigate to your Planner in Teams/browser
   - Click any request → Headers → Look for `Authorization: Bearer eyJ0...`
   - Copy everything after `Bearer `

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and fill in:
   - `GITHUB_TOKEN` - Your GitHub PAT
   - `GRAPH_TOKEN` - Your Microsoft Graph bearer token
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

## Note on Tokens

- GitHub PATs don't expire but you can rotate them
- Microsoft Graph bearer tokens expire (~1 hour)
- If Graph API returns 401, refresh your token from browser and update `.env`