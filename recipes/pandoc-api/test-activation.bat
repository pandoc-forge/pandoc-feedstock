@echo off
REM Checks activate.bat and deactivate.bat, run in pandoc-api's (activated)
REM test environment on Windows.
setlocal
set "D=%CONDA_PREFIX%\share\pandoc"
set "ACT=%CONDA_PREFIX%\etc\conda\activate.d\pandoc-api_activate.bat"
set "DEACT=%CONDA_PREFIX%\etc\conda\deactivate.d\pandoc-api_deactivate.bat"

if not "%PANDOC_DATA_DIRS%"=="%D%" (echo activated: got "%PANDOC_DATA_DIRS%" & exit /b 1)
call "%ACT%"
if not "%PANDOC_DATA_DIRS%"=="%D%" (echo activated twice: got "%PANDOC_DATA_DIRS%" & exit /b 1)
call "%DEACT%"
if defined PANDOC_DATA_DIRS (echo deactivated: got "%PANDOC_DATA_DIRS%" & exit /b 1)
set "PANDOC_DATA_DIRS=C:\a;C:\b"
call "%ACT%"
if not "%PANDOC_DATA_DIRS%"=="%D%;C:\a;C:\b" (echo added before the user's: got "%PANDOC_DATA_DIRS%" & exit /b 1)
call "%DEACT%"
if not "%PANDOC_DATA_DIRS%"=="C:\a;C:\b" (echo user's kept: got "%PANDOC_DATA_DIRS%" & exit /b 1)
set "PANDOC_DATA_DIRS=C:\a;%D%;C:\b"
call "%DEACT%"
if not "%PANDOC_DATA_DIRS%"=="C:\a;C:\b" (echo removed from the middle: got "%PANDOC_DATA_DIRS%" & exit /b 1)
if defined _PANDOC_API_DIRS (echo helper variables left & exit /b 1)
echo activation scripts (bat): OK
