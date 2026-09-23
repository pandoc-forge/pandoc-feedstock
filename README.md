# pandoc-feedstock

Builds [pandoc](https://pandoc.org) from source for the `pandoc-forge` conda channel on prefix.dev. The channel is meant to be a drop-in replacement for conda-forge's pandoc.

| Package | Platforms | Contents |
|---|---|---|
| `pandoc` | linux-64, linux-aarch64, osx-64, osx-arm64, win-64 | `pandoc` (plus `pandoc-lua` and `pandoc-server` symlinks on Unix) and its man pages. Statically linked on Linux, with data files embedded and `+lua +server +http` |
| `pandoc-wasm` | noarch | `share/pandoc-wasm/pandoc.wasm`, a WASI module |
| `pandoc-crossref` | same as `pandoc` | `pandoc-crossref`, statically linked against the same pandoc library as the `pandoc` binary, and pinned to that exact pandoc (`pandoc ==3.11 *pandoc_forge*`). Build strings name the pandoc version, e.g. `pandoc3_11_pandoc_forge_0` |
| `pandoc-api` | noarch | Nothing. Its version is the pandoc API version (pandoc-types major.minor, e.g. `1.23`) |

## pandoc-crossref

pandoc-crossref is built right after pandoc in the same job, by `scripts/build-crossref.sh`. It freezes pandoc's cabal plan, adds pandoc-crossref (the `CROSSREF_TAG` in `pins.env`) to pandoc's own cabal project, and builds it with the same options. So it links exactly the pandoc library that is in the `pandoc` binary, and only pandoc-crossref and its few extra dependencies get compiled. That means using pandoc's GHC and Hackage snapshot rather than upstream pandoc-crossref's GHC and freeze file.

pandoc-crossref warns whenever it runs through a pandoc other than the one it was compiled with, and its test checks that there is no such warning. A pandoc-crossref failure doesn't stop pandoc being packaged. Releases include pandoc-crossref only if it built on all five platforms.

## pandoc-api

This works like conda-forge's `python_abi`. Each `pandoc` depends on the `pandoc-api` version it speaks, and `pandoc-api` only allows pandoc-forge builds of pandoc (`run_constraints: pandoc * *pandoc_forge*`). A filter that depends on `pandoc` and `pandoc-api 1.23.*` therefore gets a pandoc-forge pandoc whose JSON AST it can read. If a higher-priority channel supplies pandoc instead, the solve fails rather than mixing builds.

CI reads the version from the `pandoc-types` bound in the tag's `pandoc.cabal` (`scripts/pandoc-api-version.sh`), so no one maintains the mapping. Every branch builds the same `pandoc-api`, and uploads skip the copies that already exist.

## Install

```sh
pixi add --channel https://prefix.dev/ickc/pandoc-forge --channel conda-forge pandoc
# or
conda install -c https://prefix.dev/ickc/pandoc-forge -c conda-forge pandoc
```

Pre-release and test builds go to `https://prefix.dev/ickc/pandoc-forge-dev`.

`pandoc-forge` builds have build strings matching `*pandoc_forge*`. To require them over conda-forge's, use the spec `pandoc * *pandoc_forge*`.

## How it builds

`pins.env` holds everything that determines a build: the jgm/pandoc tag (`PANDOC_VERSION`), the Hackage snapshot (`INDEX_STATE`, upstream's release time for that tag), the exact GHC and cabal versions, and the Linux build image by digest. `.github/workflows/build.yml` ports upstream's release builds to GitHub Actions:

| Target | Runner | Method (as upstream) |
|---|---|---|
| linux-64, linux-aarch64 | `ubuntu-24.04`, `ubuntu-24.04-arm` | static musl build in `quay.io/benz0li/ghc-musl:9.10` |
| osx-64, osx-arm64 | `macos-15-intel`, `macos-15` | GHC 9.10 + cabal |
| win-64 | `windows-2022` | GHC 9.10 + cabal |
| wasm | `ubuntu-24.04` | `make pandoc.wasm` with ghc-wasm-meta, pinned by pandoc's `flake.lock` |

`scripts/build-native.sh` and `scripts/build-wasm.sh` build and stage binaries into `dist/`. The rattler-build recipes in `recipes/` then package what is in `dist/`.

## Publishing

- Pushes to `main` upload whatever built to `pandoc-forge-dev`.
- Releases to `pandoc-forge` are manual: run the workflow from `main` or a `v*` branch with `channel: pandoc-forge`. It uploads only if every platform built. The upload job runs in the `release` GitHub environment, which is limited to `main` and `v*`.

## Older pandoc versions

`main` builds the latest pandoc. Each older version that downstream packages pin (for example quarto's exact `pandoc 3.8.3`) lives on a `v<major>.<minor>.x` branch, which differs from `main` only in `pins.env`. Changes to the build are made on `main` and merged into the branches.

## Publishing details

- Uploads try prefix.dev trusted publishing first and fall back to the `PREFIX_API_KEY` secret. They never overwrite: a fix to a published version needs a new `build_number`.
- The target channels default to `ickc/pandoc-forge-dev` and `ickc/pandoc-forge`. The repo variables `PREFIX_DEV_CHANNEL` and `PREFIX_RELEASE_CHANNEL` override them.

## Updating

- **New pandoc release:** update `pins.env` (version, index-state, and toolchain if upstream changed it), and reset `build_number` to 0 in the `pandoc` and `pandoc-wasm` recipes.
- **Packaging change for the same pandoc version:** bump `build_number` instead.
- **New pandoc-crossref release:** on each branch whose pandoc the new tag's `pandoc` bounds admit, set `CROSSREF_TAG` in `pins.env` and reset `build_number` in `recipes/pandoc-crossref` to 0. Its pandoc packages already exist and are skipped on upload.
