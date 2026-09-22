#!/usr/bin/env bash
# Build pandoc-cli from the pandoc source tree in $1 and stage the result in $2:
#
#   $2/bin/pandoc[.exe]
#   $2/share/man/man1/*.1
#   $2/COPYING.md, $2/COPYRIGHT
#
# Mirrors jgm/pandoc's release builds (linux/make_artifacts.sh,
# macos/make_macos_release.sh, .github/workflows/release-candidate.yml).
# Extra cabal and GHC options come from $CABALOPTS and $GHCOPTS, and the
# Hackage snapshot from $INDEX_STATE (see pins.env).
set -euo pipefail

src=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)

CABALOPTS="-fembed_data_files -fserver -flua -fhttp ${CABALOPTS:-}"
GHCOPTS=${GHCOPTS:-}

exe=
case "$(uname -s)" in
MINGW* | MSYS* | CYGWIN*) exe=.exe ;;
esac

cd "$src"
# Pin the Hackage snapshot used for dependency resolution.
if [[ -n ${INDEX_STATE:-} ]]; then
	echo "index-state: $INDEX_STATE" >cabal.project.local
fi
cabal update
# shellcheck disable=SC2086
cabal build $CABALOPTS --ghc-options="$GHCOPTS" pandoc-cli
# shellcheck disable=SC2086
binpath=$(cabal list-bin $CABALOPTS --ghc-options="$GHCOPTS" pandoc-cli)
echo "Built executable: $binpath"

mkdir -p "$out/bin" "$out/share/man/man1"
cp "$binpath" "$out/bin/pandoc$exe"
# upstream does not strip the Windows release binary either
[[ -z $exe ]] && strip "$out/bin/pandoc"
cp pandoc-cli/man/pandoc.1 pandoc-cli/man/pandoc-lua.1 pandoc-cli/man/pandoc-server.1 "$out/share/man/man1/"
cp COPYING.md COPYRIGHT "$out/"

pandoc="$out/bin/pandoc$exe"
"$pandoc" --version
echo "Checking for +server +lua..."
"$pandoc" --version | grep -q '+server +lua'
echo "Checking that data files are embedded..."
echo hello | "$pandoc" -s --metadata title=t -t html | grep -q '<title>t</title>'
if [[ $(uname -s) == Linux ]]; then
	echo "Checking that the binary is statically linked..."
	file "$pandoc" | grep -q 'statically linked'
fi
