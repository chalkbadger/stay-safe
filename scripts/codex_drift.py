import argparse
import difflib
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "codex-rs/core/config.schema.json"
TAG = re.compile(r"rust-v(\d+)\.(\d+)\.(\d+)\Z")
PREFIX = "https://github.com/openai/codex/blob/"
LINK = re.compile(r"\[([^\]]+)\](?::\s*|\()(https://github\.com/openai/codex/blob/[^\s)]+)")
SOURCE = re.compile(re.escape(PREFIX) + r"([0-9a-f]{40})/([^#]+)(?:#L(\d+)(?:-L(\d+))?)?\Z")


def version(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f"not a stable Codex tag: {tag}")
    return tuple(map(int, match.groups()))


def git(repo, *args):
    try:
        run = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args],
                             text=True, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"Git failed: {error}") from error
    if run.returncode:
        raise ValueError(f"Git {' '.join(args)} failed: {run.stderr.strip()}")
    return run.stdout


def citations(path):
    text = Path(path).read_text(encoding="utf-8")
    links = LINK.findall(text)
    if not links or len(links) != text.count(PREFIX):
        raise ValueError("meanings must contain labeled, pinned Codex source links")
    result = []
    for label, url in links:
        match = SOURCE.fullmatch(url)
        if not match:
            raise ValueError(f"invalid pinned source link: {label}")
        ref, source, first, last = match.groups()
        bounds = (int(first) - 1, int(last or first)) if first else None
        if bounds and not 0 <= bounds[0] < bounds[1]:
            raise ValueError(f"invalid source range: {label}")
        result.append({"label": label, "ref": ref, "path": source, "range": bounds})
    return result


def mapped_range(old, new, bounds):
    if bounds is None:
        return None
    operations = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    def boundary(position, right):
        choices = []
        for action, a, b, c, d in operations:
            if a <= position <= b:
                if action == "equal":
                    choices.append(c + position - a)
                elif a == b or a < position < b:
                    choices.extend((c, d))
                else:
                    choices.append(c if position == a else d)
        return (max if right else min)(choices or [0])
    return boundary(bounds[0], False), boundary(bounds[1], True)


def touches(operation, bounds):
    action, first, last, _, _ = operation
    if action == "equal":
        return False
    if bounds is None:
        return True
    start, end = bounds
    return start <= first <= end if first == last else first < end and last > start


def changed_source(old, new, ranges, before, after, path):
    hunks, labels = [], set()
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for group in matcher.get_grouped_opcodes(3):
        affected = {label for label, bounds in ranges
                    if any(touches(operation, bounds) for operation in group)}
        if not affected:
            continue
        labels.update(affected)
        a, b, c, d = group[0][1], group[-1][2], group[0][3], group[-1][4]
        hunks.append(f"@@ -{a + 1 if b > a else a},{b-a} +{c + 1 if d > c else c},{d-c} @@\n")
        for action, i, j, k, l in group:
            chunks = [(" ", old[i:j])] if action == "equal" else []
            if action in {"replace", "delete"}:
                chunks.append(("-", old[i:j]))
            if action in {"replace", "insert"}:
                chunks.append(("+", new[k:l]))
            for prefix, lines in chunks:
                for line in lines:
                    hunks.append(prefix + line)
                    if not line.endswith("\n"):
                        hunks.append("\n\\ No newline at end of file\n")
    if hunks:
        return {"path": path, "labels": sorted(labels),
                "diff": f"--- {before}/{path}\n+++ {after}/{path}\n" + "".join(hunks)}
    return None


def schema_fields(schema):
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        raise ValueError("configuration schema must be an object with properties")
    fields = {}
    def visit(node, path, seen):
        if not isinstance(node, (dict, bool)):
            raise ValueError(f"invalid schema node at {path}")
        values = fields.setdefault(path or "$", [])
        if isinstance(node, bool):
            values.append({"allowed": node})
            return
        ref = node.get("$ref")
        if ref:
            if not isinstance(ref, str) or not ref.startswith("#/"):
                raise ValueError(f"unsupported schema reference: {ref}")
            target = schema
            try:
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError) as error:
                raise ValueError(f"missing schema reference: {ref}") from error
            if ref not in seen:
                visit(target, path, seen | {ref})
        navigation = {"$ref", "$schema", "definitions", "properties"}
        if isinstance(node.get("additionalProperties"), dict):
            navigation.add("additionalProperties")
        metadata = {key: value for key, value in node.items() if key not in navigation}
        if metadata and metadata not in values:
            values.append(metadata)
        properties = node.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"invalid schema properties at {path}")
        for key, child in sorted(properties.items()):
            visit(child, f"{path}.{key}" if path else key, seen)
        for key in ("allOf", "anyOf", "oneOf"):
            branches = node.get(key, [])
            if key in node and (not isinstance(branches, list) or not branches):
                raise ValueError(f"invalid schema {key} at {path}: expected a nonempty list")
            for child in branches:
                visit(child, path, seen)
        if isinstance(node.get("additionalProperties"), dict):
            visit(node["additionalProperties"], f"{path}.*", seen)
        if "items" in node:
            for child in node["items"] if isinstance(node["items"], list) else [node["items"]]:
                visit(child, f"{path}[]", seen)
    visit(schema, "", set())
    return fields


