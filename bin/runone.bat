@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%~1"=="" goto :usage

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "PYTHON_BIN=%ROOT_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=python"

if /I "%~1"=="checkxq" goto :checkxq

set "HOLDINGS_FILE=%ROOT_DIR%\data\stock_holdings.json"
set "SYMBOL=%~1"
shift

set "RUNONE_STOCK_NAME="
set "RUNONE_MARKET="

if not "%~1"=="" (
    set "RUNONE_NEXT_ARG=%~1"
    if /I not "!RUNONE_NEXT_ARG!"=="CN" if /I not "!RUNONE_NEXT_ARG!"=="HK" if not "!RUNONE_NEXT_ARG:~0,1!"=="-" (
        set "RUNONE_STOCK_NAME=%~1"
        shift
    )
)

if /I "%~1"=="CN" (
    set "RUNONE_MARKET=CN"
    shift
) else if /I "%~1"=="HK" (
    set "RUNONE_MARKET=HK"
    shift
)

set "RUNONE_FORWARD_ARGS="
:collect_forward_args
if "%~1"=="" goto after_collect_forward_args
set "RUNONE_FORWARD_ARGS=!RUNONE_FORWARD_ARGS! "%~1""
shift
goto collect_forward_args
:after_collect_forward_args

pushd "%ROOT_DIR%" >nul
if not "%RUNONE_STOCK_NAME%"=="" (
    if not "%RUNONE_MARKET%"=="" (
        "%PYTHON_BIN%" "%ROOT_DIR%\scripts\ensure_holding_in_watchlist.py" "%SYMBOL%" --holdings-file "%HOLDINGS_FILE%" --name "%RUNONE_STOCK_NAME%" --market %RUNONE_MARKET%
    ) else (
        "%PYTHON_BIN%" "%ROOT_DIR%\scripts\ensure_holding_in_watchlist.py" "%SYMBOL%" --holdings-file "%HOLDINGS_FILE%" --name "%RUNONE_STOCK_NAME%"
    )
) else (
    if not "%RUNONE_MARKET%"=="" (
        "%PYTHON_BIN%" "%ROOT_DIR%\scripts\ensure_holding_in_watchlist.py" "%SYMBOL%" --holdings-file "%HOLDINGS_FILE%" --market %RUNONE_MARKET%
    ) else (
        "%PYTHON_BIN%" "%ROOT_DIR%\scripts\ensure_holding_in_watchlist.py" "%SYMBOL%" --holdings-file "%HOLDINGS_FILE%"
    )
)
if errorlevel 1 (
    set "EXIT_CODE=%ERRORLEVEL%"
    popd >nul
    exit /b %EXIT_CODE%
)

"%PYTHON_BIN%" "%ROOT_DIR%\scripts\refresh_holdings_publish_to_cloudbase.py" --symbols "%SYMBOL%" --latest-only !RUNONE_FORWARD_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

exit /b %EXIT_CODE%

:checkxq
pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\diagnose_xueqiu_cookie.py"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%

:usage
echo Usage: %~n0 SYMBOL [NAME] [CN^|HK] [extra refresh_holdings_publish_to_cloudbase args]
echo Example: %~n0 09988 "阿里巴巴" HK
echo Example: %~n0 000591 --pending-reverse-mode tail_mixed --skip-build --skip-upload
echo Example: %~n0 000591 --day-bars 1000 --skip-build --skip-upload
echo Example: %~n0 000591 --m60-bars 800 --m15-bars 1200 --skip-build --skip-upload
echo Diagnostic: %~n0 checkxq
exit /b 1