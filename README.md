# pandoc-feedstock

Builds [pandoc](https://pandoc.org) from source for the `pandoc-forge` conda channel on prefix.dev. The channel is meant to be a drop-in replacement for conda-forge's pandoc.

| Package | Platforms | Contents |
|---|---|---|
| `pandoc` | linux-64, linux-aarch64, osx-64, osx-arm64, win-64 | `pandoc` (plus `pandoc-lua` and `pandoc-server` symlinks on Unix) and its man pages. Statically linked on Linux, with data files embedded and `+lua +server +http` |
| `pandoc-wasm` | noarch | `share/pandoc-wasm/pandoc.wasm`, a WASI module |
| `pandoc-crossref` | same as `pandoc` | `pandoc-crossref`, statically linked against the same pandoc library as the `pandoc` binary, and pinned to that exact pandoc (`pandoc ==3.12 *pandoc_forge*`). Build strings name the pandoc version, e.g. `pandoc3_12_pandoc_forge_0` |
| `pandoc-api` | noarch | Nothing. Its version is the pandoc API version (pandoc-types major.minor, e.g. `1.23`) |

## pandoc-crossref

pandoc-crossref is built right after pandoc in the same job, by `scripts/build-crossref.sh`. It freezes pandoc's cabal plan, adds pandoc-crossref (the `CROSSREF_TAG` in `pins.env`) to pandoc's own cabal project, and builds it with the same options. So it links exactly the pandoc library that is in the `pandoc` binary, and only pandoc-crossref and its few extra dependencies get compiled. That means using pandoc's GHC and Hackage snapshot rather than upstream pandoc-crossref's GHC and freeze file.

pandoc-crossref's own test suites (`test-pandoc-crossref` and `test-integrative`, with the flaky tests enabled as in upstream's CI) run in the same job against that pandoc library, and a failure fails the build.

When no pandoc-crossref tag admits a new pandoc yet, `CROSSREF_TAG` stays at the newest tag, and CI applies our patches in `patches/pandoc-crossref/<tag>/`, which relax its `pandoc` bounds. Such a build is released only if crossref's test suites all pass against the new pandoc. If a test fails only because pandoc's output changed (not because of a crossref bug), list it in `patches/pandoc-crossref/<tag>/skip-pandoc-<pandoc version>.txt` with the reason, and it is skipped for that pandoc only. Once upstream tags a release that admits the new pandoc, switch `CROSSREF_TAG` to it and drop the patches.

pandoc-crossref warns whenever it runs through a pandoc other than the one it was compiled with, and its test checks that there is no such warning. A pandoc-crossref failure doesn't stop pandoc being packaged. Releases include pandoc-crossref only if it built on all five platforms.

## pandoc-api

This works like conda-forge's `python_abi`. Each `pandoc` and `pandoc-wasm` depends on the `pandoc-api` version it speaks, and `pandoc-api` only allows pandoc-forge builds of pandoc (`run_constraints: pandoc * *pandoc_forge*`). `pandoc-api` also constrains `pandoc-wasm` the same way. An environment therefore has one pandoc API, which all its engines speak and all its filters target. A JSON filter depends on `pandoc` and `pandoc-api 1.23.*`, and gets a pandoc-forge pandoc whose JSON AST it can read. A Lua filter runs on either engine, so it depends on `pandoc-api 1.23.*` only, and the environment chooses the engine. If a higher-priority channel supplies pandoc instead, the solve fails rather than mixing builds.

CI reads the version from the `pandoc-types` bound in the tag's `pandoc.cabal` (`scripts/pandoc-api-version.sh`), so no one maintains the mapping. Every branch builds the same `pandoc-api`, and uploads skip the copies that already exist.

## Install

```sh
pixi add --channel https://prefix.dev/pandoc-forge --channel conda-forge pandoc
# or
conda install -c https://prefix.dev/pandoc-forge -c conda-forge pandoc
```

Pre-release and test builds go to `https://prefix.dev/pandoc-forge/dev`.

