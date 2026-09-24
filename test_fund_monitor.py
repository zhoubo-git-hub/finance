import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import fund_monitor as monitor


class FundEstimateTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime(2026, 9, 24, 14, 52, tzinfo=ZoneInfo("Asia/Shanghai"))

    def sina_response(self, code, nav, estimate, change):
        payload = (
            f'var hq_str_fu_{code}="Fund,14:50:00,x,{nav},x,x,x,'
            f'2026-09-24,{estimate},{change}";'
        )
        return Mock(text=payload, raise_for_status=Mock())

    def test_zero_unchanged_sina_estimate_uses_target_etf(self):
        for code, symbol, change in (
            ("014415", "sh516670", -1.67),
            ("016185", "sz159611", 0.0),
        ):
            with (
                self.subTest(code=code),
                patch.object(monitor, "now_local", return_value=self.today),
                patch.object(
                    monitor,
                    "request_get",
                    return_value=self.sina_response(code, "1.0000", "1.0000", "0"),
                ),
                patch.object(
                    monitor,
                    "get_latest_official_nav",
                    return_value={"date": "2026-09-23", "nav": 1.0},
                ),
                patch.object(
                    monitor,
                    "get_tencent_proxy_change",
                    return_value={"change_percent": change, "time": "2026-09-24 14:50:00"},
                ) as proxy_quote,
                patch.object(monitor, "log_message"),
            ):
                data = monitor.get_fund_data(code)

            proxy_quote.assert_called_once_with(symbol)
            self.assertEqual(data["gszzl"], f"{change:.2f}")
            self.assertIn("代理估值", data["estimate_note"])

    def test_nonzero_sina_estimate_is_preserved(self):
        with (
            patch.object(monitor, "now_local", return_value=self.today),
            patch.object(
                monitor,
                "request_get",
                return_value=self.sina_response("014415", "1.0000", "0.9800", "-2.0"),
            ),
            patch.object(monitor, "get_proxy_fund_estimate") as proxy_estimate,
        ):
            data = monitor.get_fund_data("014415")

        self.assertEqual(data["gszzl"], "-2.0")
        proxy_estimate.assert_not_called()

    def test_unverified_zero_without_proxy_is_not_reported_as_zero(self):
        with (
            patch.object(monitor, "now_local", return_value=self.today),
            patch.object(
                monitor,
                "request_get",
                return_value=self.sina_response("999999", "1.0000", "1.0000", "0"),
            ),
            patch.object(monitor, "log_message"),
        ):
            self.assertIsNone(monitor.get_fund_data("999999"))

    def test_stale_target_etf_quote_is_not_reported(self):
        with (
            patch.object(monitor, "now_local", return_value=self.today),
            patch.object(
                monitor,
                "get_latest_official_nav",
                return_value={"date": "2026-09-23", "nav": 1.0},
            ),
            patch.object(
                monitor,
                "get_tencent_proxy_change",
                return_value={"change_percent": -1.67, "time": "2026-09-23 15:00:00"},
            ),
            patch.object(monitor, "log_message"),
        ):
            self.assertIsNone(monitor.get_proxy_fund_estimate("014415"))


if __name__ == "__main__":
    unittest.main()
