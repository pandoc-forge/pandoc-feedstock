# pandoc-api (pandoc-forge): take this environment's share/pandoc back out of
# PANDOC_DATA_DIRS (see activate.ps1), and remove the variable if that leaves
# it empty.
if (-not [string]::IsNullOrEmpty($Env:PANDOC_DATA_DIRS)) {
    $_pandocApiDir = Join-Path $Env:CONDA_PREFIX (Join-Path "share" "pandoc")
    $_pandocApiSep = [IO.Path]::PathSeparator
    $_pandocApiDirs = [Collections.Generic.List[string]]$Env:PANDOC_DATA_DIRS.Split($_pandocApiSep)
    # Removes the first occurrence only
    if ($_pandocApiDirs.Remove($_pandocApiDir)) {
        if ($_pandocApiDirs.Count -gt 0) {
            $Env:PANDOC_DATA_DIRS = $_pandocApiDirs -join $_pandocApiSep
        } else {
            Remove-Item Env:PANDOC_DATA_DIRS
        }
    }
    Remove-Variable _pandocApiDir, _pandocApiSep, _pandocApiDirs
}
