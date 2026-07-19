@echo off
REM Sharecoin (SHC) - instant solo mining starter for kawpowminer.
REM Drop this file into the same folder as kawpowminer.exe and run it.
REM (Don't have kawpowminer yet? See this repo's README.md "Mining" section
REM for where to get it.)
REM
REM Rewards go to YOUR OWN wallet address below - not anyone else's.
REM Each miner who uses their own address gets credit for the blocks they
REM personally find.

if not exist "%~dp0kawpowminer.exe" (
    echo kawpowminer.exe not found in this folder.
    echo Download it and place it next to this .bat file - see this
    echo repo's README.md "Mining" section for where to get it.
    pause
    exit /b 1
)

set /p WALLET="Enter your Sharecoin wallet address (starts with m or n): "
if "%WALLET%"=="" (
    echo No address entered - exiting.
    pause
    exit /b 1
)

set /p WORKERNAME="Enter a worker name (anything, e.g. rig1) [rig1]: "
if "%WORKERNAME%"=="" set WORKERNAME=rig1

echo.
echo Connecting to stormforge.tail0b8084.ts.net:10000 as %WALLET%.%WORKERNAME%
echo.

"%~dp0kawpowminer.exe" -P stratum+tcp://%WALLET%.%WORKERNAME%@stormforge.tail0b8084.ts.net:10000 --cu-grid-size 1 --cu-streams 1 --display-interval 2

pause
