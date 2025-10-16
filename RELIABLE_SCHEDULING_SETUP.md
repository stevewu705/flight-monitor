# Reliable 5-Minute Scheduling for GitHub Actions

GitHub Actions scheduled workflows are unreliable and can have 10-60 minute delays. To get reliable 5-minute checks, use an external cron service to trigger your workflow.

## Step 1: Create a GitHub Personal Access Token (PAT)

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name it: `Flight Monitor Trigger`
4. Set expiration: `No expiration` (or 1 year)
5. Check permissions:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
6. Click "Generate token"
7. **Copy the token immediately** (you won't see it again!)

## Step 2: Choose a Free External Cron Service

### Option A: cron-job.org (Recommended - Easiest)

1. Go to https://cron-job.org/en/
2. Sign up for free account
3. Create new cron job:
   - **Title**: Flight Monitor Trigger
   - **URL**: `https://api.github.com/repos/stevewu705/flight-monitor/dispatches`
   - **Schedule**: Every 5 minutes
   - **Request Method**: POST
   - **Headers**:
     ```
     Authorization: Bearer YOUR_GITHUB_TOKEN_HERE
     Accept: application/vnd.github.v3+json
     Content-Type: application/json
     ```
   - **Request Body**:
     ```json
     {"event_type": "check-flights"}
     ```
4. Save and enable

### Option B: EasyCron (Alternative)

1. Go to https://www.easycron.com/
2. Sign up for free account (allows 1 job)
3. Create cron job:
   - **Cron Expression**: `*/5 * * * *`
   - **URL to call**: `https://api.github.com/repos/stevewu705/flight-monitor/dispatches`
   - **HTTP Method**: POST
   - **HTTP Headers**:
     ```
     Authorization: Bearer YOUR_GITHUB_TOKEN_HERE
     Accept: application/vnd.github.v3+json
     Content-Type: application/json
     ```
   - **POST Data**:
     ```json
     {"event_type": "check-flights"}
     ```
4. Enable the cron job

### Option C: UptimeRobot (Alternative - Designed for uptime monitoring)

1. Go to https://uptimerobot.com/
2. Sign up for free account
3. Add new monitor:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: Flight Monitor
   - **URL**: `https://api.github.com/repos/stevewu705/flight-monitor/dispatches`
   - **Monitoring Interval**: 5 minutes
   - **Monitor Timeout**: 30 seconds
   - **HTTP Method**: POST
   - **Custom HTTP Headers**:
     ```
     Authorization: Bearer YOUR_GITHUB_TOKEN_HERE
     Accept: application/vnd.github.v3+json
     Content-Type: application/json
     ```
   - **POST Value**:
     ```json
     {"event_type": "check-flights"}
     ```

## Step 3: Test the Setup

1. Wait 5 minutes for the first trigger
2. Go to your GitHub repo → Actions tab
3. You should see workflow runs triggered by "repository_dispatch" instead of "schedule"
4. These should occur reliably every 5 minutes

## How It Works

- The external service calls GitHub's API every 5 minutes
- This triggers your workflow via `repository_dispatch` event
- Your workflow runs immediately (usually within 30 seconds)
- Much more reliable than GitHub's built-in cron scheduling

## Troubleshooting

- **401 Unauthorized**: Check your GitHub token is correct and has `repo` + `workflow` permissions
- **404 Not Found**: Check the repository name in the URL is correct
- **No workflow runs**: Make sure the workflow file has `repository_dispatch` trigger (already added in .github/workflows/flight-monitor.yml:12)
