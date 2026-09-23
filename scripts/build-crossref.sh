#!/usr/bin/env bash
# Build pandoc-crossref from the source tree in $2 against the pandoc source
# tree in $1, which scripts/build-native.sh has already built, and stage it in
# $3:
#
#   $3/bin/pandoc-crossref[.exe]
#   $3/LICENSE
#
# pandoc-crossref is added to pandoc's own cabal project, with pandoc's build
# plan frozen first. It therefore links the very pandoc library (same
# dependencies, flags and GHC) that is in the pandoc binary we ship, and only
# pandoc-crossref and its few extra dependencies get compiled. Takes the same
# $CABALOPTS and $GHCOPTS as build-native.sh; they must match for the pandoc
# library to be reused.
set -euo pipefail

src=$(cd "$1" && pwd)
xsrc=$(cd "$2" && pwd)
mkdir -p "$3"
out=$(cd "$3" && pwd)

# shellcheck source=scripts/cabal-opts.sh
. "$(dirname "$0")/cabal-opts.sh"

cd "$src"
# Freeze pandoc's plan so that adding pandoc-crossref to the project cannot
# change pandoc's dependency versions.
# shellcheck disable=SC2086
cabal freeze $CABALOPTS --ghc-options="$GHCOPTS"
# cabal on Windows needs a Windows path, not Git Bash's /d/...
xpath=$xsrc
if command -v cygpath >/dev/null; then
	xpath=$(cygpath -m "$xsrc")
fi
echo "packages: $xpath" >>cabal.project.local
# shellcheck disable=SC2086
cabal build $CABALOPTS --ghc-options="$GHCOPTS" pandoc-crossref:exe:pandoc-crossref
# shellcheck disable=SC2086
binpath=$(cabal list-bin $CABALOPTS --ghc-options="$GHCOPTS" pandoc-crossref:exe:pandoc-crossref)
echo "Built executable: $binpath"

mkdir -p "$out/bin"
cp "$binpath" "$out/bin/pandoc-crossref$exe"
[[ -z $exe ]] && strip "$out/bin/pandoc-crossref"
cp "$xsrc/LICENSE" "$out/"

crossref="$out/bin/pandoc-crossref$exe"
"$crossref" --version
if [[ $(uname -s) == Linux ]]; then
	echo "Checking that the binary is statically linked..."
	file "$crossref" | grep -q 'statically linked'
fi
