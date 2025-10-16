# GitHub Actions Setup Guide

This guide will help you migrate your flight monitoring app from Google Cloud to GitHub Actions.

## Cost Comparison

- **Google Cloud App Engine**: $5-30/month (always running)
- **GitHub Actions**: **$0/month** (public repo) or **$0/month** (private repo with free tier)

## Setup Steps

### 1. Create a GitHub Repository

```bash
# Initialize git (if not already done)
git init

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
```

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add these three secrets:

1. **SEATS_API_KEY**
   - Value: `pro_2whFTuolRGFLZBsQjNbHFqTgb30`

2. **TELEGRAM_BOT_TOKEN**
   - Value: `8460887866:AAGsF2IOSWnjpn1_OFfOR9lJDOjv6PDF0Ro`

3. **TELEGRAM_CHAT_ID**
   - Value: `5007736940`

### 3. Remove Hardcoded Secrets (IMPORTANT!)

Edit `flights_availability_check.py` and change lines 8-10:

```python
# Before (with hardcoded values):
SEATS_API_KEY = os.environ.get("SEATS_API_KEY", "pro_2whFTuolRGFLZBsQjNbHFqTgb30")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8460887866:AAGsF2IOSWnjpn1_OFfOR9lJDOjv6PDF0Ro")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "5007736940")

# After (no hardcoded values):
SEATS_API_KEY = os.environ.get("SEATS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
```

### 4. Push to GitHub

```bash
# Add all files
git add .

# Commit
git commit -m "Migrate to GitHub Actions"

# Push to GitHub
git push -u origin main
```

### 5. Enable GitHub Actions

1. Go to your repository on GitHub
2. Click the "Actions" tab
3. Click "I understand my workflows, go ahead and enable them"
4. You should see "Flight Availability Monitor" workflow

### 6. Test the Workflow

**Option 1: Wait for scheduled run** (next 5-minute interval)

**Option 2: Manual trigger**
1. Go to Actions tab
2. Click "Flight Availability Monitor"
3. Click "Run workflow" → "Run workflow"

### 7. Monitor the Workflow

- Go to Actions tab to see all runs
- Click on any run to see detailed logs
- You'll receive Telegram notifications as before

## How It Works

- **Schedule**: Runs every 5 minutes via GitHub Actions cron
- **Cost**: $0 (public repo) or uses your 2,000 free minutes/month
- **Runtime**: ~30-60 seconds per check
- **Monthly usage**: ~8,640-17,280 minutes (if private repo)

## Disable Auto-Disable After 60 Days

GitHub automatically disables scheduled workflows after 60 days of no repo activity. To prevent this:

**Option 1**: Make any commit/push to the repo every 60 days

**Option 2**: Create an auto-commit workflow (add this as `.github/workflows/keep-alive.yml`):

```yaml
name: Keep Alive

on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly on the 1st
  workflow_dispatch:

jobs:
  keep-alive:
    runs-on: ubuntu-latest
    steps:
      - name: Keep workflow active
        run: echo "Keeping workflow active"
```

## Troubleshooting

### Workflow not running?
- Check Actions tab is enabled
- Verify secrets are set correctly
- Check workflow file syntax

### Getting errors?
- Check Actions tab → Click on failed run → View logs
- Verify your API keys are still valid

### No Telegram messages?
- Test manually: Actions → Run workflow
- Check Telegram bot token is correct
- Verify chat ID is correct

## Cleanup Old Google Cloud Resources

```bash
# Stop all versions
gcloud app versions list
gcloud app versions stop VERSION_ID --quiet

# Optional: Delete the project entirely
gcloud projects delete PROJECT_ID
```

## Files You Can Delete

These are no longer needed for GitHub Actions:
- `app.yaml` (Google Cloud config)
- `cron.yaml` (Google Cloud cron)
- `main.py` (Flask app - not needed for GitHub Actions)
- `.gcloudignore`
- `DEPLOYMENT_GUIDE.md`

**Keep these:**
- `flights_availability_check.py` (main script)
- `requirements.txt` (dependencies)
- `.github/workflows/flight-monitor.yml` (GitHub Actions workflow)
- `.env` (for local testing)

## Local Testing

You can still test locally:

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows

# Run check once
python flights_availability_check.py
```

## Making Changes

After making changes to the code:

```bash
git add .
git commit -m "Update flight search criteria"
git push
```

Changes take effect immediately for the next scheduled run.
