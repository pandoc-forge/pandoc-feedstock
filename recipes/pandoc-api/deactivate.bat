@REM pandoc-api (pandoc-forge): take this environment's share\pandoc back out of
@REM PANDOC_DATA_DIRS (see activate.bat), and unset the variable if that leaves
@REM it empty. Unlike deactivate.sh, this removes every occurrence.
@if not defined PANDOC_DATA_DIRS goto :eof
@set "_PANDOC_API_DIR=%CONDA_PREFIX%\share\pandoc"
@set "_PANDOC_API_DIRS=;%PANDOC_DATA_DIRS%;"
@call set "_PANDOC_API_DIRS=%%_PANDOC_API_DIRS:;%_PANDOC_API_DIR%;=;%%"
@REM Without the outer ; (an empty value unsets the variable)
@set "PANDOC_DATA_DIRS=%_PANDOC_API_DIRS:~1,-1%"
@set "_PANDOC_API_DIR="
@set "_PANDOC_API_DIRS="
