@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "PYTHON_BIN=%ROOT_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=python"

set "INSTALL_HINT=%PYTHON_BIN% -m pip install --pre -r requirements.txt"

if /I "%~1"=="help" goto :usage
if /I "%~1"=="/?" goto :usage
if /I "%~1"=="checkxq" goto :checkxq

call :ensure_runtime_deps pandas numpy pydantic matplotlib mplfinance typer requests akshare browser_cookie3 pypdf
if errorlevel 1 exit /b 1

pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\refresh_holdings_publish_to_cloudbase.py" --latest-only %*
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

exit /b %EXIT_CODE%

:checkxq
call :ensure_runtime_deps requests browser_cookie3
if errorlevel 1 exit /b 1
pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\diagnose_xueqiu_cookie.py"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%

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
echo   - parallelism defaults to min(4, CPU count)
echo.
echo Common examples:
echo   %~n0
echo     Regenerate holdings, rebuild latest publish bundle, and upload.
echo.
echo   %~n0 --parallelism 4
echo     Same as above, but generate holdings in parallel with 4 workers.
echo.
echo   %~n0 --no-skip-gen-base --parallelism 4
echo     Force regenerate fundamental base reports before rebuilding/uploading.
echo.
echo   %~n0 --pending-reverse-mode tail_mixed --skip-build --skip-upload
echo     Regenerate reports with a custom pending reverse rule, without rebuilding or uploading.
echo.
echo   %~n0 --day-bars 1000 --skip-build --skip-upload
echo     Regenerate reports using a 1000-bar daily K-line fetch window.
echo.
echo   %~n0 --m60-bars 800 --m15-bars 1200 --skip-build --skip-upload
echo     Regenerate reports using custom 60M and 15M fetch windows.
echo.
echo   %~n0 --symbols 000591 000651 --skip-build --skip-upload --parallelism 2
echo     Validate two symbols only, without rebuilding the publish bundle or uploading.
echo.
echo Diagnostics:
echo   %~n0 checkxq
exit /b 0