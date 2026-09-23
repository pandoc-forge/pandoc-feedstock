#!/usr/bin/env bash
# Print the pandoc API version (pandoc-types major.minor, e.g. 1.23) of the
# pandoc source tree in $1, read from the pandoc-types bound in pandoc.cabal.
# JSON filters are compatible when this matches, so it versions pandoc-api.
set -euo pipefail

cabal=${1:?usage: pandoc-api-version.sh PANDOC_SRC}/pandoc.cabal

# e.g. "pandoc-types >= 1.23.1.2 && < 1.24,"
bound=$(grep -m1 -E '^[[:space:],]*pandoc-types[[:space:]]*>=' "$cabal")
if [[ ! $bound =~ \>=[[:space:]]*([0-9]+)\.([0-9]+)[0-9.]*[[:space:]]*\&\&[[:space:]]*\<[[:space:]]*([0-9]+)\.([0-9]+) ]]; then
	echo "cannot parse pandoc-types bound in $cabal: $bound" >&2
	exit 1
fi
major=${BASH_REMATCH[1]} minor=${BASH_REMATCH[2]}
# The bound must span exactly one API version, e.g. >= 1.23.x && < 1.24.
if [[ ${BASH_REMATCH[3]}.${BASH_REMATCH[4]} != "$major.$((minor + 1))" ]]; then
	echo "pandoc-types bound spans more than one API version: $bound" >&2
	exit 1
fi
echo "$major.$minor"
