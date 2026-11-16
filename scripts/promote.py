#!/usr/bin/env python3
"""Fetch the dev channel's packages that a release promotes.

A release doesn't rebuild. It copies to the release channel the exact files
in the dev channel that this branch's pins.env names, which are the ones
checked there. This finds them in the dev channel's repodata:

  pandoc           every platform, required
  pandoc-wasm      noarch, required from pandoc 3.9 on (no wasm upstream before)
  pandoc-api       noarch, required
  pandoc-crossref  every platform, or left out with a warning (as a release
                   has always done when it didn't build everywhere)

Files the release channel already has are left out: it never changes a
published file. It downloads the others into OUT/<subdir>/, checks each
against the sha256 in the dev repodata, and prints them, one per line.
Checking where they were built, and the upload, are the workflow's. It only
reads public URLs, so it can run anywhere, e.g. to see what a release would
copy:

Usage: promote.py [--dev CHANNEL] [--release CHANNEL] OUT
       (defaults: pandoc-forge/dev, pandoc-forge)
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

SERVER = "https://prefix.dev"
NATIVE = ["linux-64", "linux-aarch64", "osx-64", "osx-arm64", "win-64"]
PANDOC_REPO = "jgm/pandoc"
CROSSREF_REPO = "lierdakil/pandoc-crossref"


def get(url):
    # prefix.dev's package host refuses Python's default User-Agent (403)
    req = urllib.request.Request(url, headers={"User-Agent": "pandoc-forge-promote"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def raw(repo, tag, path):
    return get(f"https://raw.githubusercontent.com/{repo}/{tag}/{path}").decode()


def ver(s):
    return tuple(int(x) for x in s.split("."))


def repodata(channel, subdir):
    try:
        d = json.loads(get(f"{SERVER}/{channel}/{subdir}/repodata.json"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    return {**d.get("packages", {}), **d.get("packages.conda", {})}


def wanted():
    """(name, version, build string, subdirs, required) from pins.env, the
    pandoc-api recipe, and upstream's files at the pinned tags."""
    pins = dict(re.findall(r"^([A-Z_]+)=(.*)$", Path("pins.env").read_text(), re.M))
    pandoc = pins["PANDOC_VERSION"]
    with tempfile.TemporaryDirectory() as src:
        Path(src, "pandoc.cabal").write_text(raw(PANDOC_REPO, pandoc, "pandoc.cabal"))
        api = subprocess.run(["bash", "scripts/pandoc-api-version.sh", src],
                             check=True, text=True, capture_output=True).stdout.strip()
    api_build = re.search(r"^\s*build_number:\s*(\d+)",
                          Path("recipes/pandoc-api/recipe.yaml").read_text(), re.M)[1]
    crossref = re.search(r"^version:\s*(\S+)",
                         raw(CROSSREF_REPO, pins["CROSSREF_TAG"], "pandoc-crossref.cabal"),
                         re.M | re.I)[1]
    return [
        ("pandoc", pandoc, f"pandoc_forge_{pins['PANDOC_BUILD_NUMBER']}", NATIVE, True),
        *([("pandoc-wasm", pandoc, f"pandoc_forge_{pins['PANDOC_WASM_BUILD_NUMBER']}",
            ["noarch"], True)] if ver(pandoc) >= (3, 9) else []),
        ("pandoc-api", api, f"pandoc_forge_{api_build}", ["noarch"], True),
        ("pandoc-crossref", crossref,
         f"pandoc{pandoc.replace('.', '_')}_pandoc_forge_{pins['CROSSREF_BUILD_NUMBER']}",
         NATIVE, False),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dev", default="pandoc-forge/dev")
    ap.add_argument("--release", default="pandoc-forge")
    ap.add_argument("out", type=Path)
    a = ap.parse_args()

    index = {s: repodata(a.dev, s) for s in NATIVE + ["noarch"]}
    picked, missing = [], []
    for name, version, build, subdirs, required in wanted():
        found, absent = [], []
        for s in subdirs:
            hits = [(fn, r) for fn, r in index[s].items() if
                    (r["name"], r["version"], r["build"]) == (name, version, build)]
            (found if hits else absent).append((s, *hits[0]) if hits else s)
        spec = f"{name} {version} {build}"
        if not absent:
            picked += found
        elif required:
            missing.append(f"{spec} ({', '.join(absent)})")
        else:
            print(f"::warning::{spec} is missing on {', '.join(absent)}; "
                  f"releasing without {name}", file=sys.stderr)
    if missing:
        sys.exit(f"not in {a.dev} (yet? repodata.json can lag an upload "
                 "by up to 30 min): " + "; ".join(missing))

    released = {}
    for subdir, fn, record in picked:
        if subdir not in released:
            released[subdir] = repodata(a.release, subdir)
        if fn in released[subdir]:
            print(f"{subdir}/{fn}: already in {a.release}", file=sys.stderr)
            continue
        data = get(f"{SERVER}/{a.dev}/{subdir}/{fn}")
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            sys.exit(f"{subdir}/{fn}: sha256 differs from {a.dev}'s repodata")
        path = a.out / subdir / fn
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(path)


if __name__ == "__main__":
    main()
