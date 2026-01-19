# AGENTS.md

This file provides information for AI agents working on this codebase.

## Project Overview

GitHub ↔ Microsoft Planner sync service that bidirectionally synchronizes issues and tasks.

## Technology Stack

- **Language:** Python 3.14
- **Dependencies:**
  - `requests==2.31.0` - HTTP client for API calls
  - `python-dotenv==1.0.0` - Environment variable management
  - `msal==1.25.0` - Microsoft Authentication Library for token refresh

## Development Guidelines

### Branching Strategy

- All commits go directly to `main` branch
- No feature branches - commit and push to `main`

### Commit Workflow

After implementing any feature or fix:
1. Test the changes (use `--oneshot` flag for quick testing)
2. Commit changes with descriptive message
3. Push to `main` immediately

```bash
git add .
git commit -m "Clear description of changes"
git push
```

### Testing

Use the `--oneshot` flag for testing:
```bash
python sync.py --oneshot
```

This runs one sync cycle and exits, making it easy to verify changes.

### Important Implementation Details

#### Microsoft Graph API ETag Handling

The Planner API requires an `If-Match` header with the current ETag for all update operations. The `update_planner_task()` function automatically handles this by:
1. Fetching the task to get its current ETag
2. Including the ETag in the update request headers

#### Authentication

- GitHub: Uses Personal Access Token (PAT)
- Microsoft Graph: Uses MSAL client credentials flow with automatic token refresh
- Tokens are refreshed automatically - no manual intervention needed

#### Sync Logic

- GitHub closed issues ↔ Planner 100% complete tasks
- GitHub open issues ↔ Planner 0-99% complete tasks
- Percent complete is derived from GitHub issue labels or state
- Both open and closed items are synced (no filtering)

### Environment Variables

Required in `.env`:
- `GITHUB_TOKEN` - GitHub Personal Access Token
- `GITHUB_REPO` - Repository in format `owner/repo`
- `GRAPH_CLIENT_ID` - Azure AD Application (client) ID
- `GRAPH_CLIENT_SECRET` - Azure AD client secret
- `GRAPH_TENANT_ID` - Azure AD Directory (tenant) ID
- `PLAN_ID` - Microsoft Planner plan ID
- `BUCKET_ID` - Microsoft Planner bucket ID
- `POLL_INTERVAL_MINUTES` - Sync interval (default: 15)

## Code Style

- Follow existing patterns and conventions
- No comments unless explicitly requested
- Use consistent formatting with existing code
