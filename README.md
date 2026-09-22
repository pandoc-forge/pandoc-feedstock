# pandoc-feedstock

Builds [pandoc](https://pandoc.org) from source for the `pandoc-forge` conda channel on prefix.dev. The channel is meant to be a drop-in replacement for conda-forge's pandoc.

| Package | Platforms | Contents |
|---|---|---|
| `pandoc` | linux-64, linux-aarch64, osx-64, osx-arm64, win-64 | `pandoc` (plus `pandoc-lua` and `pandoc-server` symlinks on Unix) and its man pages. Statically linked on Linux, with data files embedded and `+lua +server +http` |
| `pandoc-wasm` | noarch | `share/pandoc-wasm/pandoc.wasm`, a WASI module |

## Install

```sh
pixi add --channel https://prefix.dev/pandoc-forge --channel conda-forge pandoc
# or
conda install -c https://prefix.dev/pandoc-forge -c conda-forge pandoc
```

Pre-release and test builds go to `https://prefix.dev/pandoc-forge-dev`.

`pandoc-forge` builds have build strings matching `*pandoc_forge*`. To require them over conda-forge's, use the spec `pandoc * *pandoc_forge*`.

## How it builds

`PANDOC_VERSION` names the jgm/pandoc tag to build. `.github/workflows/build.yml` ports upstream's release builds to GitHub Actions:

| Target | Runner | Method (as upstream) |
|---|---|---|
| linux-64, linux-aarch64 | `ubuntu-24.04`, `ubuntu-24.04-arm` | static musl build in `quay.io/benz0li/ghc-musl:9.10` |
| osx-64, osx-arm64 | `macos-15-intel`, `macos-15` | GHC 9.10 + cabal |
| win-64 | `windows-2022` | GHC 9.10 + cabal |
| wasm | `ubuntu-24.04` | `make pandoc.wasm` with ghc-wasm-meta, pinned by pandoc's `flake.lock` |

`scripts/build-native.sh` and `scripts/build-wasm.sh` build and stage binaries into `dist/`. The rattler-build recipes in `recipes/` then package what is in `dist/`.

## Publishing

- Pushes to `main` upload whatever built to `pandoc-forge-dev`.
- Releases to `pandoc-forge` are manual: run the workflow from `main` with `channel: pandoc-forge`. It uploads only if every platform built. The upload job runs in the `release` GitHub environment, which is limited to `main`, and prefix.dev only accepts uploads to `pandoc-forge` from that environment.
- Uploads use prefix.dev trusted publishing (no API keys) and never overwrite: a fix to a published version needs a new `build_number`.

## Updating

- **New pandoc release:** update `PANDOC_VERSION`, and reset `build_number` to 0 in both recipes.
- **Packaging change for the same pandoc version:** bump `build_number` instead.
