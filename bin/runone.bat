@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

if not defined RUN_WITH_LOG (
    set "LOG_DIR=%ROOT_DIR%\build\logs"
    if not exist "!LOG_DIR!" mkdir "!LOG_DIR!" >nul 2>&1
    for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_LOG_STAMP=%%I"
    set "LOG_FILE=!LOG_DIR!\%~n0_!RUN_LOG_STAMP!.log"
    echo Writing log to: !LOG_FILE!
    set "RUN_WITH_LOG=1"
    "%ComSpec%" /d /s /c ""%~f0" %*" > "!LOG_FILE!" 2>&1
    set "EXIT_CODE=!ERRORLEVEL!"
    type "!LOG_FILE!"
    echo Log saved to: !LOG_FILE!
    if not "!EXIT_CODE!"=="0" (
        echo Command failed with exit code !EXIT_CODE!.
        pause
    )
    exit /b !EXIT_CODE!
)

for /f %%I in ('powershell -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()"') do set "RUN_START_MS=%%I"

if "%~1"=="" goto :usage

set "PYTHON_BIN=%ROOT_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=python"

set "RUNONE_PROFILE_ARGS="

if /I "%~1"=="checkxq" goto :checkxq

if /I "%~1"=="intraday" (
    set "RUNONE_PROFILE_ARGS=--skip-gen-base --skip-gen-fund --tech-timeframes 5m --publish-timeframes 30m 5m day"
    shift
)

if "%~1"=="" goto :usage

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
    goto :exit_with_elapsed
)

"%PYTHON_BIN%" "%ROOT_DIR%\scripts\refresh_holdings_publish_to_cloudbase.py" --symbols "%SYMBOL%" --latest-only %RUNONE_PROFILE_ARGS% !RUNONE_FORWARD_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

goto :exit_with_elapsed

:checkxq
pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\diagnose_xueqiu_cookie.py"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
goto :exit_with_elapsed

:usage
echo Usage: %~n0 [intraday] SYMBOL [NAME] [CN^|HK] [extra refresh_holdings_publish_to_cloudbase args]
echo Recommended templates:
echo   Daily single-symbol publish:
echo     %~n0 09988 "阿里巴巴" HK --skip-gen-base --skip-gen-fund --parallelism 1
echo.
echo   Intraday single-symbol refresh (30M + standalone 5M only):
echo     %~n0 intraday 00700 HK --parallelism 1
echo.
echo   Single-symbol validation without upload:
echo     %~n0 intraday 00700 HK --skip-upload --parallelism 1
echo.
echo More explicit examples:
echo   %~n0 000591 --skip-gen-base --skip-gen-fund --tech-timeframes day 5m --parallelism 1
echo   %~n0 000591 --pending-reverse-mode tail_mixed --skip-build --skip-upload
echo   %~n0 000591 --zhongshu-level segment --skip-build --skip-upload
echo   %~n0 000591 --day-bars 600 --skip-build --skip-upload
echo   %~n0 000591 --m60-bars 800 --m5-bars 800 --skip-build --skip-upload
echo Profile: %~n0 intraday = only regenerate 30M main analysis + standalone 5M chart layer, and publish 30M/5M/day charts
echo Diagnostic: %~n0 checkxq
set "EXIT_CODE=1"
goto :exit_with_elapsed

:exit_with_elapsed
if not defined EXIT_CODE set "EXIT_CODE=0"
for /f %%I in ('powershell -NoProfile -Command "$start=[int64]$env:RUN_START_MS; $elapsed=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()-$start; [TimeSpan]::FromMilliseconds($elapsed).ToString(\"hh\:mm\:ss\.fff\")"') do set "RUN_ELAPSED=%%I"
echo Total elapsed time: !RUN_ELAPSED!
exit /b %EXIT_CODE%