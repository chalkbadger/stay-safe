"""Inventory Codex's saved one-line allow records without parsing a rules program."""

import json
import os
import re
import stat

from .codex import MAX_BYTES, Reader, open_input


RECORD = re.compile(r'prefix_rule\(pattern=(\[.*\]), decision="allow"\)')
# The only words of a saved approval the report may show, as its first word: the program list in
# contracts/claims.md [lists_commands_codex_stops_asking_about]. Change it only by pull request, together
# with that contract line.
PROGRAMS = ('git', 'gh', 'npm', 'npx', 'pnpm', 'yarn', 'node', 'python', 'python3', 'pip', 'pip3', 'uv', 'cargo',
            'go', 'make', 'docker', 'kubectl', 'curl', 'wget', 'ssh', 'bash', 'sh', 'rm', 'mv', 'cp', 'chmod')


def declaration(line):
    record = RECORD.fullmatch(line)
    if record is None:
        return None
    try:
        pattern = json.loads(record[1])
    except (ValueError, RecursionError):
        return None
    if not pattern or not all(isinstance(token, str) for token in pattern):
        return None
    return pattern


def read_file(path, source, *, discovered=False):
    reader = Reader(source)
    try:
        fd = open_input(path)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                reader.gap('Rules input is not a regular file.')
                return [], sorted(reader.gaps)
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            reader.gap('Rules input exceeds the 1 MiB size limit.')
            return [], sorted(reader.gaps)
        text = content.decode('utf-8')
    except FileNotFoundError:
        if discovered:
            reader.add(['rules'], 'rules file', ['absent'])
        else:
            reader.gap('Selected rules input is missing; its path was withheld.')
        return reader.entries, sorted(reader.gaps)
    except (OSError, ValueError):
        reader.gap('Rules input is unreadable, a symlink or invalid UTF-8; raw errors were withheld.')
        return [], sorted(reader.gaps)

    for index, line in enumerate(text.split('\n'), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        pattern = declaration(line)
        if pattern is None:
            reader.gap('Rules contain lines that are not inspected.')
            continue
        observations = [f'program: {name}' for name in PROGRAMS if name == pattern[0]] + [f'tokens: {len(pattern)}']
        if len(pattern) == 1:
            observations.append('broad: one-token prefix')
        reader.add(['prefix_rule', str(index)], 'saved approval', observations, {'saved_approval': True})
    return reader.entries, sorted(reader.gaps)


def other_files(path, source):
    """Codex also loads every other *.rules file beside the default one; flag them unread and unnamed."""
    try:
        names = os.listdir(path.parents[0])
    except FileNotFoundError:
        return []
    except OSError:
        return [f'{source}: The rules directory cannot be listed; '
                'other rules files may exist and were not inspected.']
    if any(name.endswith('.rules') and name != 'default.rules' for name in names):
        return [f'{source}: Other rules files exist and were not inspected.']
    return []
