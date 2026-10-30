import json
import unittest
from datetime import datetime
from unittest.mock import Mock

import trigger_fund_monitor as trigger


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 30, 15, 10, tzinfo=trigger.SHANGHAI)
        self.run = {
            "databaseId": 123,
            "createdAt": "2026-10-30T06:52:05Z",
            "status": "completed",
            "conclusion": "success",
            "url": "https://github.com/zhoubo-git-hub/finance/actions/runs/123",
        }

    def test_existing_afternoon_run_prevents_duplicate_send(self):
        command = Mock(return_value=json.dumps([self.run]))
        self.assertEqual(trigger.trigger(self.now, command=command), 0)
        self.assertEqual(command.call_count, 1)

    def test_morning_manual_test_does_not_suppress_scheduled_send(self):
        self.run["createdAt"] = "2026-10-30T02:00:00Z"
        command = Mock(side_effect=[json.dumps([self.run]), "accepted"])
        self.assertEqual(trigger.trigger(self.now, command=command), 0)
        self.assertEqual(command.call_args.args[0][:2], ["workflow", "run"])

    def test_lost_dispatch_response_is_checked_before_retry(self):
        command = Mock(side_effect=["[]", RuntimeError("network disconnected"), json.dumps([self.run])])
        sleep = Mock()
        self.assertEqual(trigger.trigger(self.now, command=command, sleep=sleep), 0)
        dispatches = [call for call in command.call_args_list if call.args[0][:2] == ["workflow", "run"]]
        self.assertEqual(len(dispatches), 1)
        sleep.assert_called_once_with(20)

    def test_failed_queries_never_dispatch_blindly(self):
        command = Mock(side_effect=RuntimeError("API unavailable"))
        sleep = Mock()
        self.assertEqual(trigger.trigger(self.now, command=command, sleep=sleep), 1)
        self.assertEqual(command.call_count, 3)
        self.assertTrue(all(call.args[0][:2] == ["run", "list"] for call in command.call_args_list))

    def test_check_only_cannot_dispatch(self):
        command = Mock(return_value="[]")
        self.assertEqual(trigger.trigger(self.now, check_only=True, command=command), 0)
        self.assertEqual(command.call_count, 1)

    def test_failed_existing_run_requires_review_without_resending(self):
        self.run["conclusion"] = "failure"
        command = Mock(return_value=json.dumps([self.run]))
        self.assertEqual(trigger.trigger(self.now, command=command), 1)
        self.assertEqual(command.call_count, 1)


if __name__ == "__main__":
    unittest.main()
