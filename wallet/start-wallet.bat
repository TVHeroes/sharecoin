@echo off
REM Launches the Sharecoin wallet GUI, connected to the live public node
REM via a router port-forward and dynamic DNS (sharecoin.duckdns.org) -
REM see this repo's README for details.
REM -prune=550 keeps this wallet's disk footprint small by discarding old
REM block data once it's been validated - fine for a normal wallet (balance/
REM send/receive), but means this copy can't serve deep-history queries
REM (getrandombeacon over an old block range) or rescan from a birth date
REM older than the retained window. Run without -prune if you need either.
REM -fallbackfee=0.0001 (~10 sat/vB) - this chain is too young/low-traffic
REM for Bitcoin Core's automatic fee estimator to have real data yet, and
REM the estimator has no fallback by default in modern Bitcoin Core (it's
REM disabled for safety on mainnet). Without this, sending fails outright
REM with "Fee estimation failed."
if not exist "%~dp0datadir" mkdir "%~dp0datadir"
"%~dp0sharecoin-qt.exe" -regtest -datadir="%~dp0datadir" -connect=sharecoin.duckdns.org:8443 -prune=550 -fallbackfee=0.0001
