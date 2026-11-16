# pandoc-api (pandoc-forge): pandoc 3.14 and later search the directories in
# PANDOC_DATA_DIRS for data files, so a Lua filter installed in this
# environment's share/pandoc/filters is found by name (pandoc -L <name>.lua).
# Older pandoc ignores the variable. Add share/pandoc first, unless it's
# already listed.
_pandoc_api_dir="${CONDA_PREFIX}/share/pandoc"
case ":${PANDOC_DATA_DIRS-}:" in
    *":${_pandoc_api_dir}:"*) ;;
    *) export PANDOC_DATA_DIRS="${_pandoc_api_dir}${PANDOC_DATA_DIRS:+:${PANDOC_DATA_DIRS}}" ;;
esac
unset _pandoc_api_dir
