# GitHub Actions Setup

GitHub Actions fetches data and sends mail. A Windows task triggers that workflow
at 14:52 Asia/Shanghai on weekdays.

## What is included

- `fund_monitor.py`
  - Runs once and exits.
  - Skips non-trading days automatically.
  - Reads mail credentials from environment variables.
- `.github/workflows/fund-monitor.yml`
  - Supports manual `workflow_dispatch` for testing and for the local Windows scheduler trigger.
- `trigger_fund_monitor.py`
  - Uses only Python's standard library and the authenticated GitHub CLI.
  - Checks for an existing run after 14:52 before every dispatch attempt.
  - Retries trigger failures up to three times, with 20 and 60 second delays.
  - Records command failures in a rotating `fund_trigger.log` beside the script.
  - Does not automatically resend an existing failed run because one group may already have received mail.

## Required GitHub secrets

Add these repository secrets in `Settings -> Secrets and variables -> Actions`:

- `SENDER_EMAIL`
- `SENDER_PASS`

## Notes

- The workflow already uses `Asia/Shanghai`.
- The single automatic trigger is `FundMonitorDaily`, at `14:52` on weekdays.
- Its action uses Python to run the deployed `trigger_fund_monitor.py` from
  `%USERPROFILE%\IdeaProjects\FundMonitorRuntime`. Keep that deployment independent
  of temporary Codex worktrees and sandboxed AppData locations.
- The original task definition is backed up as `FundMonitorDaily.before-*.xml`
  in the deployment directory before the action is changed.
- Run `install_fund_trigger.ps1` with the existing task's administrator account
  to deploy the trigger. It preserves the task's schedule and identity, sets a
  ten-minute execution limit, and uses `pythonw.exe` to avoid a console window.
- Use `python trigger_fund_monitor.py --check-only` to check connectivity and
  duplicate detection without triggering any mail. Manual email tests can still
  use `gh workflow run fund-monitor.yml --repo zhoubo-git-hub/finance --ref main`.
- Receiver addresses are currently stored in the workflow file.
- Do not also enable GitHub `schedule`, or the send time will drift and duplicate the local `14:52` trigger.
