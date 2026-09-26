@echo off
rem Public https link to the GrievEye dashboards (Cloudflare quick tunnel, no account needed).
rem Start bot.py first, then double-click this file. Keep this window open while you demo.
rem The address is printed below (https://....trycloudflare.com) and changes on every start.
rem bot.py finds it automatically for /mydashboard links (restart not needed).

rem Only one tunnel can run: stop an old one (for example this file started twice).
taskkill /IM cloudflared.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
"%LOCALAPPDATA%\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000 --metrics 127.0.0.1:4041 --no-autoupdate
pause
