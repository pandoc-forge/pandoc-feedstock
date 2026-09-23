# shellcheck shell=bash disable=SC2034,SC2154
# Sourced by the build scripts, with $src set to the pandoc source tree: sets
# the cabal and GHC options for building pandoc, and $exe. pandoc-crossref is
# built with the same options, so that it reuses the pandoc library.
CABALOPTS="-fembed_data_files -fserver -flua ${CABALOPTS:-}"
# Older pandoc versions (e.g. 3.6.3) have no http flag and always support HTTP.
if grep -q '^flag http' "$src/pandoc.cabal"; then
	CABALOPTS="-fhttp $CABALOPTS"
fi
GHCOPTS=${GHCOPTS:-}

exe=
case "$(uname -s)" in
MINGW* | MSYS* | CYGWIN*) exe=.exe ;;
esac
