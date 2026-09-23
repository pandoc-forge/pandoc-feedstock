#!/usr/bin/env bash
# Build pandoc.wasm from the pandoc source tree in $1 and stage it in $2:
#
#   $2/pandoc.wasm
#   $2/COPYING.md, $2/COPYRIGHT
#
# Uses the GHC wasm toolchain (ghc-wasm-meta) at the revision pinned in
# pandoc's own flake.lock, so each pandoc release is built with the toolchain
# upstream used for it. Installs the toolchain to $GHC_WASM_PREFIX
# (default ~/.ghc-wasm) unless it is already there. The Hackage snapshot
# comes from $INDEX_STATE (see pins.env).
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)

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
# Pin the Hackage snapshot used for dependency resolution.
if [[ -n ${INDEX_STATE:-} ]]; then
	echo "index-state: $INDEX_STATE" >cabal.project.local
fi
make pandoc.wasm

cp pandoc.wasm COPYING.md COPYRIGHT "$out/"
ls -l "$out/pandoc.wasm"
# Smoke test. Node comes with the ghc-wasm-meta toolchain sourced above.
echo "Smoke test with node $(node --version)..."
run=(node --no-warnings "$here/run-wasm.mjs" "$out/pandoc.wasm")
cd "$(mktemp -d)"
"${run[@]}" --version
echo '# Hello' | "${run[@]}" -t html | grep -q '<h1 id="hello">Hello</h1>'
# `--version` reports -lua for upstream's pandoc.wasm too, but Lua filters work.
echo 'function Str(e) return pandoc.Str(e.text:upper()) end' >upper.lua
echo hello | "${run[@]}" -L upper.lua -t plain | grep -q HELLO
