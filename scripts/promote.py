#!/usr/bin/env python3
"""Fetch the dev channel's packages that a release promotes.

A release doesn't rebuild. It copies to the release channel the exact files
in the dev channel that this branch's pins.env names, which are the ones
checked there. This finds them in the dev channel's sharded repodata
(CEP 16), which prefix.dev updates within seconds of an upload, so a
release can follow the push build at once (repodata.json lags by up to
30 minutes):

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
copy. It needs Python 3.14's compression.zstd or the zstd command:

Usage: promote.py [--dev CHANNEL] [--release CHANNEL] OUT
       (defaults: pandoc-forge/dev, pandoc-forge)
"""

import argparse
import hashlib
import re
import struct
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
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


def unzstd(data):
    try:
        from compression import zstd  # Python 3.14
    except ImportError:
        return subprocess.run(["zstd", "-dcq"], input=data, check=True,
                              capture_output=True).stdout
    return zstd.decompress(data)


# msgpack type bytes: a fixed-width number, or a length of this width
MSGPACK_NUM = {0xca: ">f", 0xcb: ">d", 0xcc: ">B", 0xcd: ">H", 0xce: ">I",
               0xcf: ">Q", 0xd0: ">b", 0xd1: ">h", 0xd2: ">i", 0xd3: ">q"}
MSGPACK_LEN = {0xc4: ("bin", ">B"), 0xc5: ("bin", ">H"), 0xc6: ("bin", ">I"),
               0xd9: ("str", ">B"), 0xda: ("str", ">H"), 0xdb: ("str", ">I"),
               0xdc: ("array", ">H"), 0xdd: ("array", ">I"),
               0xde: ("map", ">H"), 0xdf: ("map", ">I")}


def unmsgpack(b):
    """Decode msgpack without extension types, which is all sharded repodata
    uses. The standard library has no decoder."""
    def item(i):
        t, i = b[i], i + 1
        if t < 0x80 or t >= 0xe0:  # fixint
            return t - 0x100 if t >= 0xe0 else t, i
        if t in (0xc0, 0xc2, 0xc3):
            return {0xc0: None, 0xc2: False, 0xc3: True}[t], i
        if t in MSGPACK_NUM:
            fmt = MSGPACK_NUM[t]
            return struct.unpack_from(fmt, b, i)[0], i + struct.calcsize(fmt)
        if t < 0x90:
            kind, n = "map", t & 0x0f
        elif t < 0xa0:
            kind, n = "array", t & 0x0f
        elif t < 0xc0:
            kind, n = "str", t & 0x1f
        elif t in MSGPACK_LEN:
            kind, fmt = MSGPACK_LEN[t]
            n, i = struct.unpack_from(fmt, b, i)[0], i + struct.calcsize(fmt)
        else:
            raise ValueError(f"msgpack type {t:#x} at byte {i - 1}")
        if kind in ("str", "bin"):
            return b[i:i + n].decode() if kind == "str" else b[i:i + n], i + n
        out = []
        for _ in range(2 * n if kind == "map" else n):
            x, i = item(i)
            out.append(x)
        return dict(zip(out[::2], out[1::2])) if kind == "map" else out, i
    return item(0)[0]


def repodata(channel, subdir, names):
    """The records of the packages NAMES in CHANNEL/SUBDIR, by filename."""
    url = f"{SERVER}/{channel}/{subdir}/"
    try:
        index = unmsgpack(unzstd(get(url + "repodata_shards.msgpack.zst")))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    base = urllib.parse.urljoin(url, index["info"]["shards_base_url"])
    records = {}
    for name in sorted(names & index["shards"].keys()):
        shard = unmsgpack(unzstd(get(f"{base}{index['shards'][name].hex()}.msgpack.zst")))
        records |= shard.get("packages", {}) | shard.get("packages.conda", {})
    return records


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

    targets = wanted()
    names = {t[0] for t in targets}
    index = {s: repodata(a.dev, s, names) for s in NATIVE + ["noarch"]}
    picked, missing = [], []
    for name, version, build, subdirs, required in targets:
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
        sys.exit(f"not in {a.dev} (has the push build uploaded them?): "
                 + "; ".join(missing))

    released = {}
    for subdir, fn, record in picked:
        if subdir not in released:
            released[subdir] = repodata(a.release, subdir, names)
        if fn in released[subdir]:
            print(f"{subdir}/{fn}: already in {a.release}", file=sys.stderr)
            continue
        data = get(f"{SERVER}/{a.dev}/{subdir}/{fn}")
        if hashlib.sha256(data).digest() != record["sha256"]:
            sys.exit(f"{subdir}/{fn}: sha256 differs from {a.dev}'s repodata")
        path = a.out / subdir / fn
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(path)


if __name__ == "__main__":
    main()
