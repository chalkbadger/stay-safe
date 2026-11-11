# stay-safe

stay-safe shows people what their coding agent is connected to, what is risky about
that setup, and what agents like theirs have actually done, as a diagnostic they can
share.

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

- **What can change a finding.** The report names every connection (where code or
  data can go) and each permission that can change a risk it shows. An inspection gap
  appears only for a problem that could change a finding.
- **What Codex would do.** Where Codex's source is clear, stay-safe reads a setting
  the same way and cites the source in the [meanings table](../harnesses/codex.md).
- **No silent all-clear.** When stay-safe can't tell, it shows the risk or a gap. A
  report without a finding never implies a safety it can't support.
