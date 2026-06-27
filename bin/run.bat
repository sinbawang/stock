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

set "PYTHON_BIN=%ROOT_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=python"

set "INSTALL_HINT=%PYTHON_BIN% -m pip install --pre -r requirements.txt"
set "RUN_PROFILE_ARGS="

if /I "%~1"=="help" goto :usage
if /I "%~1"=="/?" goto :usage
if /I "%~1"=="checkxq" goto :checkxq
if /I "%~1"=="intraday" (
	set "RUN_PROFILE_ARGS=--skip-gen-base --skip-gen-fund --tech-timeframes 5m --publish-timeframes 30m 5m day"
	shift
)

set "RUN_FORWARD_ARGS="
:collect_forward_args
if "%~1"=="" goto after_collect_forward_args
set "RUN_FORWARD_ARGS=!RUN_FORWARD_ARGS! "%~1""
shift
goto collect_forward_args
:after_collect_forward_args

call :ensure_runtime_deps pandas numpy pydantic matplotlib mplfinance typer requests akshare browser_cookie3 pypdf
if errorlevel 1 (
	set "EXIT_CODE=1"
	goto :exit_with_elapsed
)

pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\refresh_holdings_publish_to_cloudbase.py" --latest-only %RUN_PROFILE_ARGS% !RUN_FORWARD_ARGS!
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

goto :exit_with_elapsed

:checkxq
call :ensure_runtime_deps requests browser_cookie3
if errorlevel 1 (
	set "EXIT_CODE=1"
	goto :exit_with_elapsed
)
pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\diagnose_xueqiu_cookie.py"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
goto :exit_with_elapsed

:ensure_runtime_deps
setlocal EnableExtensions
set "MODULE_LIST=%*"
pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" -c "import importlib.util, sys; missing = [name for name in sys.argv[1:] if importlib.util.find_spec(name) is None]; sys.exit(0 if not missing else 1)" %*
set "CHECK_EXIT=%ERRORLEVEL%"
popd >nul
if not "%CHECK_EXIT%"=="0" (
	echo Missing Python dependencies for %~n0.
	echo Required modules: %MODULE_LIST%
	echo.
	echo Install them with:
	echo   %INSTALL_HINT%
	exit /b 1
)
endlocal & exit /b 0

:usage
echo Usage: %~n0 [refresh_holdings_publish_to_cloudbase args]
echo.
echo Default behavior:
echo   - Always forwards --latest-only to refresh_holdings_publish_to_cloudbase.py
echo   - skipGenBase defaults to true, but base.json will still refresh automatically when a newer report period is detected
echo   - day-bars now defaults to 600
echo   - mixed report generation already covers 30M and embeds 5M precision, so the default extra tech-timeframes are day 60m 15m
echo   - parallelism defaults to min(4, CPU count)
echo   - special profile: %~n0 intraday = only regenerate 30M main analysis + standalone 5M chart layer, and publish 30M/5M/day charts
echo.
echo Recommended templates:
echo   Daily publish:
echo     %~n0 --skip-gen-base --skip-gen-fund --parallelism 4
echo.
echo   Intraday refresh (30M + standalone 5M only):
echo     %~n0 intraday --parallelism 4
echo.
echo   Validation without upload:
echo     %~n0 intraday --skip-upload --parallelism 4
echo.
echo More explicit examples:
echo   %~n0 --no-skip-gen-base --parallelism 4
echo     Force regenerate fundamental base reports before rebuilding/uploading.
echo.
echo   %~n0 --skip-gen-base --skip-gen-fund --tech-timeframes day 5m --parallelism 4
echo     Keep day charts plus the standalone 5M chart layer, while skipping 60M and 15M extra chart generation.
echo.
echo   %~n0 --pending-reverse-mode tail_mixed --skip-build --skip-upload
echo     Regenerate reports with a custom pending reverse rule, without rebuilding or uploading.
echo.
echo   %~n0 --zhongshu-level segment --skip-build --skip-upload
echo     Regenerate reports and draw segment zhongshu instead of bi zhongshu.
echo.
echo   %~n0 --symbols 000591 000651 --skip-build --skip-upload --parallelism 2
echo     Validate two symbols only, without rebuilding the publish bundle or uploading.
echo.
echo Diagnostics:
echo   %~n0 checkxq
set "EXIT_CODE=0"
goto :exit_with_elapsed

:exit_with_elapsed
if not defined EXIT_CODE set "EXIT_CODE=0"
for /f %%I in ('powershell -NoProfile -Command "$start=[int64]$env:RUN_START_MS; $elapsed=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()-$start; [TimeSpan]::FromMilliseconds($elapsed).ToString(\"hh\:mm\:ss\.fff\")"') do set "RUN_ELAPSED=%%I"
echo Total elapsed time: %RUN_ELAPSED%
exit /b %EXIT_CODE%