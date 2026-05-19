# Revival 2026.05.1

This release starts the maintained revival of The Book of Secret Knowledge.

## Highlights

- Adds `MAINTENANCE.md` with the revival policy, dead-link process, PR triage model, and release process.
- Adds contribution guidance and issue/PR templates so incoming suggestions are reviewable.
- Adds a dependency-free link checker and GitHub Actions workflow for Markdown link validation.
- Adds a maintainer PR backlog report script for clearing the open PR queue with evidence.
- Begins README curation by updating moved/deprecated links and adding modern operational tools across CLI, DNS, HTTP, terminals, diagnostics, and containers.
- Replaces stale entries for curl, HTTPie, impacket, iptraf-ng, Panopticlick, and xip.io, and removes archived namebench from active DNS tooling.
- Clears the hard-dead links found by the first full local audit: the latest report checks 1001 unique links with 0 hard failures and records transient or bot-blocked sites separately.
- Includes `docs/triage/open-pr-backlog.md` with the current upstream PR backlog snapshot for maintainer triage.

## Maintainer Notes

The current live upstream backlog is pull requests, not issues. The revival should clear the backlog by merging good submissions, closing weak submissions with reasons, and recreating useful stale changes manually when needed.
