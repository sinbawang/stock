@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

set "PYTHON_BIN=%ROOT_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=python"

if /I "%~1"=="help" goto :usage
if /I "%~1"=="/?" goto :usage
if /I "%~1"=="checkxq" goto :checkxq

pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\refresh_holdings_publish_to_cloudbase.py" --latest-only %*
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
echo   %~n0 --symbols 000591 000651 --skip-build --skip-upload --parallelism 2
echo     Validate two symbols only, without rebuilding the publish bundle or uploading.
echo.
echo Diagnostics:
echo   %~n0 checkxq
exit /b 0