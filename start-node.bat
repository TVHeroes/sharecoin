@echo off
REM Starts a Sharecoin regtest node using the prebuilt Windows binaries in
REM wallet\ - no WSL/Linux required. Uses its own datadir (separate from
REM whatever wallet\start-wallet.bat connects to), so this is meant for
REM running your own node/network - see README.md's "Running your own
REM network" section for the Stratum proxy needed to actually let GPU
REM miners connect to it.
REM
REM Change RPCUSER/RPCPASSWORD below before using this for real - the
REM placeholder password is not secret.

set DATADIR=%~dp0node-data
set P2PPORT=19610
set RPCPORT=19710
set RPCUSER=sharecoin
set RPCPASSWORD=CHANGE_ME

if not exist "%DATADIR%" mkdir "%DATADIR%"

"%~dp0wallet\sharecoin-cli.exe" -regtest -datadir="%DATADIR%" -rpcport=%RPCPORT% -rpcuser=%RPCUSER% -rpcpassword=%RPCPASSWORD% getblockcount >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Node already running.
    goto :end
)

echo Starting sharecoind...
start "Sharecoin node" "%~dp0wallet\sharecoind.exe" -regtest -datadir="%DATADIR%" -printtoconsole=0 -port=%P2PPORT% -rpcport=%RPCPORT% -rpcuser=%RPCUSER% -rpcpassword=%RPCPASSWORD% -rpcbind=127.0.0.1 -rpcallowip=127.0.0.1 -wallet=w -fallbackfee=0.0001

echo Waiting for RPC...
ping -n 6 127.0.0.1 >nul

:end
"%~dp0wallet\sharecoin-cli.exe" -regtest -datadir="%DATADIR%" -rpcport=%RPCPORT% -rpcuser=%RPCUSER% -rpcpassword=%RPCPASSWORD% getblockcount
pause
