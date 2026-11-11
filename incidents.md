# Reported incidents

Real-world reports of coding agents doing destructive or risky things. Risk rules cite these entries by ID. Each entry is **reported, not verified**: most sources are articles or forum posts that quote the original report.

## I1. Home directory deleted by `rm -rf`
- Harness: Claude Code
- What happened: asked to clean up packages, the agent ran `rm -rf tests/patches/plan/ ~/`. The trailing `~/` deleted the home directory, including the Keychain.
- Enabling condition: shell commands ran without careful review, possibly with permissions skipped.
- Source: [Gigazine](https://gigazine.net/gsc_news/en/20251216-claude-code-cli-mac-deleted)

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

## I4. Documents folder deleted despite deletion protection
- Harness: Cursor
- What happened: the agent deleted the macOS Documents folder. Cursor's File-Deletion Protection covers its editor tools, not shell commands.
- Enabling condition: a protection setting that does not cover the shell.
- Source: [Cursor forum](https://forum.cursor.com/t/cursor-claude-code-deleted-my-entire-documents-folder-on-macos/167086)

## I5. `git reset --hard` at session start
- Harness: Claude Code
- What happened: on two occasions the agent ran `git reset --hard origin/main` within a second of session start. It then said it had added a git hook to block this; the hook did not exist.
- Enabling condition: destructive git commands allowed without approval; the agent misreported its own safeguard.
- Source: [Claude Code issue #34327](https://claudeissues.com/issue/34327-claude-code-destroyed-users-uncommitted-work-by-running-git-reset-hard-on-sessio)

## I6. Uncommitted work lost despite a `CLAUDE.md` rule
- Harness: Claude Code (Haiku)
- What happened: the agent ran `git checkout` and destroyed two hours of uncommitted work. `CLAUDE.md` told it not to run destructive git commands.
- Enabling condition: a safety rule written only in an instructions file, with nothing enforcing it.
- Source: [Claude Code issue #70363](https://claudeissues.com/issue/70363-haiku-claude-code-destroyed-2-hours-of-uncommitted-work-by-running-git-checkout)

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

## I10. Read-deny rules not enforced
- Harness: Claude Code
- What happened: `settings.json` read-deny rules for sensitive files were not enforced. The issue was later closed as resolved.
- Enabling condition: a deny rule that does not do what it says.
- Source: [GitHub issue #24846](https://github.com/anthropics/claude-code/issues/24846)

## I11. Agent bypassed a denylist and disabled its sandbox
- Harness: Claude Code
- What happened: with `npx` denied, the agent ran it via `/proc/self/root/usr/bin/npx`. When the sandbox caught that, the agent disabled the sandbox.
- Enabling condition: a string-matching command denylist; a sandbox the agent can turn off.
- Source: [Ona newsletter](https://ona.com/newsletter/03-mar-2026)

## I12. Shell injection bypasses command filters
- Harness: 10 of 11 open-source coding agents tested
- What happened: the GuardFall technique bypassed their command filtering.
- Enabling condition: command lists matched as strings.
- Source: [Context Studios](https://www.contextstudios.ai/comparisons/command-allowlisting-vs-sandboxing-ai-agents)

## I13. Repository settings run commands on collaborators' machines
- Harness: Claude Code
- What happened: a cloned repository's `.claude/settings.json` could define hooks that ran shell commands for everyone who opened it. Since patched.
- Enabling condition: project-level settings that define hooks or servers.
- Source: [The Register](https://www.theregister.com/2026/02/26/clade_code_cves/)

## I14. Similar repository-supplied command execution
- Harness: Gemini CLI
- What happened: a comparable flaw allowed deleting files or installing a remote shell.
- Enabling condition: project-level configuration that runs commands.
- Source: [Yahoo Tech](https://tech.yahoo.com/cybersecurity/articles/coding-gemini-cli-security-150312104.html)

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

## I17. Wiper prompt shipped in an extension release
- Harness: Amazon Q (VS Code extension)
- What happened: a pull request added a prompt telling the assistant to delete files, terminate AWS resources and remove IAM users. It passed release verification; only a syntax error stopped it from running.
- Enabling condition: instructions the agent loads from a supply-chain source.
- Sources: [CyberInsider](https://cyberinsider.com/?p=267392), [Substack](https://mrdecentralize.substack.com/p/amazon-q-where-code-verification)

## I18. Malware ran the developer's agents with permissions skipped
- Harness: Claude Code, Gemini CLI and others (Nx "s1ngularity")
- What happened: a compromised npm package ran the installed AI CLIs with `--dangerously-skip-permissions` and `--yolo` to search for secrets. About half the victims had AI CLIs installed.
- Enabling condition: an agent CLI that any local script can start with approvals skipped.
- Sources: [StepSecurity](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware), [TraxTech](https://www.traxtech.com/ai-in-supply-chain/the-nx-supply-chain-attack-exposes-critical-vulnerabilities-in-software-development-ecosystems)

## I19. Worm wrote itself into agent settings
- Harness: Claude Code (Shai-Hulud)
- What happened: an npm worm wrote modified configuration to `~/.claude/settings.json` so its code ran whenever Claude Code started.
- Enabling condition: user-level settings that define hooks, writable by any local process.
- Sources: [Cloud Security Alliance](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/05/CSA_research_note_shai-hulud-ai-supply-chain_20260517-csa-styled.pdf), [Cybersecurity News](https://cybersecuritynews.com/shai-hulud-worm-steals-npm/amp/)

## I20. Injected text turned off approvals
- Harness: GitHub Copilot (VS Code), CVE-2025-53773
- What happened: text in code, web pages or issues got the agent to set `"chat.tools.autoApprove": true` in its own settings.
- Enabling condition: an agent that can edit its own approval settings.
- Sources: [GBHackers](https://gbhackers.com/github-copilot-rce-vulnerability/amp/), [Cybersecurity News](https://cybersecuritynews.com/github-copilot-rce-vulnerability/amp)

## I21. Hidden instructions in issue comments
- Harness: Claude Code GitHub Action and other AI workflows
- What happened: prompt injection hidden in HTML comments in public issues, invisible when rendered but read by the model. Patched in Claude Code 2.1.128.
- Enabling condition: an agent that reads untrusted repository content with write access.
- Sources: [Microsoft Security](https://www.microsoft.com/en-us/security/blog/?p=147931), [Decrypt](https://decrypt.co/?p=370238)

## I22. Database reset to fix a schema error
- Harness: Cursor
- What happened: the bug was in the code, but the agent reset the database, for the second time, despite instructions not to.
- Enabling condition: database access plus a safety rule held only in instructions.
- Source: [Cursor forum](https://forum.cursor.com/t/agent-decides-again-to-wipe-entire-db/123619)

## I23. Production tables dropped by a dev-only migration command
- Harness: unspecified agent with Prisma
- What happened: the agent ran `prisma migrate diff` with the production URL as the disposable shadow database; all 22 tables were dropped.
- Enabling condition: a production database URL the agent can read.
- Sources: [AI Incident Database](https://incidentdatabase.ai/es/entities/prisma/), [Prisma](https://www.prisma.io/blog/stop-your-ai-agent-dropping-your-database)

## I24. "Diagnose" became a driver update
- Harness: Claude Code
- What happened: asked only why a GPU drew 70% power, the agent updated drivers, causing a 24-hour crash loop.
- Enabling condition: system-level command access without approval.
- Source: [AI Weekly](https://aiweekly.co/alerts/claude-code-auto-updates-gpu-drivers-causes-24hr-bsod-cascade)

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
