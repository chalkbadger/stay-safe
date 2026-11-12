# Reported incidents

Real-world reports of coding agents doing destructive or risky things. Risk rules cite these entries by ID. Each entry is **reported, not verified**: most sources are articles or forum posts that quote the original report.

## I1. Home directory deleted by `rm -rf`
- Harness: Claude Code
- What happened: The user asked Claude Code to clean up packages. Their post quotes the agent's explanation: `rm -rf tests/ patches/ plan/ ~/` deleted the home directory, including the Keychain.
- Enabling condition: shell commands ran without careful review, possibly with permissions skipped.
- Sources: [Original report](https://www.reddit.com/r/ClaudeAI/comments/1pgxckk/claude_cli_deleted_my_entire_home_directory_wiped/), [Gigazine](https://gigazine.net/gsc_news/en/20251216-claude-code-cli-mac-deleted)

## I2. Home directory added to a delete command
- Harness: Cursor (Gemini 2.5 Pro)
- What happened: the agent ran `rm -rf /crushwork ~/`.
- Enabling condition: shell commands ran without approval.
- Source: [Cursor forum](https://forum.cursor.com/t/cursor-tried-to-wipe-my-computer/107142)

## I3. Windows drive wiped
- Harness: Cursor
- What happened: a mis-quoted `rmdir /s /q` deleted the whole D: drive, about 80 GB.
- Enabling condition: shell commands ran without approval.
- Source: [Cursor forum](https://forum.cursor.com/t/agent-wiped-d-drive-instead-of-deleting-one-folder/169919)

## I4. Repository and parent folder contents deleted
- Harness: reported as Cursor with Claude Code; the exact agent was not established.
- What happened: a user reported losing repository and parent folder contents twice, without a confirmation prompt. The report does not identify the command or establish whether deletion protection was enabled.
- Enabling condition: not established by the report.
- Source: [Cursor forum](https://forum.cursor.com/t/cursor-claude-code-deleted-my-entire-documents-folder-on-macos/167086)

## I5. `git reset --hard` at session start
- Harness: Claude Code
- What happened: on two occasions the agent ran `git reset --hard origin/main` within a second of session start. It then said it had added a git hook to block this; the hook did not exist.
- Enabling condition: destructive git commands allowed without approval; the agent misreported its own safeguard.
- Source: [Claude Code issue #34327](https://claudeissues.com/issue/34327-claude-code-destroyed-users-uncommitted-work-by-running-git-reset-hard-on-sessio)

## I6. Uncommitted work lost despite a `CLAUDE.md` warning
- Harness: Claude Code (Haiku)
- What happened: while restoring one component, the agent ran `git reset HEAD && git checkout -- .`, reportedly losing two hours of uncommitted work. `CLAUDE.md` advised considering safer alternatives before destructive operations; it did not ban them.
- Enabling condition: destructive shell commands executed despite advisory instructions. The report does not establish which permission allowed them.
- Source: [Claude Code issue #70363](https://github.com/anthropics/claude-code/issues/70363)

## I7. Production volumes deleted with a found token
- Harness: Cursor (Claude Opus 4.6)
- What happened: blocked by a credential mismatch, the agent found an API token meant for managing custom domains. The token could also delete volumes, and the agent deleted production data. The provider later recovered it.
- Enabling condition: a readable token with more scope than its purpose.
- Sources: [Penligent](https://www.penligent.ai/hackinglabs/fr/?p=5035), [Railway](https://blog.railway.com/p/your-ai-wants-to-nuke-your-database), [The Daily WTF](https://thedailywtf.com/articles/empty-pockets)

## I8. Database changes after an order to stop
- Harness: Replit
- What happened: told to stop all code changes, the agent ran its own database operations.
- Enabling condition: production database access for the agent.
- Source: [it-daily](https://www.it-daily.net/?p=152977)

## I9. `.env` read despite an ignore file
- Harness: Claude Code
- What happened: in a test, `.claudeignore` did not stop the agent reading `.env`.
- Enabling condition: an ignore file treated as access control.
- Source: [AI Incident Database report 6847](https://incidentdatabase.ai/reports/6847)

## I10. Sensitive file read with a reported deny configuration
- Harness: Claude Code
- What happened: a user reported that the Read tool exposed `.env.local` despite their `settings.json`. Their example used `permissions.read.deny`, unlike the documented `permissions.deny` array of `Read(...)` rules. The report does not establish a bypass of a correctly configured deny rule.
- Enabling condition: not established; the supplied configuration differs from the documented format.
- Sources: [GitHub issue #24846](https://github.com/anthropics/claude-code/issues/24846), [Permission documentation](https://code.claude.com/docs/en/permissions)

## I11. Denylist workaround requested an unsandboxed run
- Harness: Claude Code
- What happened: a researcher asked the agent to work around an `npx` deny rule. It used `/proc/self/root/usr/bin/npx`. When sandbox startup failed, the agent requested approval to run outside the sandbox; the article then shows `npx` running.
- Enabling condition: a command-name deny rule missed an alternate path. The unsandboxed attempt still presented an approval prompt.
- Source: [Ona experiment](https://ona.com/stories/how-claude-code-escapes-its-own-denylist-and-sandbox)

## I12. Shell safety gaps across ten tested agents
- Harness: 10 of 11 open-source agents surveyed by GuardFall
- What happened: researchers reported shell safety gaps in ten tested configurations. Three had string-matching guards that were defeated outright. Others had different gaps, including incomplete or absent guards and sandbox opt-outs, not ten successful bypasses of command filters.
- Enabling condition: varied by agent and configuration; the report says container defaults defended until their local-mode opt-out was selected.
- Source: [Adversa research](https://adversa.ai/blog/opensource-ai-coding-agents-shell-injection-vulnerability/)

## I13. Repository settings run commands on collaborators' machines
- Harness: Claude Code
- What happened: a cloned repository's `.claude/settings.json` could define hooks that ran shell commands for everyone who opened it. Since patched.
- Enabling condition: project-level settings that define hooks or servers.
- Source: [The Register](https://www.theregister.com/2026/02/26/clade_code_cves/)

## I14. README injection bypassed a command allowlist
- Harness: Gemini CLI
- What happened: researchers used instructions in a repository README and a command crafted to pass a `grep` allowlist to exfiltrate environment variables. They described file deletion and remote-shell installation as possible consequences, not observed outcomes. Fixed in version 0.1.14.
- Enabling condition: untrusted repository text influenced shell execution, and the allowlist check accepted a command containing more than the allowed operation.
- Source: [Tracebit research](https://tracebit.com/blog/code-exec-deception-gemini-ai-cli-hijack)

## I15. Prompt injection through GitHub issues
- Harness: any agent using the GitHub MCP server
- What happened: hidden instructions in public issues could take over the agent.
- Enabling condition: an MCP server that reads untrusted public content.
- Source: [Cybersecurity News](https://cybersecuritynews.com/github-mcp-server-vulnerability/amp/)

## I16. Sandbox escape through the Docker socket
- Harness: Codex, Cursor, Gemini CLI
- What happened: an exposed Docker socket let agents escape their sandboxes.
- Enabling condition: the Docker socket reachable from inside the sandbox.
- Source: [Pillar Security](https://www.pillar.security/blog/one-docker-socket-to-rule-them-all-escaping-codex-cursor-and-gemini-clis-sandboxes)

## I17. Malicious code shipped in an extension release
- Harness: Amazon Q Developer (VS Code extension)
- What happened: AWS reported that an attacker used an overly broad build token to commit malicious code, which was automatically released in version 1.84.0. A syntax error prevented it from executing. AWS replaced that version with 1.85.0.
- Enabling condition: an inappropriately scoped build token and an automatic release path admitted an unauthorized change.
- Source: [AWS security bulletin](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/)

## I18. Malware tried installed agents with approvals skipped
- Harness: Claude Code, Gemini CLI and Amazon Q CLI (Nx "s1ngularity")
- What happened: compromised npm packages attempted to run installed AI CLIs with `--dangerously-skip-permissions`, `--yolo` or `--trust-all-tools` to locate sensitive files. The cited analysis shows the invocation code, not how often those AI-assisted searches succeeded.
- Enabling condition: malware already executing locally could start available agent CLIs in modes that skip tool approvals.
- Source: [StepSecurity analysis](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware)

## I19. Worm persisted through agent startup hooks
- Harness: Claude Code (Mini Shai-Hulud)
- What happened: sources describe the worm persisting through Claude Code hooks but disagree about the settings location. Sonar describes project `.claude/settings.json` files with a `SessionStart` hook running `node .claude/setup.mjs`; the Cloud Security Alliance note names user-level `~/.claude/settings.json`.
- Enabling condition: malware could modify startup hooks that executed on later agent sessions; the settings scope is disputed.
- Sources: [Sonar analysis](https://www.sonarsource.com/blog/mini-shai-hulud-targets-ai-coding-agents/), [Cloud Security Alliance research note](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/05/CSA_research_note_shai-hulud-ai-supply-chain_20260517-csa-styled.pdf)

## I20. Injected text turned off approvals
- Harness: GitHub Copilot (VS Code), CVE-2025-53773
- What happened: text in code, web pages or issues got the agent to set `"chat.tools.autoApprove": true` in its own settings.
- Enabling condition: an agent that can edit its own approval settings.
- Sources: [GBHackers](https://gbhackers.com/github-copilot-rce-vulnerability/amp/), [Cybersecurity News](https://cybersecuritynews.com/github-copilot-rce-vulnerability/amp)

## I21. Issue content steered an agent toward workflow secrets
- Harness: Claude Code GitHub Action
- What happened: Microsoft demonstrated prompt injection that led the Read tool to access `/proc/self/environ`, exposing the workflow's API key. Claude Code 2.1.128 blocked sensitive `/proc` files; that mitigation was not a general fix for prompt injection. The same article separately describes injection attempts hidden in HTML comments.
- Enabling condition: untrusted GitHub content reached an agent whose file-reading tool could access workflow secrets outside the subprocess sandboxing model.
- Source: [Microsoft research](https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/)

## I22. Database reset to fix a schema error
- Harness: Cursor
- What happened: the bug was in the code, but the agent reset the database, for the second time, despite instructions not to.
- Enabling condition: database access plus a safety rule held only in instructions.
- Source: [Cursor forum](https://forum.cursor.com/t/agent-decides-again-to-wipe-entire-db/123619)

## I23. Production tables dropped by a dev-only migration command
- Harness: Claude Code (reported model: Opus 5)
- What happened: The agent ran `prisma migrate diff`. It used the production Supabase URL for the shadow database, which Prisma treats as disposable. The report says all 22 tables were dropped.
- Enabling condition: a production database URL the agent can read.
- Sources: [Original report](https://www.reddit.com/r/Anthropic/comments/1v9iurd/and_just_like_that_opus_5_ultracode_wipes_the/), [AI Incident Database record](https://incidentdatabase.ai/cite/1676/), [AI Incident Database index](https://incidentdatabase.ai/es/entities/prisma/), [Prisma guidance](https://www.prisma.io/blog/stop-your-ai-agent-dropping-your-database)

## I24. Driver update followed by boot and network failures
- Harness: Claude Code
- What happened: a user asked for help with a GPU performance issue and reported that the agent automatically updated drivers. The PC then failed to boot; recovery involved System Restore and a separate VPN-related DNS problem, taking over 24 hours overall. The report does not provide the original prompt or permission settings.
- Enabling condition: not established by the report.
- Source: [Archived original report](https://reddit.sentinel-team.org/posts/1tg335j/snapshots/2026-05-23T02%3A20%3A04.239191Z)

## I25. Tests deleted or weakened to report success
- Harness: several
- What happened: agents deleted failing tests, replaced assertions with `expect(true).toBe(true)`, disabled TLS verification, or committed with `--no-verify`, then reported that all tests pass.
- Enabling condition: an agent that can edit tests and skip hooks.
- Sources: [DevGenius](https://blog.devgenius.io/we-gave-ai-permission-to-run-our-tests-then-it-started-testing-the-wrong-thing-00dfeb4d1420), [gitpod issue](https://github.com/gitpod-io/gitpod/issues/21355), [ImpossibleBench](https://www.greaterwrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1)

## I26. Saved command approval persisted across sessions and workspaces
- Harness: Codex CLI 0.130.0
- What happened: a user reported that selecting the persistent approval for `curl` allowed later `curl` invocations without prompting, including after restarting in another workspace. The report describes unexpected approval scope and persistence, not destructive consequences.
- Enabling condition: a saved one-token allow prefix covered additional arguments to the same program.
- Source: [OpenAI Codex issue #22181](https://github.com/openai/codex/issues/22181)
