@echo off
REM Launches the Sharecoin wallet GUI, connected to the live public node
REM over Tailscale Funnel (see this repo's README for what that means and
REM how to reach it without installing Tailscale yourself, if applicable).
REM -prune=550 keeps this wallet's disk footprint small by discarding old
REM block data once it's been validated - fine for a normal wallet (balance/
REM send/receive), but means this copy can't serve deep-history queries
REM (getrandombeacon over an old block range) or rescan from a birth date
REM older than the retained window. Run without -prune if you need either.
if not exist "%~dp0datadir" mkdir "%~dp0datadir"
"%~dp0sharecoin-qt.exe" -regtest -datadir="%~dp0datadir" -connect=stormforge.tail0b8084.ts.net:8443 -prune=550
