import json
import os
import re
import smtplib
import sys
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

try:
    import exchange_calendars as xcals
    import pandas as pd
except Exception:
    xcals = None
    pd = None


APP_TIMEZONE = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Shanghai"))
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASS = os.environ.get("SENDER_PASS", "")
RECEIVER_GROUP_A = os.environ.get("RECEIVER_GROUP_A", "542335825@qq.com")
RECEIVER_GROUP_B = os.environ.get("RECEIVER_GROUP_B", "3217542796@qq.com")

ALL_FUND_CODES = ["012553", "020274", "014415", "021620", "010770", "017102", "016185", "513870"]
GROUP_A_CODES = ["012553", "020274", "014415"]
GROUP_B_CODES = [code for code in ALL_FUND_CODES if code not in GROUP_A_CODES]

NASDAQ_SYMBOL = "IXIC"
NASDAQ_ENDPOINTS = [
    "https://hq.sinajs.cn/list=int_nasdaq",
    "https://hq.sinajs.cn/list=gb_$ixic",
]

TRADING_CALENDAR_CODE = os.environ.get("TRADING_CALENDAR_CODE", "XSHG")
LOG_PATH = Path(__file__).with_name("fund_monitor.log")
PROXIES = {
    "http": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
    "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)
CALENDAR = None


def now_local():
    return datetime.now(APP_TIMEZONE)


def ensure_log_file():
    if LOG_PATH.exists():
        try:
            with LOG_PATH.open("rb") as file:
                start = file.read(3)
            if start != b"\xef\xbb\xbf":
                LOG_PATH.replace(LOG_PATH.with_suffix(".log.bak"))
        except Exception:
            pass
    if not LOG_PATH.exists():
        with LOG_PATH.open("w", encoding="utf-8-sig") as file:
            file.write("")


def log_message(message):
    line = f"[{now_local().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    try:
        ensure_log_file()
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except Exception:
        pass


def fail(message):
    log_message(message)
    raise SystemExit(1)


def validate_config():
    if not SENDER_EMAIL:
        fail("Missing SENDER_EMAIL environment variable.")
    if not SENDER_PASS:
        fail("Missing SENDER_PASS environment variable.")


def request_get(url, headers=None, params=None, timeout=10):
    return requests.get(
        url,
        headers=headers,
        params=params,
        timeout=timeout,
        proxies=PROXIES if (PROXIES.get("http") or PROXIES.get("https")) else None,
    )


def is_trading_day(check_date):
    if xcals is None or pd is None:
        return check_date.weekday() < 5

    global CALENDAR
    if CALENDAR is None:
        try:
            CALENDAR = xcals.get_calendar(TRADING_CALENDAR_CODE)
        except Exception as exc:
            log_message(f"Trading calendar load failed: {exc}")
            return check_date.weekday() < 5

    try:
        return CALENDAR.is_session(pd.Timestamp(check_date))
    except Exception as exc:
        log_message(f"Trading day check failed: {exc}")
        return check_date.weekday() < 5


def get_fund_data(code):
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    headers = {"User-Agent": USER_AGENT}
    try:
        response = request_get(url, headers=headers, timeout=10)
        response.raise_for_status()
        match = re.search(r"jsonpgz\((.*)\);", response.text)
        if match:
            return json.loads(match.group(1))
    except Exception as exc:
        log_message(f"Failed to fetch fund {code}: {exc}")
    return None


def parse_sina_index_payload(text):
    match = re.search(r'="(.*)"', text)
    if not match:
        return None

    parts = match.group(1).split(",")
    if len(parts) < 4:
        return None

    try:
        price = float(parts[1])
    except Exception:
        price = None

    try:
        change = float(parts[2])
    except Exception:
        change = None

    try:
        change_percent = float(parts[3].strip("%"))
    except Exception:
        change_percent = None

    return {
        "name": parts[0] or "纳斯达克综合指数",
        "symbol": NASDAQ_SYMBOL,
        "price": price,
        "change": change,
        "change_percent": change_percent,
        "time": now_local().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_nasdaq_data():
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://finance.sina.com.cn",
    }
    for url in NASDAQ_ENDPOINTS:
        try:
            response = request_get(url, headers=headers, timeout=10)
            response.raise_for_status()
            parsed = parse_sina_index_payload(response.text)
            if parsed:
                return parsed
        except Exception as exc:
            log_message(f"Failed to fetch Nasdaq data ({url}): {exc}")
    return None


def generate_fund_report(data_list, title):
    lines = [f"{title} ({now_local().strftime('%Y-%m-%d %H:%M:%S')})", "=" * 40]
    for data in data_list:
        lines.append(f"【{data['name']} ({data['fundcode']})】")
        lines.append(f"当前估值: {data['gsz']} (涨跌幅: {data['gszzl']}%)")
        lines.append(f"更新时间: {data['gztime']}")
        lines.append("-" * 40)
    return "\n".join(lines)


def append_nasdaq(report_text, nasdaq_data):
    if not nasdaq_data:
        return report_text

    change = nasdaq_data.get("change")
    change_percent = nasdaq_data.get("change_percent")
    change_str = f"{change:+.2f}" if isinstance(change, (int, float)) else "N/A"
    change_percent_str = f"{change_percent:+.2f}%" if isinstance(change_percent, (int, float)) else "N/A"

    lines = [report_text, "【纳指】"]
    lines.append(f"指数: {nasdaq_data['name']} ({nasdaq_data['symbol']})")
    lines.append(f"当前: {nasdaq_data['price']} (涨跌: {change_str} 点 / {change_percent_str})")
    lines.append(f"更新时间: {nasdaq_data['time']}")
    lines.append("-" * 40)
    return "\n".join(lines)


def send_email(content, receiver_email, subject_suffix):
    msg = MIMEText(content, "plain", "utf-8")
    msg["From"] = f"{Header('基金助手', 'utf-8').encode()} <{SENDER_EMAIL}>"
    msg["To"] = f"{Header('投资者', 'utf-8').encode()} <{receiver_email}>"
    msg["Subject"] = Header(
        f"每日基金行情提醒 - {subject_suffix} - {now_local().strftime('%Y-%m-%d')}",
        "utf-8",
    )

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, [receiver_email], msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        log_message(f"Failed to send email: {exc}")
        return False


def fetch_funds(codes):
    results = []
    for code in codes:
        data = get_fund_data(code)
        if data:
            results.append(data)
    return results


def run_once():
    validate_config()

    today = now_local().date()
    if not is_trading_day(today):
        log_message(f"Non-trading day, skip send: {today}")
        return

    group_a_results = fetch_funds(GROUP_A_CODES)
    group_b_results = fetch_funds(GROUP_B_CODES)
    nasdaq_data = get_nasdaq_data()

    if group_a_results:
        report_a = generate_fund_report(group_a_results, "基金实时监控报告（A 组）")
        if send_email(report_a, RECEIVER_GROUP_A, "A 组"):
            log_message("A group email sent.")
        else:
            log_message("A group email failed.")
    else:
        log_message("A group fund data is empty.")

    if group_b_results or nasdaq_data:
        report_b = generate_fund_report(group_b_results, "基金实时监控报告（B 组）")
        report_b = append_nasdaq(report_b, nasdaq_data)
        if send_email(report_b, RECEIVER_GROUP_B, "B 组+纳指"):
            log_message("B group email sent.")
        else:
            log_message("B group email failed.")
    else:
        log_message("B group fund data and Nasdaq data are empty.")


if __name__ == "__main__":
    try:
        run_once()
    except KeyboardInterrupt:
        sys.exit(130)
