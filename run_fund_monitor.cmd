@echo off
set RUN_ONCE=1
set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" "C:\Users\Administrator\IdeaProjects\finance\fund_monitor.py"
exit /b %errorlevel%
