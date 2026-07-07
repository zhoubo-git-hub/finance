# GitHub Actions Setup

This project can run without the local Windows scheduler by using GitHub Actions.

## What is included

- `fund_monitor.py`
  - Runs once and exits.
  - Skips non-trading days automatically.
  - Reads mail credentials from environment variables.
- `.github/workflows/fund-monitor.yml`
  - Runs at `14:52` on weekdays in China time.
  - Keeps the weekday scheduled trigger plus manual `workflow_dispatch` for testing.

## Required GitHub secrets

Add these repository secrets in `Settings -> Secrets and variables -> Actions`:

- `SENDER_EMAIL`
- `SENDER_PASS`

## Notes

- The workflow already uses `Asia/Shanghai`.
- Receiver addresses are currently stored in the workflow file.
- The local Windows task is no longer needed.
