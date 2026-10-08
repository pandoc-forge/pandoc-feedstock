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
#
# pandoc-crossref's own test suites then run against that pandoc library, with
# the flaky tests enabled as in upstream's CI, and must all pass: a failure
# fails the build, so the package is neither built nor released. This matters
# most when CROSSREF_TAG is patched to admit a newer pandoc than upstream does
# (patches/pandoc-crossref/<tag>/, applied by CI). Tests known to fail against
# this pandoc only because pandoc's output changed are listed, with the
# reason, in patches/pandoc-crossref/$CROSSREF_TAG/skip-pandoc-$PANDOC_VERSION.txt
# and skipped.
set -euo pipefail

skips=$(cd "$(dirname "$0")/.." && pwd)/patches/pandoc-crossref/${CROSSREF_TAG:?}/skip-pandoc-${PANDOC_VERSION:?}.txt

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
cat >>cabal.project.local <<EOF
packages: $xpath

package pandoc-crossref
  tests: True
  flags: +enable_flaky_tests
EOF
# shellcheck disable=SC2086
cabal build $CABALOPTS --ghc-options="$GHCOPTS" pandoc-crossref:exe:pandoc-crossref
testopts=()
if [[ -f $skips ]]; then
	while IFS= read -r path; do
		path=${path%$'\r'} # Git for Windows may check the file out with CRLF
		[[ -z $path || $path == '#'* ]] && continue
		echo "Skipping known failure: $path"
		testopts+=(--test-option=--skip "--test-option=$path")
	done <"$skips"
fi
# shellcheck disable=SC2086
cabal test $CABALOPTS --ghc-options="$GHCOPTS" --test-show-details=direct ${testopts[@]+"${testopts[@]}"} pandoc-crossref
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
