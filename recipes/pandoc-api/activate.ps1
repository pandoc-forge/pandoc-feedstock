# pandoc-api (pandoc-forge): pandoc 3.14 and later search the directories in
# PANDOC_DATA_DIRS for data files, so a Lua filter installed in this
# environment's share/pandoc/filters is found by name (pandoc -L <name>.lua).
# Older pandoc ignores the variable. Add share/pandoc first, unless it's
# already listed.
$_pandocApiDir = Join-Path $Env:CONDA_PREFIX (Join-Path "share" "pandoc")
$_pandocApiSep = [IO.Path]::PathSeparator
if ([string]::IsNullOrEmpty($Env:PANDOC_DATA_DIRS)) {
    $Env:PANDOC_DATA_DIRS = $_pandocApiDir
} elseif ($Env:PANDOC_DATA_DIRS.Split($_pandocApiSep) -notcontains $_pandocApiDir) {
    $Env:PANDOC_DATA_DIRS = $_pandocApiDir + $_pandocApiSep + $Env:PANDOC_DATA_DIRS
}
Remove-Variable _pandocApiDir, _pandocApiSep
