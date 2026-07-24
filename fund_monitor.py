import os
import re
import smtplib
import sys
import time
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
SMTP_FALLBACK_PORT = int(os.environ.get("SMTP_FALLBACK_PORT", "587"))
SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "15"))
SMTP_RETRY_COUNT = int(os.environ.get("SMTP_RETRY_COUNT", "2"))
SMTP_RETRY_DELAY = int(os.environ.get("SMTP_RETRY_DELAY", "3"))

SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASS = os.environ.get("SENDER_PASS", "")
RECEIVER_GROUP_A = os.environ.get("RECEIVER_GROUP_A", "542335825@qq.com")
RECEIVER_GROUP_B = os.environ.get("RECEIVER_GROUP_B", "3217542796@qq.com")

ALL_FUND_CODES = [
    "012553",
    "020274",
    "014415",
    "021620",
    "010770",
    "017102",
    "016185",
    "513870",
    "019432",
    "163813",
    "513650",
    "016452",
    "003547",
]
GROUP_A_CODES = ["012553", "020274", "014415", "016185"]
GROUP_B_CODES = [code for code in ALL_FUND_CODES if code not in GROUP_A_CODES or code == "016185"]
EXCHANGE_ETF_CODES = {"513650", "513870"}
MAX_ESTIMATE_AGE_DAYS = 7
PROXY_ESTIMATE_CONFIG = {
    "016452": {
        "name": "南方纳斯达克100指数发起(QDII)A",
        "symbol": "gb_ndx",
        "label": "纳斯达克100指数",
    },
    "163813": {
        "name": "中银全球策略(QDII-FOF)A",
        "symbol": "gb_ixic",
        "label": "纳斯达克综合指数",
    },
    "003547": {
        "name": "鹏华丰禄债券",
        "symbol": "sh000012",
        "label": "上证国债指数",
    },
}

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
    if code in EXCHANGE_ETF_CODES:
        return get_exchange_etf_data(code)

    data = get_sina_fund_estimate(code)
    if data:
        return data

    if code in PROXY_ESTIMATE_CONFIG:
        return get_proxy_fund_estimate(code)

    log_message(f"No real-time estimate available for fund {code}.")
    return None


def get_sina_fund_estimate(code):
    url = f"https://hq.sinajs.cn/list=fu_{code}"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://finance.sina.com.cn",
    }
    try:
        response = request_get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = "gbk"
        match = re.search(r'="(.*)"', response.text)
        if not match or not match.group(1):
            return None

        parts = match.group(1).split(",")
        if len(parts) < 10 or not parts[8] or not parts[9]:
            log_message(f"Malformed Sina estimate for fund {code}.")
            return None

        estimate_date = datetime.strptime(parts[7], "%Y-%m-%d").date()
        estimate_age_days = (now_local().date() - estimate_date).days
        if estimate_age_days < 0 or estimate_age_days > MAX_ESTIMATE_AGE_DAYS:
            log_message(
                f"Stale Sina estimate for fund {code}: {parts[7]} "
                f"({estimate_age_days} days old)."
            )
            return None

        float(parts[8])
        float(parts[9])
        return {
            "fundcode": code,
            "name": parts[0],
            "jzrq": parts[7],
            "dwjz": parts[3],
            "gsz": parts[8],
            "gszzl": parts[9],
            "gztime": f"{parts[7]} {parts[1]}",
        }
    except Exception as exc:
        log_message(f"Failed to fetch Sina estimate for fund {code}: {exc}")
    return None


def get_latest_official_nav(code):
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://fundf10.eastmoney.com/",
    }
    params = {
        "fundCode": code,
        "pageIndex": 1,
        "pageSize": 1,
        "startDate": "",
        "endDate": "",
    }
    try:
        response = request_get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        records = response.json().get("Data", {}).get("LSJZList", [])
        if not records:
            return None

        record = records[0]
        return {
            "date": record["FSRQ"],
            "nav": float(record["DWJZ"]),
        }
    except Exception as exc:
        log_message(f"Failed to fetch official NAV for fund {code}: {exc}")
        return None


def get_sina_proxy_change(symbol):
    url = f"https://hq.sinajs.cn/list={symbol}"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://finance.sina.com.cn",
    }
    try:
        response = request_get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = "gbk"
        match = re.search(r'="(.*)"', response.text)
        if not match or not match.group(1):
            return None

        parts = match.group(1).split(",")
        if symbol.startswith("gb_"):
            if len(parts) < 4:
                return None
            return {
                "change_percent": float(parts[2]),
                "time": parts[3],
            }

        if len(parts) < 32:
            return None
        previous_close = float(parts[2])
        current_price = float(parts[3])
        if not previous_close:
            return None
        return {
            "change_percent": (current_price - previous_close) / previous_close * 100,
            "time": f"{parts[30]} {parts[31]}",
        }
    except Exception as exc:
        log_message(f"Failed to fetch proxy quote {symbol}: {exc}")
        return None


