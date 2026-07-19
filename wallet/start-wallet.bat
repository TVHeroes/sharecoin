@echo off
REM Launches the Sharecoin wallet GUI, connected to the live public node
REM over Tailscale Funnel (see this repo's README for what that means and
REM how to reach it without installing Tailscale yourself, if applicable).
"%~dp0sharecoin-qt.exe" -regtest -datadir="%~dp0datadir" -connect=stormforge.tail0b8084.ts.net:8443
