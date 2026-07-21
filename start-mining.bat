@echo off
REM Sharecoin (SHC) - instant solo mining starter for kawpowminer.
REM Drop this file into the same folder as kawpowminer.exe and run it.
REM (Don't have kawpowminer yet? See this repo's README.md "Mining" section
REM for where to get it.)
REM
REM Rewards go to YOUR OWN wallet address below - not anyone else's.
REM Each miner who uses their own address gets credit for the blocks they
REM personally find.
REM
REM To skip the prompts below and start instantly every time, fill in
REM both values here (leave either one blank to keep the interactive
REM prompts instead):
set WALLET_ADDRESS=
set WORKER_NAME=

set "KAWPOWMINER=%~dp0kawpowminer.exe"
if not exist "%KAWPOWMINER%" set "KAWPOWMINER=%~dp0kawpowminer-windows-1.2.4\kawpowminer.exe"
if not exist "%KAWPOWMINER%" (
    echo kawpowminer.exe not found in this folder or kawpowminer-windows-1.2.4\.
    echo Download it and place it next to this .bat file - see this
    echo repo's README.md "Mining" section for where to get it.
    pause
    exit /b 1
)

if not "%WALLET_ADDRESS%"=="" if not "%WORKER_NAME%"=="" (
    set "WALLET=%WALLET_ADDRESS%"
    set "WORKERNAME=%WORKER_NAME%"
    goto :start
)

set /p WALLET="Enter your Sharecoin wallet address (starts with m or n): "
if "%WALLET%"=="" (
    echo No address entered - exiting.
    pause
    exit /b 1
)

set /p WORKERNAME="Enter a worker name (anything, e.g. rig1) [rig1]: "
if "%WORKERNAME%"=="" set WORKERNAME=rig1

:start
echo.
echo Connecting to sharecoin.duckdns.org:10000 as %WALLET%.%WORKERNAME%
echo.

"%KAWPOWMINER%" -P stratum+tcp://%WALLET%.%WORKERNAME%@sharecoin.duckdns.org:10000 --cu-grid-size 1 --cu-streams 1 --display-interval 2

pause