`pandoc-forge` builds have build strings matching `*pandoc_forge*`. To require them over conda-forge's, use the spec `pandoc * *pandoc_forge*`.

## How it builds

`pins.env` holds everything that determines a build: the jgm/pandoc tag (`PANDOC_VERSION`), the Hackage snapshot (`INDEX_STATE`, upstream's release time for that tag), the exact GHC and cabal versions, and the Linux build image's tag for that GHC. The tag is rebuilt from time to time (Alpine updates, same GHC), and quay stops serving the old digest at once, so it isn't pinned by digest; CI logs the digest it used. `.github/workflows/build.yml` ports upstream's release builds to GitHub Actions:

| Target | Runner | Method (as upstream) |
|---|---|---|
| linux-64, linux-aarch64 | `ubuntu-24.04`, `ubuntu-24.04-arm` | static musl build in `quay.io/benz0li/ghc-musl:<GHC_VERSION>` |
| osx-64, osx-arm64 | `macos-15-intel`, `macos-15` | GHC 9.10 + cabal |
| win-64 | `windows-2022` | GHC 9.10 + cabal |
| wasm | `ubuntu-24.04` | `make pandoc.wasm` with ghc-wasm-meta, pinned by pandoc's `flake.lock` |

`scripts/build-native.sh` and `scripts/build-wasm.sh` build and stage binaries into `dist/`. The rattler-build recipes in `recipes/` then package what is in `dist/`.

## Publishing

- Pushes to `main` upload whatever built to `pandoc-forge/dev`.
- Releases to `pandoc-forge` are manual: run the workflow from `main` or a `v*` branch with `channel: pandoc-forge`. It uploads only if every platform built. The upload job runs in the `release` GitHub environment, which is limited to `main` and `v*`.

## Older pandoc versions

`main` builds the latest pandoc. Each older version that downstream packages pin (for example quarto's exact `pandoc 3.8.3`) lives on a `v<major>.<minor>.x` branch, which differs from `main` only in `pins.env` (including its build numbers). Changes to the build are made on `main` and merged into the branches.

## Publishing details

- Uploads try prefix.dev trusted publishing first and fall back to the `PREFIX_API_KEY` secret. They never overwrite: a fix to a published version needs a new build number (`*_BUILD_NUMBER` in `pins.env`).
- The target channels default to `pandoc-forge/dev` and `pandoc-forge` (the `pandoc-forge` group's primary channel). The repo variables `PREFIX_DEV_CHANNEL` and `PREFIX_RELEASE_CHANNEL` override them.

## Updating

### Bumping to a new pandoc release

What changed upstream decides the work, so this list is a starting point, not a complete procedure. Start from the release notes and the diff since the previous tag: <https://github.com/jgm/pandoc/releases/latest>, and `git diff <old>..<new> -- pandoc.cabal cabal.project flake.lock Makefile .circleci .github/workflows wasm` in a jgm/pandoc clone.

1. **Keep the previous version buildable.** If a downstream package pins it exactly (e.g. quarto on conda-forge), or it is the newest pandoc with an unpatched pandoc-crossref, branch `v<old>.x` from `main` first.
2. **`pins.env` on `main`:**
   - `PANDOC_VERSION`: the new tag.
   - `INDEX_STATE`: the GitHub release's `publishedAt` (`gh release view <tag> -R jgm/pandoc --json publishedAt`).
   - `GHC_VERSION`, `CABAL_VERSION`: what upstream's release builds use (`.circleci/config.yml`, `.github/workflows/release-candidate.yml`).
   - `GHC_MUSL_IMAGE`: `quay.io/benz0li/ghc-musl:<GHC_VERSION>`, the tag for exactly that GHC.
   - `CROSSREF_TAG`: the newest tag whose `pandoc` bounds admit the new version. If none does yet, keep the newest tag and add `patches/pandoc-crossref/<tag>/*.patch` relaxing its bounds (`pandoc-crossref.cabal` and `package.yaml`). crossref's test suites decide whether it ships.
   - Reset `PANDOC_BUILD_NUMBER`, `PANDOC_WASM_BUILD_NUMBER` and `CROSSREF_BUILD_NUMBER` to 0.
3. **Things in the upstream diff to look at:**
   - the `pandoc-types` bound in `pandoc.cabal`: a new major.minor means a new `pandoc-api` version, and filters need rebuilding against it;
   - cabal flags (`embed_data_files`, `http`, `lua`, `server`) and their defaults: `scripts/cabal-opts.sh` sets them explicitly;
   - `cabal.project`, especially the `wasm32` section and its `source-repository-package` forks;
   - `flake.lock`: its ghc-wasm-meta revision is the wasm toolchain;
   - build tools needed at configure time (`alex`, `happy`), installed by the wasm job;
   - new Lua API marked `Since: <new version>` in `doc/lua-filters.md`, for filters' minimum versions.
4. **Try it locally** where it's cheap: the Linux build in the ghc-musl container (`build-native.sh`, then `build-crossref.sh`) shows most problems in about 20 minutes.
5. **Open a PR.** PR runs build and test everything on every platform without uploading. On a PR, a job fails if pandoc-crossref didn't build, pass its tests and package (on pushes it doesn't, so that pandoc still uploads).
6. **Merge**, which uploads to `pandoc-forge/dev`. Check it from there: `pandoc --version`, `pandoc` + `pandoc-crossref` (no version warning), a Lua filter such as `pandoc-amsthm`, and that `quarto` still resolves to the pandoc it pins.
7. **Release:** Actions → Build → Run workflow on `main` → `channel: pandoc-forge`.

### Other updates

- **Packaging change for an already-published version:** on that version's branch, bump the affected `*_BUILD_NUMBER` in `pins.env`.
- **New pandoc-crossref release:** on each branch whose pandoc the new tag's `pandoc` bounds admit, set `CROSSREF_TAG`, delete `patches/pandoc-crossref/<old tag>/`, and reset `CROSSREF_BUILD_NUMBER` to 0. Its pandoc packages already exist and are skipped on upload.
- **Build changes** go on `main` and are then merged into each `v*` branch. `pins.env` is the only file that differs, so a merge conflict can only be there: keep the branch's values.

### Automation

`.github/workflows/bump.yml` runs `scripts/bot.py` daily, and it opens a PR for each of the updates above that is mechanical:

- **A new pandoc release** (on `main`): `PANDOC_VERSION`, `INDEX_STATE`, GHC and the image from upstream's CircleCI config, `CROSSREF_TAG` or a generated bounds patch, and build numbers reset. The PR body lists what in upstream's diff needs a look: GHC, the pandoc API, flags and `cabal.project`, the wasm toolchain, and new Lua API. It's labelled `needs-review`, `pandoc-api` or `crossref-patched` when that applies. Steps 1 and 5–7 of the checklist stay manual.
- **A newer pandoc-crossref tag** admitting a branch's pandoc.

A `bot/…` branch that already exists is never pushed again, so closing a PR declines that update. Run it by hand with Actions → Bump → Run workflow (`dry-run` prints the changes instead), or locally with `python3 scripts/bot.py --dry-run [branch...]`.

It opens PRs as the **pandoc-forge-bot** GitHub App, because PRs opened with `GITHUB_TOKEN` don't trigger `build.yml`. To set it up (once, as an org owner):

1. Org settings → Developer settings → GitHub Apps → New: name `pandoc-forge-bot`, no webhook, repository permissions *Contents*, *Pull requests* and *Issues*: read and write. Only on this account.
2. Install it on `pandoc-forge/pandoc-feedstock` only.
3. Generate a private key. In this repo, add the variable `BOT_CLIENT_ID` (the App's client ID) and the secret `BOT_PRIVATE_KEY` (the `.pem` contents).

Until `BOT_CLIENT_ID` is set, the workflow skips itself.