def schema_diff(old, new):
    changes = []
    for path in sorted(old.keys() | new.keys()):
        if path not in old:
            changes.append({"change": "added", "path": path, "after": new[path]})
        elif path not in new:
            changes.append({"change": "removed", "path": path, "before": old[path]})
        elif old[path] != new[path]:
            changes.append({"change": "changed", "path": path, "before": old[path], "after": new[path]})
    return changes


def scan(repo, meanings, start, end=None):
    tags = sorted((tag for tag in git(repo, "tag", "--list", "rust-v*").splitlines()
                   if TAG.fullmatch(tag)), key=version)
    end = end or (tags[-1] if tags else None)
    if start not in tags or end not in tags or version(start) > version(end):
        raise ValueError(f"missing or reversed stable release range: {start}..{end}")
    links = citations(meanings)
    @lru_cache(maxsize=None)
    def contents(ref, path, required=False):
        entry = git(repo, "ls-tree", ref, "--", path)
        if not entry:
            if required:
                raise ValueError(f"missing source file: {ref}:{path}")
            return []
        if entry.split()[1] != "blob":
            raise ValueError(f"source is not a file: {ref}:{path}")
        return git(repo, "show", f"{ref}:{path}").splitlines(keepends=True)
    def schema(ref):
        try:
            return schema_fields(json.loads("".join(contents(ref, SCHEMA, True))))
        except (ValueError, TypeError) as error:
            raise ValueError(f"invalid schema at {ref}:{SCHEMA}: {error}") from error
    for link in links:
        anchor = contents(link["ref"], link["path"], True)
        if link["range"] and link["range"][1] > len(anchor):
            raise ValueError(f"source range exceeds file: {link['label']}")
    previous_schema, releases, before = schema(start), [], start
    for after in (tag for tag in tags if version(start) < version(tag) <= version(end)):
        sources = []
        for path in sorted({link["path"] for link in links}):
            old, new = contents(before, path), contents(after, path)
            if old == new:
                continue
            ranges = [(link["label"], mapped_range(contents(link["ref"], path), old, link["range"]))
                      for link in links if link["path"] == path]
            change = changed_source(old, new, ranges, before, after, path)
            if change:
                sources.append(change)
        current_schema = schema(after)
        releases.append({"from": before, "tag": after,
                         "commit": git(repo, "rev-parse", f"{after}^{{commit}}").strip(),
                         "sources": sources, "schema": schema_diff(previous_schema, current_schema)})
        previous_schema, before = current_schema, after
    return {"from": start, "through": end, "releases": releases}


def render(report):
    lines = ["# Codex release scan", "", f"Scanned {len(report['releases'])} stable releases: "
             f"`{report['from']}` → `{report['through']}`.", "",
             "Source drift only; behavior and uncited callers need review. Progress was not changed."]
    for release in report["releases"]:
        lines += ["", f"## {release['from']} → {release['tag']}", "", f"Commit: `{release['commit']}`", ""]
        for source in release["sources"]:
            lines += [f"### {source['path']} — {', '.join(source['labels'])}", "", "```diff", source["diff"].rstrip(), "```", ""]
        if not release["sources"]:
            lines += ["No changed cited ranges.", ""]
        lines += ["### Configuration fields", "",
                  f"[Schema at this release]({PREFIX}{release['commit']}/{SCHEMA})", ""]
        for change in release["schema"]:
            lines.append(f"- {change['change'].capitalize()}: `{change['path']}`")
        if not release["schema"]:
            lines.append("No schema field changes.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-repo", required=True, type=Path)
    parser.add_argument("--meanings", type=Path, default=ROOT / "harnesses/codex.md")
    parser.add_argument("--state", type=Path, default=ROOT / "docs/codex-scan-state.json")
    parser.add_argument("--from-tag")
    parser.add_argument("--to-tag")
    args = parser.parse_args()
    try:
        start = args.from_tag
        if start is None:
            try:
                start = json.loads(args.state.read_text(encoding="utf-8"))["last_scanned_tag"]
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise ValueError(f"invalid scan state {args.state}: {error}") from error
        report = scan(args.codex_repo, args.meanings, start, args.to_tag)
    except (OSError, ValueError) as error:
        print(f"Codex scan failed: {error}", file=sys.stderr)
        return 2
    print(render(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
