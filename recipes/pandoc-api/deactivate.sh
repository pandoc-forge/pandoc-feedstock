# pandoc-api (pandoc-forge): take this environment's share/pandoc back out of
# PANDOC_DATA_DIRS (see activate.sh), and unset the variable if that leaves
# it empty.
_pandoc_api_dir="${CONDA_PREFIX}/share/pandoc"
case ":${PANDOC_DATA_DIRS-}:" in
    *":${_pandoc_api_dir}:"*)
        # What comes before and after its first occurrence
        _pandoc_api_dirs=":${PANDOC_DATA_DIRS}:"
        _pandoc_api_dirs="${_pandoc_api_dirs%%:"${_pandoc_api_dir}":*}:${_pandoc_api_dirs#*:"${_pandoc_api_dir}":}"
        _pandoc_api_dirs="${_pandoc_api_dirs#:}"
        _pandoc_api_dirs="${_pandoc_api_dirs%:}"
        if [ -n "${_pandoc_api_dirs}" ]; then
            export PANDOC_DATA_DIRS="${_pandoc_api_dirs}"
        else
            unset PANDOC_DATA_DIRS
        fi
        unset _pandoc_api_dirs
        ;;
esac
unset _pandoc_api_dir
