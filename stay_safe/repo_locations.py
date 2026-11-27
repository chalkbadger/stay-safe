from bisect import bisect_left
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tomllib
from urllib.parse import quote_from_bytes

from .codex import open_input


def metadata(path, limit):
    with os.fdopen(open_input(path), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError
        return data


def tracked_files(index, wanted):
    version = int.from_bytes(index[4:8], "big")
    if index[:4] != b"DIRC" or version not in (2, 3, 4):
        return {}
    for digest in (hashlib.sha1, hashlib.sha256):
        width = digest().digest_size
        if digest(memoryview(index)[:-width]).digest() == index[-width:]:
            break
    else:
        return {}
    end = len(index) - width
    pos, previous, tracked = 12, b"", {}
    for _ in range(int.from_bytes(index[8:12], "big")):
        start = pos
        mode = int.from_bytes(index[pos + 24:pos + 28], "big")
        blob_id = index[pos + 40:pos + 40 + width]
        pos += 40 + width
        flags = int.from_bytes(index[pos:pos + 2], "big")
        pos += 2
        extended = 0
        if flags & 0x4000:
            extended = int.from_bytes(index[pos:pos + 2], "big")
            pos += 2
        prefix = b""
        if version == 4:
            remove = index[pos] & 127
            while index[pos] & 128:
                pos += 1
                remove = ((remove + 1) << 7) + (index[pos] & 127)
                if remove > len(previous):
                    raise ValueError
            pos += 1
            if remove > len(previous):
                raise ValueError
            prefix = previous[:len(previous) - remove]
        nul = index.index(0, pos, end)
        if len(prefix) + nul - pos > 4096:
            return {}
        previous = prefix + index[pos:nul]
        pos = nul + 1
        if version < 4:
            pos += (start - pos) % 8
        if previous in wanted and mode in (0o100644, 0o100755) and not flags & 0x3000 and not extended & 0x2000:
            tracked[previous] = blob_id
    while pos < end:
        extension = index[pos:pos + 4]
        if pos + 8 > end:
            return {}
        size = int.from_bytes(index[pos + 4:pos + 8], "big")
        if not 65 <= extension[0] <= 90 and (extension != b"sdir" or size != 0):
            return {}
        pos += 8 + size
    return tracked if pos == end else {}


@dataclass
class SelectedFile:
    uri: str
    device: int
    inode: int
    blob_id: bytes
    lines: dict = field(default_factory=dict)

    def capture(self, info, content, harness):
        self.lines = {}
        if (info.st_dev, info.st_ino) != (self.device, self.inode):
            return
        digest = hashlib.sha1() if len(self.blob_id) == 20 else hashlib.sha256()
        digest.update(f"blob {len(content)}\0".encode("ascii"))
        digest.update(content)
        if digest.digest() == self.blob_id:
            self.lines = setting_lines(content, harness)


def checkout_path(root, candidate):
    current = root
    for part in candidate.relative_to(root).parts:
        if part == "..":
            if current == root:
                return None
            current = current.parent
        else:
            current = current / part
            if stat.S_ISLNK(current.stat(follow_symlinks=False).st_mode):
                return None
    return current


def selected_files(paths):
    overrides = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
    if not paths or any(key in os.environ for key in overrides):
        return {}
    try:
        cwd = Path(".").resolve(strict=True)
        for root in (cwd, *cwd.parents):
            gitdir = root / ".git"
            try:
                mode = gitdir.stat(follow_symlinks=False).st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISREG(mode):
                pointer = os.fsdecode(metadata(gitdir, 8192)).removesuffix("\n")
                if not pointer.startswith("gitdir: "):
                    return {}
                gitdir = root / pointer[8:]
            elif not stat.S_ISDIR(mode):
                return {}
            break
        else:
            return {}
    except (OSError, ValueError, IndexError, RuntimeError):
        return {}
    candidates = {}
    for path in paths:
        try:
            candidate = checkout_path(root, cwd / path)
            if candidate is None or candidate.resolve(strict=True) != candidate:
                continue
            name = os.fsencode(candidate.relative_to(root))
            info = candidate.stat(follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):
                candidates[path] = (name, info)
        except (OSError, ValueError, RuntimeError):
            continue
    if not candidates:
        return {}
    try:
        index = metadata(gitdir / "index", 64 * 1024 * 1024)
        tracked = tracked_files(index, {name for name, _ in candidates.values()})
    except (OSError, ValueError, IndexError):
        return {}
    return {path: SelectedFile(quote_from_bytes(name), info.st_dev, info.st_ino, tracked[name])
            for path, (name, info) in candidates.items() if name in tracked}


KEY = r"""(?:[A-Za-z0-9_-]+|'[^'\n]*'|"(?:\\.|[^"\\\n])*")"""
DOTTED = re.compile(KEY + r"(?:[ \t]*\.[ \t]*" + KEY + r")*")
KEY_PART = re.compile(KEY)
STRING = re.compile(
    r'"""(?:\\[\s\S]|"(?!"")|[^"\\]++)*"{3,5}'
    + r"|'''(?:'(?!'')|[^']++)*'{3,5}"
    + r"""|"(?:\\.|[^"\\]++)*"|'[^']*'""")
DELIMITER = re.compile(r"""[#\n"'\[\]{}]""")
SPACE = re.compile(r"\s*")


def toml_lines(text, line):
    fields, table, pos = {}, (), 0
    while pos < len(text):
        pos = SPACE.match(text, pos).end()
        if pos == len(text):
            break
        end = text.find("\n", pos)
        end = len(text) if end < 0 else end
        if text[pos] == "#":
            pos = end
            continue
        header = text[pos] == "["
        array = text.startswith("[[", pos)
        start = pos + (2 if array else int(header))
        key = DOTTED.match(text, SPACE.match(text, start).end())
        if key is None:
            return {}
        pieces = tuple(tomllib.loads("v=" + k)["v"] if k[0] in "\"'" else k
                       for k in KEY_PART.findall(key[0]))
        if header:
            table = None if array else pieces
            pos = end
            continue
        depth, cursor = 0, key.end()
        while match := DELIMITER.search(text, cursor):
            cursor = match.end()
            char = match[0]
            if char in "\"'":
                string = STRING.match(text, match.start())
                if string is None:
                    return {}
                cursor = string.end()
            elif char == "#":
                newline = text.find("\n", cursor)
                cursor = len(text) if newline < 0 else newline
            elif char == "\n" and depth == 0:
                break
            else:
                depth += int(char in "[{") - int(char in "]}")
        else:
            cursor = len(text)
        if table is not None:
            path = table + pieces
            fields[path] = line(pos)
            value = text[key.end():cursor].lstrip(" \t=").rstrip("\r\n")
            if value.startswith("{") and "\n" not in value:
                values = tomllib.loads("v=" + value)["v"]
                def inline(items, parent):
                    for name, item in items.items():
                        fields[parent + (name,)] = line(pos)
                        if isinstance(item, dict):
                            inline(item, parent + (name,))
                inline(values, path)
        pos = cursor
    return fields


def json_lines(text, line):
    fields = {}
    decoder = json.JSONDecoder()

    def value(pos, path):
        char = text[pos]
        if char not in "{[":
            return decoder.raw_decode(text, pos)[1]
        pos = SPACE.match(text, pos + 1).end()
        keys, number = set(), 0
        while text[pos] not in "}]":
            start = pos
            if char == "{":
                key, pos = decoder.raw_decode(text, pos)
                if key in keys:
                    raise ValueError
                keys.add(key)
                pos = SPACE.match(text, SPACE.match(text, pos).end() + 1).end()
            else:
                number += 1
                key = str(number)
            child = path + (key,)
            fields[child] = line(start)
            pos = SPACE.match(text, value(pos, child)).end()
            if text[pos] == ",":
                pos = SPACE.match(text, pos + 1).end()
        return pos + 1

    value(SPACE.match(text).end(), ())
    return fields


def setting_lines(content, harness):
    text = content.decode("utf-8")
    newlines = [m.start() for m in re.finditer("\n", text)]
    def line(pos):
        return bisect_left(newlines, pos) + 1
    try:
        return (toml_lines if harness == "Codex" else json_lines)(text, line)
    except (ValueError, IndexError, RecursionError):
        return {}


def setting_line(risk, keys, fields, report):
    rule = risk["rule"]
    if report["harness"] == "Claude Code":
        if keys[0] == "hooks":
            from .claude import HOOK_FIELDS, runs
            handlers = [h for h in report["_hooks"][risk["entry"]]["handlers"] if runs(h)]
            if len(handlers) != 1:
                return None
            hook = handlers[0]
            field_names = HOOK_FIELDS[hook["kind"]]
            if len(field_names) != 1:
                return None
            keys = ("hooks", hook["event"], str(hook["group"]), "hooks", str(hook["position"]), field_names[0])
        if keys[0] == "sshHostCommands":
            commands = [line for path, line in fields.items()
                        if len(path) == 3 and path[0] == "sshHostCommands" and path[2] == "command"]
            return commands[0] if len(commands) == 1 else None
        if keys in (("statusLine",), ("fileSuggestion",)):
            keys += ("command",)
    elif keys == ("approval_policy",):
        if rule != "commands_without_prompts" or risk["configured_evidence"][0] != "never":
            return None
    elif keys == ("shell_environment_policy",):
        keys += ("inherit",)
    elif keys[0] in ("apps", "mcp_servers"):
        if rule == "configured_program":
            options = [keys + (field,) for field in ("command", "http_headers_helper") if keys + (field,) in fields]
            return fields[options[0]] if len(options) == 1 else None
        if rule in ("automatic_tools", "self_described_tools"):
            keys += ("approval_mode" if len(keys) == 4 else "default_tools_approval_mode",)
        elif rule == "destructive_tools" and len(keys) == 4:
            keys += ("enabled",)
        elif rule == "destructive_tools" and keys[0] == "apps":
            candidates = ("destructive_enabled",) if keys[1] == "_default" else ("default_tools_enabled", "destructive_enabled")
            for field in candidates:
                if keys + (field,) in fields:
                    return fields[keys + (field,)]
            return fields.get(("apps", "_default", "destructive_enabled"))
        else:
            return None
    elif keys[0] == "hooks":
        return None
    return fields.get(keys)