def get_proxy_fund_estimate(code):
    config = PROXY_ESTIMATE_CONFIG[code]
    official_nav = get_latest_official_nav(code)
    proxy_quote = get_sina_proxy_change(config["symbol"])
    if not official_nav or not proxy_quote:
        log_message(f"Failed to build proxy estimate for fund {code}.")
        return None

    change_percent = proxy_quote["change_percent"]
    estimated_nav = official_nav["nav"] * (1 + change_percent / 100)
    estimate_note = (
        f"代理估值：按{config['label']} {change_percent:+.2f}% 测算，"
        f"基准为 {official_nav['date']} 官方净值"
    )
    log_message(f"Fund {code} uses proxy estimate based on {config['label']}.")
    return {
        "fundcode": code,
        "name": config["name"],
        "jzrq": official_nav["date"],
        "dwjz": f"{official_nav['nav']:.4f}",
        "gsz": f"{estimated_nav:.4f}",
        "gszzl": f"{change_percent:.2f}",
        "gztime": proxy_quote["time"],
        "estimate_note": estimate_note,
    }


def get_exchange_etf_data(code):
    url = f"https://hq.sinajs.cn/list=sh{code}"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://finance.sina.com.cn",
    }
    try:
        response = request_get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = "gbk"
        match = re.search(r'="(.*)"', response.text)
        if not match:
            return None

        parts = match.group(1).split(",")
        if len(parts) < 32:
            return None

        previous_close = float(parts[2])
        current_price = float(parts[3])
        change_percent = (
            (current_price - previous_close) / previous_close * 100
            if previous_close
            else 0
        )
        return {
            "fundcode": code,
            "name": parts[0],
            "jzrq": parts[30],
            "dwjz": f"{previous_close:.4f}",
            "gsz": f"{current_price:.4f}",
            "gszzl": f"{change_percent:.2f}",
            "gztime": f"{parts[30]} {parts[31]}",
        }
    except Exception as exc:
        log_message(f"Failed to fetch exchange ETF {code}: {exc}")
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


def parse_change_percent(value):
    try:
        return float(str(value).strip().rstrip("%"))
    except Exception:
        return None


def sort_funds_by_change(data_list):
    def sort_key(item):
        change = parse_change_percent(item.get("gszzl"))
        if change is None:
            return (1, 0.0)
        return (0, -change)

    return sorted(data_list, key=sort_key)


def generate_fund_report(data_list, title):
    lines = [f"{title} ({now_local().strftime('%Y-%m-%d %H:%M:%S')})", "=" * 40]
    for data in sort_funds_by_change(data_list):
        lines.append(f"【{data['name']} ({data['fundcode']})】")
        lines.append(f"当前估值: {data['gsz']} (涨跌幅: {data['gszzl']}%)")
        lines.append(f"更新时间: {data['gztime']}")
        if data.get("estimate_note"):
            lines.append(data["estimate_note"])
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

    transports = [
        ("SSL", SMTP_PORT),
        ("STARTTLS", SMTP_FALLBACK_PORT),
    ]
    for attempt in range(1, SMTP_RETRY_COUNT + 1):
        for mode, port in transports:
            try:
                if mode == "SSL":
                    server = smtplib.SMTP_SSL(
                        SMTP_SERVER,
                        port,
                        timeout=SMTP_TIMEOUT,
                    )
                else:
                    server = smtplib.SMTP(
                        SMTP_SERVER,
                        port,
                        timeout=SMTP_TIMEOUT,
                    )
                    server.ehlo()
                    server.starttls()
                    server.ehlo()

                try:
                    server.login(SENDER_EMAIL, SENDER_PASS)
                    server.sendmail(SENDER_EMAIL, [receiver_email], msg.as_string())
                    log_message(
                        f"Email transport succeeded via {mode} port {port} "
                        f"on attempt {attempt}."
                    )
                    return True
                finally:
                    try:
                        server.quit()
                    except Exception:
                        server.close()
            except Exception as exc:
                log_message(
                    f"Email transport failed via {mode} port {port} "
                    f"on attempt {attempt}: {exc}"
                )

        if attempt < SMTP_RETRY_COUNT:
            time.sleep(SMTP_RETRY_DELAY)

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

    send_failed = False

    if group_a_results:
        report_a = generate_fund_report(group_a_results, "基金实时监控报告（A 组）")
        if send_email(report_a, RECEIVER_GROUP_A, "A 组"):
            log_message("A group email sent.")
        else:
            log_message("A group email failed.")
            send_failed = True
    else:
        log_message("A group fund data is empty.")

    if group_b_results or nasdaq_data:
        report_b = generate_fund_report(group_b_results, "基金实时监控报告（B 组）")
        report_b = append_nasdaq(report_b, nasdaq_data)
        if send_email(report_b, RECEIVER_GROUP_B, "B 组+纳指"):
            log_message("B group email sent.")
        else:
            log_message("B group email failed.")
            send_failed = True
    else:
        log_message("B group fund data and Nasdaq data are empty.")

    if send_failed:
        fail("One or more group emails failed.")


if __name__ == "__main__":
    try:
        run_once()
    except KeyboardInterrupt:
        sys.exit(130)
