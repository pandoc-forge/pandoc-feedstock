#!/usr/bin/env python3
"""Propose pins.env updates as pull requests (run daily by bump.yml).

Three checks, each of which edits the checked-out branch and, if anything
changed, pushes it as bot/<...> and opens a PR against that branch:

  pandoc    (main only) a new jgm/pandoc release: PANDOC_VERSION, INDEX_STATE,
            the ghc-musl image and GHC upstream builds with, CROSSREF_TAG (or a
            bounds patch), build numbers reset; the PR body lists what in
            upstream's diff needs a human look.
  image     the pinned ghc-musl digest no longer exists on quay (benz0li
            rebuilds tags, and quay deletes the old manifest): repin to the
            current digest of the tag GHC_VERSION, i.e. the same GHC.
  crossref  a newer pandoc-crossref tag admits the branch's pandoc: switch to
            it, drop our patches for the old tag.

A bot branch that already exists on the remote is never touched again, so a
closed PR stays closed. Merging and releasing stay manual.

Usage: bot.py [--dry-run] [BRANCH...]   (default: main and every origin/v*)
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

PANDOC_REPO = "jgm/pandoc"
CROSSREF_REPO = "lierdakil/pandoc-crossref"
IMAGE_REPO = "benz0li/ghc-musl"
PINS = Path("pins.env")
# The only paths the bot changes, stages or resets
OWNED = ["pins.env", "patches"]
MANIFEST_TYPES = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
])
# Files of an upstream release whose changes can need work here
# (README: Bumping to a new pandoc release).
WATCH = ["pandoc.cabal", "cabal.project", "flake.lock", "Makefile",
         ".circleci", ".github/workflows", "wasm"]


def run(*cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, text=True,
                          capture_output=True).stdout.strip()


def http(url, headers=None, method="GET"):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""


def gh_json(*args):
    return json.loads(run("gh", *args))


def ver(s):
    return tuple(int(x) for x in s.split("."))


# --- pins.env -----------------------------------------------------------

def read_pins():
    return dict(re.findall(r"^([A-Z_]+)=(.*)$", PINS.read_text(), re.M))


def set_pin(key, value, comment=None, marker=None):
    """Set KEY=value. With `marker`, the one-line comment just above that
    starts with "# <marker>" (if any) describes this value: replace it with
    `comment`, or drop it when `comment` is None."""
    lines = PINS.read_text().splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(key + "="))
    lines[i] = f"{key}={value}"
    if marker is not None:
        mine = lines[i - 1].startswith("# " + marker)
        if mine:
            del lines[i - 1]
        if comment is not None:
            lines.insert(i - 1 if mine else i, "# " + comment)
    PINS.write_text("\n".join(lines) + "\n")


# --- ghc-musl on quay ----------------------------------------------------

def digest_exists(image):
    repo, digest = image.split("@")
    path = repo.removeprefix("quay.io/")
    status, _ = http(f"https://quay.io/v2/{path}/manifests/{digest}",
                     {"Accept": MANIFEST_TYPES}, "HEAD")
    return status == 200


def tag_digest(tag):
    _, body = http(f"https://quay.io/api/v1/repository/{IMAGE_REPO}/tag/"
                   f"?specificTag={tag}&onlyActiveTags=true")
    tags = json.loads(body)["tags"] if body else []
    return tags[0]["manifest_digest"] if tags else None


def set_image(ghc):
    """Pin the current digest of the ghc-musl tag for exactly GHC `ghc`."""
    digest = tag_digest(ghc)
    if not digest:
        raise SystemExit(f"no ghc-musl tag {ghc} on quay")
    set_pin("GHC_MUSL_IMAGE", f"quay.io/{IMAGE_REPO}@{digest}",
            f"quay.io/{IMAGE_REPO}:{ghc}, pinned by digest (GHC {ghc})",
            marker="quay.io/")


# --- pandoc-crossref -----------------------------------------------------

def crossref_releases():
    """Non-pre-release tags, newest first."""
    rel = gh_json("release", "list", "-R", CROSSREF_REPO, "-L", "30",
                  "--exclude-pre-releases", "--json", "tagName,publishedAt")
    return [r["tagName"] for r in sorted(rel, key=lambda r: r["publishedAt"],
                                         reverse=True)]


def pandoc_bound(text):
    """The pandoc constraint in a pandoc-crossref.cabal or package.yaml."""
    m = (re.search(r'^\s*pandoc:\s*"([^"]+)"', text, re.M)
         or re.search(r"^[\s,]*pandoc\s+([<>=^][^,\n]*\d)", text, re.M))
    return m.group(1).strip() if m else None


def admits(bound, version):
    v = ver(version)
    for part in bound.split("&&"):
        op, x = re.match(r"\s*(\^>=|>=|<=|==|<|>)\s*([\d.*]+)", part).groups()
        if x.endswith(".*"):
            op, x = "^==", x[:-2]
        x = ver(x)
        ok = {">=": v >= x, "<=": v <= x, ">": v > x, "<": v < x,
              "==": v == x, "^==": v[:len(x)] == x,
              "^>=": v >= x and v[:2] == x[:2]}[op]
        if not ok:
            return False
    return True


def crossref_bound(tag):
    _, body = http(f"https://raw.githubusercontent.com/{CROSSREF_REPO}/"
                   f"{tag}/pandoc-crossref.cabal")
    return pandoc_bound(body)


def patched_bound(tag):
    """The pandoc bound after our patches for `tag`, if we have any."""
    bounds = [pandoc_bound(l[1:]) for p in
              sorted(Path(f"patches/pandoc-crossref/{tag}").glob("*.patch"))
              for l in p.read_text().splitlines()
              if l.startswith("+") and not l.startswith("+++")]
    return next((b for b in bounds if b), None)


def write_bounds_patch(tag, version):
    """Write patches/pandoc-crossref/<tag>/ relaxing its pandoc upper bound to
    the next major (PVP A.B) after `version`; return the new bound."""
    major = ver(version)[:2]
    upper = f"{major[0]}.{major[1] + 1}"
    with tempfile.TemporaryDirectory() as tmp:
        run("git", "clone", "-q", "--depth", "1", "--branch", tag,
            f"https://github.com/{CROSSREF_REPO}", tmp)
        for name, pat in [("package.yaml", r'(^\s*pandoc:\s*"[^"]*<\s*)[\d.]+'),
                          ("pandoc-crossref.cabal",
                           r"(^[\s,]*pandoc\s+[^,\n]*<\s*)[\d.]+")]:
            f = Path(tmp, name)
            if f.exists():
                f.write_text(re.sub(pat, rf"\g<1>{upper}", f.read_text(),
                                    flags=re.M))
        diff = run("git", "diff", "--no-ext-diff", "--no-color", cwd=tmp)
    d = Path(f"patches/pandoc-crossref/{tag}")
    for old in d.glob("*.patch"):
        old.unlink()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"0001-allow-pandoc-{version}.patch").write_text(
        f"Allow pandoc {version} in pandoc-crossref {tag} "
        f"(upstream: {crossref_bound(tag)}).\n"
        "Only the bounds change; crossref's own test suites (flaky ones "
        "included)\n"
        f"must pass against pandoc {version} in CI "
        "(scripts/build-crossref.sh).\n\n" + diff + "\n")
    return patched_bound(tag)


def pick_crossref(version, current):
    """(tag, note): the newest tag admitting `version`, else `current`
    with its bounds patched as needed."""
    for tag in crossref_releases():
        bound = crossref_bound(tag)
        if bound and admits(bound, version):
            return tag, f"{tag} admits pandoc {version} ({bound})."
    bound = patched_bound(current)
    if bound and admits(bound, version):
        return current, (f"No tag admits pandoc {version}; our {current} "
                         f"patch ({bound}) already does.")
    bound = write_bounds_patch(current, version)
    return current, (f"No tag admits pandoc {version}; "
                     f"patches/pandoc-crossref/{current}/ now relaxes "
                     f"its bound to `{bound}`. Its test suites decide "
                     "whether it ships.")


def crossref_comment(tag, version):
    """The pins.env comment on CROSSREF_TAG: only a patched tag has one."""
    bound = crossref_bound(tag)
    if not bound or admits(bound, version):
        return None
    major = ".".join(version.split(".")[:2])
    return f"{tag} allows pandoc {bound}, so it is patched to admit {major}.x."


def set_crossref(tag, version):
    set_pin("CROSSREF_TAG", tag, crossref_comment(tag, version), marker="v")


def switch_crossref(old, new, version):
    run("git", "rm", "-rq", "--ignore-unmatch", f"patches/pandoc-crossref/{old}")
    set_crossref(new, version)


# --- checks --------------------------------------------------------------

def check_image(branch):
    pins = read_pins()
    if digest_exists(pins["GHC_MUSL_IMAGE"]):
        return None
    set_image(pins["GHC_VERSION"])
    digest = read_pins()["GHC_MUSL_IMAGE"].split("@")[1]
    return dict(
        branch=f"bot/ghc-musl-{branch}-{digest[7:19]}",
        title=f"{branch}: repin ghc-musl (GHC {pins['GHC_VERSION']})",
        body=f"The pinned digest `{pins['GHC_MUSL_IMAGE'].split('@')[1]}` no "
             f"longer exists on quay: benz0li rebuilt the tag and quay deleted "
             f"the old manifest, so this branch's Linux jobs can't start.\n\n"
             f"`{digest}` is the current `ghc-musl:{pins['GHC_VERSION']}`, so "
             "the GHC is unchanged. Published packages are not rebuilt "
             "(uploads skip existing files); this keeps the branch buildable.",
        labels=["ghc-musl"])


def check_crossref(branch):
    pins = read_pins()
    current, version = pins["CROSSREF_TAG"], pins["PANDOC_VERSION"]
    releases = crossref_releases()
    if current not in releases:
        return None
    for tag in releases[:releases.index(current)]:
        bound = crossref_bound(tag)
        if bound and admits(bound, version):
            break
    else:
        return None
    patched = patched_bound(current)
    switch_crossref(current, tag, version)
    set_pin("CROSSREF_BUILD_NUMBER", "0")
    return dict(
        branch=f"bot/crossref-{tag}-{branch}",
        title=f"{branch}: pandoc-crossref {tag}",
        body=f"pandoc-crossref {tag} admits pandoc {version} (`{bound}`), so "
             f"it replaces {current}"
             + (" and our bounds patch for it is dropped" if patched else "")
             + ". `CROSSREF_BUILD_NUMBER` resets to 0; the pandoc packages "
             "already exist and are skipped on upload.",
        labels=["crossref"])


def check_pandoc(branch):
    if branch != "main":
        return None
    rel = gh_json("release", "view", "-R", PANDOC_REPO,
                  "--json", "tagName,publishedAt,isPrerelease")
    pins = read_pins()
    old, new = pins["PANDOC_VERSION"], rel["tagName"]
    if rel["isPrerelease"] or ver(new) <= ver(old):
        return None
    review, labels = [], ["pandoc-release"]

    with tempfile.TemporaryDirectory() as src:
        run("git", "clone", "-q", "--filter=blob:none", "--no-checkout",
            f"https://github.com/{PANDOC_REPO}", src)
        show = lambda rev, f: run("git", "show", f"{rev}:{f}", cwd=src,
                                  check=False)

        def diff(*files, context="-U0"):
            return run("git", "diff", "--no-ext-diff", "--no-color", context,
                       old, new, "--", *files, cwd=src)

        # Toolchain: the ghc-musl tag upstream's release builds use
        def ghc_minor(rev):
            m = re.search(r"ghc-musl:(\d+\.\d+)",
                          show(rev, ".circleci/config.yml"))
            return m and m.group(1)
        old_minor, new_minor = ghc_minor(old), ghc_minor(new)
        ghc = pins["GHC_VERSION"]
        if new_minor and new_minor != old_minor:
            digest = tag_digest(new_minor)
            ghc = next((t for t in (f"{new_minor}.{p}" for p in range(20, -1, -1))
                        if tag_digest(t) == digest), None)
            if not ghc:
                raise SystemExit(f"no ghc-musl tag {new_minor}.x matches "
                                 f"ghc-musl:{new_minor}")
            review.append(f"**GHC moved** from {old_minor} to {new_minor} "
                          f"(`ghc-musl:{new_minor}` is GHC {ghc}). Check "
                          "`release-candidate.yml` and `CABAL_VERSION`; the "
                          "macOS and Windows jobs take `GHC_VERSION` too.")
            labels.append("needs-review")
        rc = show(new, ".github/workflows/release-candidate.yml")
        for m in sorted(set(re.findall(r"ghc --set ([\d.]+)", rc))):
            if not ghc.startswith(m):
                review.append(f"`release-candidate.yml` installs GHC {m}, "
                              f"not {ghc}.")
                labels.append("needs-review")
        set_pin("GHC_VERSION", ghc)
        set_image(ghc)

        # pandoc API
        apis = []
        for rev in (old, new):
            Path(src, "pandoc.cabal").write_text(show(rev, "pandoc.cabal"))
            apis.append(run("bash", "scripts/pandoc-api-version.sh", src))
        if apis[0] != apis[1]:
            review.append(f"**pandoc API {apis[0]} → {apis[1]}.** `pandoc-api` "
                          f"follows by itself, but every filter in "
                          f"pandoc-forge/filters must be checked against "
                          f"{new} and rebuilt with `pandoc_api: {apis[1]}` "
                          "(variants.yaml) once it is released.")
            labels.append("pandoc-api")

        # The rest of upstream's diff that can need work here
        stat = run("git", "diff", "--no-ext-diff", "--no-color", "--stat",
                   old, new, "--", *WATCH, cwd=src)
        # Hunks of the cabal files that touch flags or conditionals, with
        # context (a changed "Default:" means nothing without its flag), and
        # every change to cabal.project
        hunks = [h for h in re.split(r"^(?=@@)", diff(
                     "pandoc.cabal", "pandoc-cli/pandoc-cli.cabal",
                     context="-U3"), flags=re.M)[1:]
                 if re.search(r"^[+-].*\b(flag|default:|manual:|if )",
                              h, re.M | re.I)]
        project = diff("cabal.project")
        if hunks or project:
            review.append("Flags, conditionals or `cabal.project` changed "
                          "(`scripts/cabal-opts.sh` sets flags explicitly):\n"
                          "```diff\n" + "".join(hunks) + project + "\n```")
            labels.append("needs-review")
        if "ghc-wasm-meta" in diff("flake.lock"):
            review.append("`flake.lock` moves ghc-wasm-meta: the wasm "
                          "toolchain changes.")
            labels.append("needs-review")
        if diff("wasm"):
            review.append("`wasm/` changed (patches, build).")
            labels.append("needs-review")
        if re.search(rf"^\+.*Since: {re.escape(new)}\b",
                     diff("doc/lua-filters.md"), re.M):
            review.append(f"New Lua API marked `Since: {new}` "
                          "(doc/lua-filters.md): filters using it need "
                          f"`>={new}` run constraints.")

    set_pin("PANDOC_VERSION", new)
    set_pin("INDEX_STATE", rel["publishedAt"])
    for k in ("PANDOC_BUILD_NUMBER", "PANDOC_WASM_BUILD_NUMBER",
              "CROSSREF_BUILD_NUMBER"):
        set_pin(k, "0")
    tag, note = pick_crossref(new, pins["CROSSREF_TAG"])
    if tag != pins["CROSSREF_TAG"]:
        switch_crossref(pins["CROSSREF_TAG"], tag, new)
    else:
        set_crossref(tag, new)
    if "patches" in note:
        labels.append("crossref-patched")

    body = [f"[pandoc {new}](https://github.com/{PANDOC_REPO}/releases/tag/"
            f"{new}), published {rel['publishedAt']} (`INDEX_STATE`). "
            "Build numbers reset to 0.",
            f"**pandoc-crossref:** {note}",
            "**Upstream changes to check:** " +
            ("none found by the bot (happy path)." if not review else ""),
            *[f"- {r}" for r in review],
            f"<details><summary>git diff --stat {old} {new} -- "
            f"{' '.join(WATCH)}</summary>\n\n```\n{stat}\n```\n</details>",
            f"**Before merging:** if a downstream package pins {old} exactly, "
            f"or {old} is the newest pandoc with an unpatched crossref, branch "
            f"`v{'.'.join(old.split('.')[:2])}.x` from `main` first. Check "
            "crossref's steps in the logs (they are `continue-on-error`). "
            "**After merging:** check from `pandoc-forge/dev`, then release "
            "(README: Bumping to a new pandoc release)."]
    return dict(branch=f"bot/pandoc-{new}", title=f"pandoc {new}",
                body="\n\n".join(body), labels=labels)


# --- driver --------------------------------------------------------------

def propose(base, pr, dry_run):
    if not run("git", "status", "--porcelain", "--", *OWNED):
        return
    print(f"== {base}: {pr['title']} ({pr['branch']})")
    if run("git", "ls-remote", "--heads", "origin", pr["branch"]):
        print("   already proposed; skipping")
        return
    run("git", "add", "-A", "--", *OWNED)
    if dry_run:
        print(run("git", "--no-pager", "diff", "--no-ext-diff", "--cached"))
        print(pr["body"])
        return
    run("git", "switch", "-q", "-c", pr["branch"])
    run("git", "commit", "-q", "-m", pr["title"], "-m", pr["body"])
    run("git", "push", "-q", "origin", pr["branch"])
    labels = dict.fromkeys(pr["labels"])
    for label in labels:
        run("gh", "label", "create", label, "--force")
    args = ["gh", "pr", "create", "-B", base, "-H", pr["branch"],
            "-t", pr["title"], "-b", pr["body"]]
    for label in labels:
        args += ["--label", label]
    print("  ", run(*args))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print the changes instead of pushing and opening PRs")
    ap.add_argument("branches", nargs="*")
    a = ap.parse_args()
    run("git", "fetch", "-q", "origin")
    branches = a.branches or ["main"] + [
        b.removeprefix("origin/") for b in
        run("git", "branch", "-r", "--format=%(refname:short)",
            "--list", "origin/v*").split()]
    for branch in branches:
        for check in (check_pandoc, check_image, check_crossref):
            run("git", "switch", "-q", "--detach", f"origin/{branch}")
            pr = check(branch)
            if pr:
                propose(branch, pr, a.dry_run)
            run("git", "reset", "-q", "--hard")
            run("git", "clean", "-qfd", "--", "patches")
            if pr and check is check_pandoc:
                break  # a release PR covers main's image and crossref too


if __name__ == "__main__":
    sys.exit(main())
