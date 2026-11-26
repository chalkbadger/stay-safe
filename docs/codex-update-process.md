# Check new Codex releases

Run this from a stay-safe checkout with Python 3.11 or newer and Git. First prepare
a Codex source checkout; no Codex executable or release API is needed:

```sh
git clone --filter=blob:none --no-checkout https://github.com/openai/codex.git ../codex-source
git -C ../codex-source fetch --tags origin
python3 scripts/codex_drift.py --codex-repo ../codex-source > codex-release-scan.md
```

Reuse that checkout on later runs, fetching tags again before scanning. The checker
uses the stable tags present locally, sorted by version, and starts after
`last_scanned_tag` in [the progress record](codex-scan-state.json). `--from-tag` and
`--to-tag` select an explicit range, for example:

```sh
python3 scripts/codex_drift.py --codex-repo ../codex-source \
  --from-tag rust-v0.167.0 --to-tag rust-v0.172.0 > codex-release-scan.md
```

Exit 0 means the scan completed; exit 2 names an input or Git failure. The checker
writes only its report to stdout and never advances progress. A partial clone can
fetch missing blobs when Git reads them.

## Review the result

Each release lists changes to the [meanings table's](../harnesses/codex.md) cited
source ranges, with labels and diff hunks, plus added, removed and changed schema
fields. Local schema references become setting paths; `*` means a named entry and
`[]` means an array item. Recursive references stop at their first repeat.

Line ranges are mapped from each citation's own revision, so earlier insertions
do not count as changes to the cited text. Boundary insertions are included for
review. A source file added or deleted between releases appears as a diff; a
missing citation at its pinned revision or a missing schema fails the scan.

Read the changed code and its callers before deciding whether a meaning changed.
Unchanged cited lines do not establish unchanged behavior. Keep old meanings where
older releases differ, and record each reviewed range beside its source evidence.
Do not replace every pin or extend every row's range from a clean drift result.

After a complete scan, retain its output and unresolved findings in the review PR,
then update `last_scanned_tag` and its commit in the progress record. That records
where scanning stopped; reviewed behavior remains in the meanings table.

The [progress record](codex-scan-state.json) lists completed field reviews by release under
`field_reviews`. The [0.172.0 field review](codex-0.172.0-fields.md) shows how to read the results. Add the
next review under its own release tag so earlier evidence stays available.

## Add to the existing scheduled task

```text
Before the roundup, fetch the stable tags from openai/codex. Read stay-safe's
docs/codex-update-process.md and docs/codex-scan-state.json, then run the documented
Codex release scan from the last scanned tag. Include every new stable release.
Report changed citation labels with their diff hunks, and added, removed or changed
configuration fields. Read the relevant code and callers; distinguish behavior
changes, source-only maintenance and unchecked settings. Preserve older version
meanings. Retain the complete scan output and unresolved findings in a review PR
before updating the scan point. Do not mark behavior reviewed merely because the
scan completed, and do not merge changes. If a required source or step is unavailable,
name it and leave the scan point unchanged.
```

This addendum belongs in the existing release task; it does not create a second
schedule or replace the rest of its roundup instructions.
