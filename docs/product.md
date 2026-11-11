# stay-safe

stay-safe gives people a shareable diagnostic of supported Codex settings and saved
approval records from inspected files, with documented defaults, related risks and
detected inspection gaps. Findings cite reported incidents; the
[full scope](report.md#full-scope) states the inspection boundary.

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

- **Configured observations.** Within the [full scope](report.md#full-scope), the
  report names supported connections and permissions from inspected files, includes
  documented defaults, and lists detected inspection gaps.
- **How settings are interpreted.** The [meanings table](../harnesses/codex.md)
  identifies supported settings and cites Codex's sources for their interpretation.
- **No silent all-clear.** A report without a finding does not establish that the
  setup is safe; the [full scope](report.md#full-scope) explains what remains uninspected.
