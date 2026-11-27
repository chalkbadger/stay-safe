import hashlib
import os
import re
import stat
import zlib

from .codex import open_input
from .provenance import valid_ref


LIMIT = 8 * 1024 * 1024


def metadata(path, limit):
    with os.fdopen(open_input(path), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError
        return data


def object_id(value, width):
    if len(value) != 2 * width or not re.fullmatch(b"[a-f0-9]+", value):
        raise ValueError
    return bytes.fromhex(value.decode("ascii"))


def head_commit(gitdir, common, width):
    value = metadata(gitdir / "HEAD", 8192).rstrip(b"\n")
    if value.startswith(b"ref: "):
        ref = value[5:]
        if not valid_ref(os.fsdecode(ref)):
            raise ValueError
        try:
            value = metadata(common / os.fsdecode(ref), 8192).rstrip(b"\n")
        except FileNotFoundError:
            for row in metadata(common / "packed-refs", LIMIT).splitlines():
                oid, _, name = row.partition(b" ")
                if name == ref:
                    return object_id(oid, width)
            raise ValueError
    return object_id(value, width)


def inflate(stream, limit):
    decoder = zlib.decompressobj()
    data = bytearray()
    consumed = 0
    while not decoder.eof:
        chunk = stream.read(65536)
        if not chunk or consumed > LIMIT + 65536:
            raise ValueError
        consumed += len(chunk)
        try:
            data.extend(decoder.decompress(chunk, limit + 1 - len(data)))
        except zlib.error as error:
            raise ValueError from error
        if len(data) > limit:
            raise ValueError
    return bytes(data)


def packed_offset(index, oid):
    with os.fdopen(open_input(index), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError
        header = stream.read(1032)
        if len(header) != 1032 or header[:8] != b"\xfftOc\0\0\0\2":
            return None
        width = len(oid)
        count = int.from_bytes(header[-4:], "big")
        bucket = 8 + 4 * oid[0]
        low = int.from_bytes(header[bucket-4:bucket], "big") if oid[0] else 0
        high = int.from_bytes(header[bucket:bucket+4], "big")
        while low < high <= count:
            mid = (low + high) // 2
            stream.seek(1032 + mid * width)
            item = stream.read(width)
            if item == oid:
                offsets = 1032 + count * (width + 4)
                stream.seek(offsets + 4 * mid)
                offset = int.from_bytes(stream.read(4), "big")
                if offset & 0x80000000:
                    stream.seek(offsets + count * 4 + 8 * (offset & 0x7fffffff))
                    offset = int.from_bytes(stream.read(8), "big")
                if offset >= 1 << 63:
                    raise ValueError
                return offset
            if item < oid:
                low = mid + 1
            else:
                high = mid
    return None


def delta_size(delta, pos):
    value = 0
    for shift in range(0, 28, 7):
        byte = delta[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError


def apply_delta(base, delta):
    base_size, pos = delta_size(delta, 0)
    size, pos = delta_size(delta, pos)
    if base_size != len(base) or size > LIMIT:
        raise ValueError
    result = bytearray()
    while pos < len(delta):
        op = delta[pos]
        pos += 1
        if op & 128:
            offset = length = 0
            for bit in range(7):
                if op & (1 << bit):
                    if bit < 4:
                        offset |= delta[pos] << (8 * bit)
                    else:
                        length |= delta[pos] << (8 * (bit - 4))
                    pos += 1
            length = length or 65536
            if offset + length > len(base) or len(result) + length > size:
                raise ValueError
            result.extend(base[offset:offset+length])
        else:
            if not op or pos + op > len(delta) or len(result) + op > size:
                raise ValueError
            result.extend(delta[pos:pos+op])
            pos += op
    if len(result) != size:
        raise ValueError
    return bytes(result)


class GitObjects:
    def __init__(self, folder, width):
        self.folder = folder
        self.width = width
        self.indexes = None

    def read(self, oid, kind, depth=0):
        if len(oid) != self.width or depth > 64:
            raise ValueError
        name = oid.hex()
        try:
            with os.fdopen(open_input(self.folder / name[:2] / name[2:]), "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError
                header, separator, data = inflate(stream, LIMIT).partition(b"\0")
                if not separator or header != kind + b" " + str(len(data)).encode("ascii"):
                    raise ValueError
        except FileNotFoundError:
            packs = self.folder / "pack"
            if self.indexes is None:
                pattern = rf"pack-[0-9a-f]{{{self.width * 2}}}\.idx"
                self.indexes = sorted(filename for filename in os.listdir(packs) if re.fullmatch(pattern, filename))
            for filename in self.indexes:
                offset = packed_offset(packs / filename, oid)
                if offset is not None:
                    data = self.unpack(packs / (filename[:-4] + ".pack"), offset, kind, depth)
                    break
            else:
                raise ValueError
        digest = hashlib.sha1() if self.width == 20 else hashlib.sha256()
        digest.update(kind + b" " + str(len(data)).encode("ascii") + b"\0")
        digest.update(data)
        if digest.digest() != oid:
            raise ValueError
        return data

    def unpack(self, pack, offset, kind, depth):
        if offset < 12 or depth > 64:
            raise ValueError
        with os.fdopen(open_input(pack), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError
            stream.seek(offset)
            first = stream.read(1)[0]
            form, size = (first >> 4) & 7, first & 15
            byte, shift = first, 4
            while byte & 128:
                byte = stream.read(1)[0]
                size |= (byte & 127) << shift
                shift += 7
                if size > LIMIT or shift > 32:
                    raise ValueError
            if form == (1 if kind == b"commit" else 2):
                base = None
            elif form == 6:
                byte = stream.read(1)[0]
                distance = byte & 127
                while byte & 128:
                    byte = stream.read(1)[0]
                    distance = ((distance + 1) << 7) | (byte & 127)
                    if distance > offset:
                        raise ValueError
                if not distance:
                    raise ValueError
                base = self.unpack(pack, offset - distance, kind, depth + 1)
            elif form == 7:
                base = self.read(stream.read(self.width), kind, depth + 1)
            else:
                raise ValueError
            body = inflate(stream, size)
            if len(body) != size:
                raise ValueError
        return body if base is None else apply_delta(base, body)


def committed_files(gitdir, tracked):
    if not tracked:
        return {}
    width = len(next(iter(tracked.values())))
    try:
        common = gitdir / os.fsdecode(metadata(gitdir / "commondir", 8192)).removesuffix("\n")
    except FileNotFoundError:
        common = gitdir
    objects = GitObjects(common / "objects", width)
    revision = head_commit(gitdir, common, width)
    commit = objects.read(revision, b"commit")
    header = commit.split(b"\n", 1)[0]
    if not header.startswith(b"tree "):
        return {}
    root = object_id(header[5:], width)
    wanted = {}
    for path in tracked:
        branch = wanted
        parts = path.split(b"/")
        for part in parts[:-1]:
            branch = branch.setdefault(part, {})
        branch[parts[-1]] = path
    pending, verified = [(root, wanted)], {}
    while pending:
        oid, branch = pending.pop()
        try:
            tree = objects.read(oid, b"tree")
            entries = tree_matches(tree, width, branch)
        except (OSError, ValueError, IndexError):
            continue
        for name, (mode, entry) in entries.items():
            match = branch[name]
            if mode == b"40000" and isinstance(match, dict):
                pending.append((entry, match))
            elif mode in (b"100644", b"100755") and isinstance(match, bytes) and tracked[match] == entry:
                verified[match] = entry
    return verified if head_commit(gitdir, common, width) == revision else {}


def tree_matches(tree, width, wanted):
    entries, pos = {}, 0
    while pos < len(tree):
        space = tree.index(b" ", pos)
        nul = tree.index(b"\0", space + 1)
        mode, name = tree[pos:space], tree[space + 1:nul]
        pos = nul + 1 + width
        if pos > len(tree) or not name or b"/" in name or name in entries:
            raise ValueError
        if name in wanted:
            entries[name] = mode, tree[nul + 1:pos]
    return entries
