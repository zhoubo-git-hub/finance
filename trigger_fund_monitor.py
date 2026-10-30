"""Trigger the GitHub mail job from Windows Task Scheduler without duplicates."""

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, time as clock_time, timedelta, timezone


SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
REPOSITORY = "zhoubo-git-hub/finance"
WORKFLOW = "fund-monitor.yml"
GH_PATH = Path(r"C:\Program Files\GitHub CLI\gh.exe")
RETRY_DELAYS = (20, 60)
COMMAND_TIMEOUT = 45
LOG = logging.getLogger("fund-trigger")


def redact(text):
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)", "[REDACTED]", text)
    return re.sub(r"(?i)(authorization:\s*(?:bearer|token)\s+)\S+", r"\1[REDACTED]", text)


def configure_log(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.setLevel(logging.INFO)
    LOG.addHandler(handler)


def run_gh(arguments):
    env = os.environ.copy()
    env.update(GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1")
    env.pop("GH_DEBUG", None)
    result = subprocess.run(
        [str(GH_PATH), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=COMMAND_TIMEOUT,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        detail = redact((result.stderr or result.stdout).strip())[-4000:]
        raise RuntimeError(f"GitHub CLI exited {result.returncode}: {detail}")
    return result.stdout


def existing_run(payload, scheduled_at):
    records = json.loads(payload)
    if not isinstance(records, list):
        raise ValueError("Expected a GitHub run list; refusing a blind dispatch.")
    for record in records:
        created_at = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
        if created_at.astimezone(SHANGHAI).date() == scheduled_at.date() and created_at >= scheduled_at:
            return record
    return None


def trigger(now, check_only=False, command=run_gh, sleep=time.sleep):
    local_now = now.astimezone(SHANGHAI)
    scheduled_at = datetime.combine(local_now.date(), clock_time(14, 52), tzinfo=SHANGHAI)
    if local_now < scheduled_at:
        LOG.info("Not yet due: next send window starts at %s.", scheduled_at.isoformat())
        return 0

    for attempt in range(1, len(RETRY_DELAYS) + 2):
        try:
            payload = command([
                "run", "list", "--repo", REPOSITORY, "--workflow", WORKFLOW,
                "--branch", "main", "--event", "workflow_dispatch", "--limit", "30",
                "--json", "databaseId,status,conclusion,createdAt,url",
            ])
            run = existing_run(payload, scheduled_at)
            if run:
                LOG.info(
                    "Existing run after 14:52: %s status=%s conclusion=%s; skip dispatch.",
                    run["url"], run["status"], run.get("conclusion"),
                )
                if run["status"] == "completed" and run.get("conclusion") != "success":
                    LOG.error("Existing run needs review; automatic resend could duplicate one group.")
                    return 1
                return 0
            if check_only:
                LOG.info("Check only: no existing run; dispatch would be required.")
                return 0

            output = command([
                "workflow", "run", WORKFLOW, "--repo", REPOSITORY, "--ref", "main",
            ])
            LOG.info("Dispatch accepted on attempt %s. %s", attempt, redact(output.strip()))
            return 0
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            LOG.error("Attempt %s failed: %s", attempt, redact(str(exc)))
            if attempt <= len(RETRY_DELAYS):
                delay = RETRY_DELAYS[attempt - 1]
                LOG.info("Retry in %s seconds; recheck existing runs before dispatch.", delay)
                sleep(delay)
    LOG.error("All trigger attempts failed. No further automatic attempts this invocation.")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Query GitHub without sending a dispatch.")
    parser.add_argument("--log-file", type=Path, default=Path(__file__).with_name("fund_trigger.log"))
    args = parser.parse_args()
    configure_log(args.log_file)
    LOG.info("Trigger started, check_only=%s.", args.check_only)
    result = trigger(datetime.now(SHANGHAI), check_only=args.check_only)
    LOG.info("Trigger finished, exit=%s.", result)
    return result


if __name__ == "__main__":
    sys.exit(main())
