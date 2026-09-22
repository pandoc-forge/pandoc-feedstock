#!/usr/bin/env bash
# Build pandoc.wasm from the pandoc source tree in $1 and stage it in $2:
#
#   $2/pandoc.wasm
#   $2/COPYING.md, $2/COPYRIGHT
#
# Uses the GHC wasm toolchain (ghc-wasm-meta) at the revision pinned in
# pandoc's own flake.lock, so each pandoc release is built with the toolchain
# upstream used for it. Installs the toolchain to $GHC_WASM_PREFIX
# (default ~/.ghc-wasm) unless it is already there.
set -euo pipefail

src=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)
prefix=${GHC_WASM_PREFIX:-$HOME/.ghc-wasm}

rev=$(jq -r '.nodes["ghc-wasm-meta"].locked.rev' "$src/flake.lock")
echo "ghc-wasm-meta revision (from pandoc's flake.lock): $rev"

if [[ $(cat "$prefix/.ghc-wasm-meta-rev" 2>/dev/null) != "$rev" ]]; then
	tmp=$(mktemp -d)
	curl -fL --retry 5 "https://gitlab.haskell.org/haskell-wasm/ghc-wasm-meta/-/archive/$rev/ghc-wasm-meta-$rev.tar.gz" |
		tar xz --strip-components=1 -C "$tmp"
	# setup.sh wipes $PREFIX, so keep the cabal store (which may come from
	# the CI cache) out of its way.
	[[ -d $prefix/.cabal ]] && mv "$prefix/.cabal" "$tmp/.cabal-keep"
	(cd "$tmp" && PREFIX="$prefix" ./setup.sh)
	[[ -d $tmp/.cabal-keep ]] && mv "$tmp/.cabal-keep" "$prefix/.cabal"
	echo "$rev" >"$prefix/.ghc-wasm-meta-rev"
	rm -rf "$tmp"
fi

# shellcheck disable=SC1091
source "$prefix/env"
cd "$src"
make pandoc.wasm

cp pandoc.wasm COPYING.md COPYRIGHT "$out/"
ls -l "$out/pandoc.wasm"
if command -v wasmtime >/dev/null; then
	echo "Smoke test with wasmtime..."
	wasmtime run "$out/pandoc.wasm" --version
	echo '# Hello' | wasmtime run "$out/pandoc.wasm" -t html | grep -q '<h1 id="hello">Hello</h1>'
else
	echo "wasmtime not found; skipping smoke test"
fi
