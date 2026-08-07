# Finance Fund Monitor

一个基于 Python 的基金与指数行情监控脚本。项目从公开行情接口获取基金、ETF 和纳斯达克指数数据，在交易日生成分组报告，并通过 SMTP 邮件发送。

> 本项目仅用于个人信息整理和技术学习，不构成投资建议。行情接口可能延迟、缺失或调整，请勿将结果作为唯一决策依据。

## 功能

- 获取场外基金估值和场内 ETF 行情。
- 对部分无法直接获取估值的基金，使用关联指数或 ETF 进行代理估算。
- 获取纳斯达克综合指数行情。
- 使用交易日历判断是否执行；依赖不可用时退化为工作日判断。
- 按基金分组生成纯文本报告并发送邮件。
- 支持 SMTP SSL、STARTTLS 回退和请求重试。
- 支持通过 GitHub Actions 手动运行并上传执行日志。

## 项目文件

| 路径 | 说明 |
|---|---|
| `fund_monitor.py` | 行情获取、报告生成和邮件发送主程序 |
| `requirements.txt` | Python 依赖 |
| `.github/workflows/fund-monitor.yml` | GitHub Actions 手动运行工作流 |
| `.env.example` | 环境变量参考模板；脚本不会自动读取该文件 |

## 环境要求

- Python 3.11 或更高版本
- 可访问所使用的行情数据源和 SMTP 服务
- 一个支持 SMTP 的发件邮箱及授权码

## 本地运行

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

运行前在当前终端设置至少以下环境变量：

- `SENDER_EMAIL`：发件邮箱
- `SENDER_PASS`：SMTP 授权码或应用密码
- `RECEIVER_GROUP_A`：A 组收件地址
- `RECEIVER_GROUP_B`：B 组收件地址

然后执行：

```bash
python fund_monitor.py
```

运行日志写入同目录的 `fund_monitor.log`。

## 配置项

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_TIMEZONE` | `Asia/Shanghai` | 报告和交易日判断时区 |
| `TRADING_CALENDAR_CODE` | `XSHG` | exchange-calendars 市场代码 |
| `SMTP_SERVER` | `smtp.qq.com` | SMTP 服务地址 |
| `SMTP_PORT` | `465` | SSL 端口 |
| `SMTP_FALLBACK_PORT` | `587` | STARTTLS 回退端口 |
| `SMTP_TIMEOUT` | `15` | SMTP 超时秒数 |
| `SMTP_RETRY_COUNT` | `2` | 邮件发送重试次数 |
| `SMTP_RETRY_DELAY` | `3` | 邮件重试间隔秒数 |
| `HTTP_RETRY_COUNT` | `2` | 行情请求重试次数 |
| `HTTP_RETRY_DELAY` | `1` | 行情请求重试间隔秒数 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 空 | 可选网络代理 |

基金代码和分组目前在 `fund_monitor.py` 的 `ALL_FUND_CODES`、`GROUP_A_CODES` 和 `GROUP_B_CODES` 中维护。

## GitHub Actions

工作流 `Fund Monitor` 当前通过 `workflow_dispatch` 手动触发。使用前请在仓库的 **Settings → Secrets and variables → Actions** 中配置：

- `SENDER_EMAIL`
- `SENDER_PASS`

如需自动定时运行，可在工作流中增加 `schedule`。GitHub Actions 的 cron 使用 UTC，请换算到目标时区。

## 数据源与容错

项目会使用新浪行情、东方财富历史净值以及腾讯行情作为部分数据来源或回退来源。接口不是稳定的正式契约，字段格式变化可能导致抓取失败。失败信息会记录到日志，GitHub Actions 失败时会上传日志文件。

## 安全说明

- 不要把邮箱密码、授权码、代理凭据或其他密钥提交到仓库。
- `.env.example` 仅用于说明变量名，不应写入真实值。
- 如果仓库改为公开，请先检查历史提交、日志和工作流是否包含个人邮箱或其他隐私信息。

## License

当前为个人私有项目，未单独授予开源许可。
