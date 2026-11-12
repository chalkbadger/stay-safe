"""Identify the diagnostic without invoking Git or contacting a service."""

import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INSTALLED = (ROOT / "stay_safe/package.txt").is_file()
REPOSITORY = "https://github.com/chalkbadger/stay-safe"
SOURCE_FILES = (
    "stay_safe/__init__.py", "stay_safe/__main__.py", "stay_safe/cli.py", "stay_safe/codex.py",
    "stay_safe/codex_rules.py", "stay_safe/provenance.py", "stay_safe/report.py", "stay_safe/rules.py",
    "stay_safe/save.py",
    "harnesses/codex.md", "incidents.md",
)
# Holds the commit in release archives (.gitattributes export-subst). It names the commit rather than running code,
# so it is not fingerprinted: a clone and a zip of one commit keep the same tool_revision.
RELEASE_FILE = "stay_safe/release.txt"
GAP = "Revision unknown; checkout source links are withheld."
COMMIT = re.compile(r"(?!0{40})[0-9a-f]{40}")


def valid_ref(ref):
    """Accept a full ref name only as git check-ref-format does (https://git-scm.com/docs/git-check-ref-format).

    No component may be empty or start with ".", so the name stays inside the Git directory.
    """
    return (ref.startswith("refs/") and not ref.endswith(".") and ".." not in ref and "@{" not in ref
            and not any(ord(c) < 0x20 or ord(c) == 0x7f or c in " ~^:?*[\\" for c in ref)
            and not any(part == "" or part.startswith(".") or part.endswith(".lock") for part in ref.split("/")))


def checkout_revision(root=ROOT):
    """Read detached or symbolic HEAD, including packed refs and worktrees."""
    try:
        gitdir = root / ".git"
        if gitdir.is_file():
            pointer = gitdir.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir: "):
                return None
            gitdir = root / pointer[8:]
        head = (gitdir / "HEAD").read_text(encoding="utf-8").removesuffix("\n")
        if COMMIT.fullmatch(head):
            return head
        ref = head[5:]
        if not head.startswith("ref: ") or not valid_ref(ref):
            return None
        common = gitdir
        if (gitdir / "commondir").is_file():
            common = gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()
        loose = common / ref
        if loose.is_file():
            value = loose.read_text(encoding="utf-8").strip()
            return value if COMMIT.fullmatch(value) else None
        for line in (common / "packed-refs").read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[1] == ref and COMMIT.fullmatch(fields[0]):
                return fields[0]
    except (OSError, ValueError):
        pass
    return None


def archive_revision(root=ROOT):
    """Read the commit `git archive` wrote into the revision file through its export-subst attribute.

    A file still holding the `$Format:%H$` placeholder, or anything but one full commit hash, gives None.
    """
    try:
        value = (root / RELEASE_FILE).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return value if COMMIT.fullmatch(value) else None


def source_revision(root=ROOT):
    """Where a .git entry exists (a folder, a worktree's file, or anything else), use only Git; otherwise read the
    revision file. If the folder can't be listed, the revision is unknown rather than taken from the revision file.
    """
    if (root / "stay_safe/package.txt").is_file():
        try:
            value = (root / "stay_safe/package.txt").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            return None, None
        return (value if COMMIT.fullmatch(value) else None), "installed package commit"
    try:
        names = os.listdir(root)
    except OSError:
        return None, None
    if ".git" in names:
        return checkout_revision(root), "checkout commit"
    return archive_revision(root), "release archive commit"


def resource(name, root=ROOT):
    """Resolve bundled references while preserving their repository paths in reports."""
    if (root / "stay_safe/package.txt").is_file() and not name.startswith("stay_safe/"):
        return root / "stay_safe/data" / name
    return root / name


def fingerprints(root=ROOT):
    hashes = {}
    for name in SOURCE_FILES:
        try:
            hashes[name] = hashlib.sha256(resource(name, root).read_bytes()).hexdigest()
        except OSError:
            hashes[name] = None
    return hashes


def identify(root=ROOT, hashes=None):
    hashes = fingerprints(root) if hashes is None else hashes
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    revision, status = source_revision(root)
    return {"tool_revision": "sha256:" + digest,
              "rules_revision": "sha256:" + hashes["stay_safe/rules.py"] if hashes["stay_safe/rules.py"] else None,
              "source_revision": revision, "source_status": status if revision else "revision unknown",
              "local_modifications": "not checked"}


def source_link(revision, path):
    if not isinstance(revision, str) or not COMMIT.fullmatch(revision):
        return None
    return f"{REPOSITORY}/blob/{revision}/{path}"
