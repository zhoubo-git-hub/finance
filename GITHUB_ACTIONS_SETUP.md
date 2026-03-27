# GitHub Actions Setup

This project can run without the local Windows scheduler by using GitHub Actions.

## What is included

- `fund_monitor.py`
  - Runs once and exits.
  - Skips non-trading days automatically.
  - Reads mail credentials from environment variables.
- `.github/workflows/fund-monitor.yml`
  - Runs at `14:50` on weekdays in China time.
  - Supports manual runs with `workflow_dispatch`.

## Required GitHub secrets

Add these repository secrets in `Settings -> Secrets and variables -> Actions`:

- `SENDER_EMAIL`
- `SENDER_PASS`

## Suggested first test

After pushing to GitHub:

1. Open the `Actions` tab.
2. Open `Fund Monitor`.
3. Click `Run workflow`.
4. Check the uploaded `fund-monitor-log` artifact.

## Notes

- The workflow already uses `Asia/Shanghai`.
- Receiver addresses are currently stored in the workflow file.
- The local Windows task is no longer needed.
