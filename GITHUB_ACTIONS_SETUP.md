# GitHub Actions Setup

This project can run without the local Windows scheduler by using GitHub Actions.

## What is included

- `fund_monitor.py`
  - Runs once and exits.
  - Skips non-trading days automatically.
  - Reads mail credentials from environment variables.
- `.github/workflows/fund-monitor.yml`
  - Supports manual `workflow_dispatch` for testing and for the local Windows scheduler trigger.

## Required GitHub secrets

Add these repository secrets in `Settings -> Secrets and variables -> Actions`:

- `SENDER_EMAIL`
- `SENDER_PASS`

## Notes

- The workflow already uses `Asia/Shanghai`.
- The single automatic trigger should be a local Windows task at `14:52` on weekdays that runs `gh workflow run fund-monitor.yml --repo zhoubo-git-hub/finance`.
- Receiver addresses are currently stored in the workflow file.
- Do not also enable GitHub `schedule`, or the send time will drift and duplicate the local `14:52` trigger.
