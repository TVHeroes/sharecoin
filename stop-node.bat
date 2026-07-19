@echo off
REM Stops the node started by start-node.bat.
set DATADIR=%~dp0node-data
set RPCPORT=19710
set RPCUSER=sharecoin
set RPCPASSWORD=CHANGE_ME

"%~dp0wallet\sharecoin-cli.exe" -regtest -datadir="%DATADIR%" -rpcport=%RPCPORT% -rpcuser=%RPCUSER% -rpcpassword=%RPCPASSWORD% stop
pause
