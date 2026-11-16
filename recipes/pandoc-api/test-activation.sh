# Checks activate.sh and deactivate.sh, run in pandoc-api's (activated) test
# environment.
set -eu
d="$CONDA_PREFIX/share/pandoc"
act="$CONDA_PREFIX/etc/conda/activate.d/pandoc-api_activate.sh"
deact="$CONDA_PREFIX/etc/conda/deactivate.d/pandoc-api_deactivate.sh"
check() {
    if [ "$2" != "$3" ]; then
        echo "$1: expected '$3', got '$2'" >&2
        exit 1
    fi
}

check "activated" "${PANDOC_DATA_DIRS-unset}" "$d"
. "$act"
check "activated twice" "$PANDOC_DATA_DIRS" "$d"
. "$deact"
check "deactivated" "${PANDOC_DATA_DIRS-unset}" unset
PANDOC_DATA_DIRS=/a:/b
. "$act"
check "added before the user's" "$PANDOC_DATA_DIRS" "$d:/a:/b"
. "$deact"
check "user's kept" "$PANDOC_DATA_DIRS" /a:/b
PANDOC_DATA_DIRS="/a:$d:/b:$d"
. "$deact"
check "first occurrence removed" "$PANDOC_DATA_DIRS" "/a:/b:$d"
echo "activation scripts: OK"
