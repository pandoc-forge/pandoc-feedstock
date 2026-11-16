@REM pandoc-api (pandoc-forge): pandoc 3.14 and later search the directories in
@REM PANDOC_DATA_DIRS for data files, so a Lua filter installed in this
@REM environment's share\pandoc\filters is found by name (pandoc -L <name>.lua).
@REM Older pandoc ignores the variable. Add share\pandoc first, unless it's
@REM already listed.
@set "_PANDOC_API_DIR=%CONDA_PREFIX%\share\pandoc"
@set "_PANDOC_API_DIRS=;%PANDOC_DATA_DIRS%;"
@REM The list without ;<dir>; (case-insensitive): unchanged if it isn't there
@call set "_PANDOC_API_REST=%%_PANDOC_API_DIRS:;%_PANDOC_API_DIR%;=%%"
@if "%_PANDOC_API_REST%"=="%_PANDOC_API_DIRS%" (
    if defined PANDOC_DATA_DIRS (
        set "PANDOC_DATA_DIRS=%_PANDOC_API_DIR%;%PANDOC_DATA_DIRS%"
    ) else (
        set "PANDOC_DATA_DIRS=%_PANDOC_API_DIR%"
    )
)
@set "_PANDOC_API_DIR="
@set "_PANDOC_API_DIRS="
@set "_PANDOC_API_REST="
