# stay-safe

stay-safe helps people check their Codex files for risky settings. Its report
explains each warning and suggests what to do.

It reads settings and saved approvals from files. Only some settings are covered.
It does not test live connections or what Codex will actually allow. The
[full scope](report.md#full-scope) explains the limits.

## How review works

Open source makes the code inspectable. stay-safe also makes its claims challengeable,
and a challenge outlives the maintainer's verdict.

- **Claims are explicit.** Every risk rule states what it flags and cites the
  [incidents](../incidents.md) behind it. Every lab result is a claim with its runs.
- **Challenges and runs belong to their authors.** Each is a self-contained record:
  what it points at, the revision, the evidence and who made it. It can be posted as a
  stay-safe issue or published anywhere else, and it stays visible beside the claim
  whatever the maintainer decides.
- **Evidence settles disputes.** A configuration rule changes when a challenge adds a
  fixture its tests fail on. A lab result changes when re-runnable runs contradict it.
  The maintainer's response sits beside the challenge rather than replacing it.
- **Users review while using it.** When someone questions a finding or recounts an
  incident in the diagnostic conversation, the agent offers to draft the record, and
  posts it only with their approval.
- **Independence is labeled:** same owner, different owner, or unknown, and
  "independence unverified" unless shown otherwise.
- **Danger is shown, not done.** Attacks run only in a contained lab where every
  target is a tripwire. Reports state what would have happened.
- **Rules are maintained centrally; evidence is not.** The maintainer merges rule
  changes. Anyone may fork the rules, and a fork's results can be shown side by side.

## What the report shows

- **What it found.** The report shows what stay-safe found in the files it read.
  It names the defaults it used.
- **What the settings mean.** The [meanings table](../harnesses/codex.md) lists
  the settings stay-safe checks and the Codex sources it uses.
- **What remains unknown.** The report says when it could not complete a check.
  A report with no warnings does not mean the setup is safe.
