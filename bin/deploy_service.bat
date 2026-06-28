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

set "PYTHON_BIN=%ROOT_DIR%\venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" set "PYTHON_BIN=python"

if /I "%~1"=="help" goto :usage
if /I "%~1"=="/?" goto :usage

pushd "%ROOT_DIR%" >nul
"%PYTHON_BIN%" "%ROOT_DIR%\scripts\deploy_tencent_container_service.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

exit /b %EXIT_CODE%

:usage
echo Usage: %~n0 [deploy_tencent_container_service args]
echo.
echo Required before first deploy:
echo   1. npm i -g @cloudbase/cli
echo   2. tcb login   ^(or tcb login --key^)
echo   3. Create the CloudBase Run service once in console, for example: chanlun-stock-service
echo.
echo Example:
echo   %~n0 --env-id your-env-id --service-name chanlun-stock-service --api-key your-cloudbase-api-key
echo.
echo Dry run:
echo   %~n0 --env-id your-env-id --service-name chanlun-stock-service --dry-run
exit /b 0