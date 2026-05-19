# Maintenance

This document explains how the revival branch keeps The Book of Secret Knowledge useful without turning it into a dumping ground.

## Revival Goal

The goal is not to add every possible link. The goal is to keep a practical, high-signal technical collection that a system administrator, DevOps engineer, security researcher, developer, or operator can use during real work.

The revival has four tracks:

1. Fix dead or moved links.
2. Add modern tools that have clear operational value.
3. Remove deprecated, abandoned, duplicated, unsafe, or low-signal resources.
4. Keep categories navigable enough that readers can find the right resource quickly.

## Current Backlog Reality

At the start of this revival pass, the live upstream repository showed no open issues and a large open pull request backlog. Some older references to "open issues" are therefore stale: the active queue to clear is pull requests, not issues.

Use `scripts/pr_backlog_report.py` to generate a current maintainer snapshot:

```bash
python scripts/pr_backlog_report.py --repo trimstray/the-book-of-secret-knowledge
```

## Curation Policy

Every accepted resource should satisfy these checks:

- The URL works or has a documented replacement.
- The project, guide, or list has clear technical value.
- The description is short, neutral, and useful.
- The resource is in the category where a reader would naturally look for it.
- The resource is not already listed under a different name.
- The page is not mainly affiliate, SEO, tracking, or lead-generation content.

Security and hacking resources must be framed as educational, defensive, lab, research, or legitimate testing material. Resources that are mainly abuse tooling without legitimate context should not be added.

## Dead-Link Handling

Dead links should be handled in this order:

1. Replace moved projects with their canonical maintained URL.
2. Replace old product pages with official documentation when the product still exists.
3. Mark uncertain outages with `*` and revisit them later.
4. Remove links that are permanently gone, hostile, hijacked, deprecated, or no longer useful.

Run:

```bash
python scripts/check_links.py README.md
```

The checker fails on hard broken links and missing local files. Transient HTTP responses such as rate limits, forbidden responses, and gateway timeouts are reported separately because many large sites block automated probes.

## Pull Request Triage

Use this decision path for the backlog:

1. Single good link, correct category, working URL: merge after style check.
2. Good link, wrong category or wording: edit or request a small change.
3. Duplicate resource: close with the existing entry linked.
4. Promotional or low-signal resource: close with the curation rule cited.
5. Broad mixed PR: ask for a split or recreate the useful subset in a maintainer branch.
6. Stale PR with conflicts: recreate the useful change manually and close the stale PR with credit.

Do not clear the backlog by closing everything. Clear it by deciding every item.

## Release Process

The fork should use calendar-style revival releases:

- `v2026.05-revival.1` for the first maintenance release.
- `v2026.05-revival.2` for follow-up batches in the same month.
- Continue monthly only when there are meaningful curated changes.

Before cutting a release:

1. Run the link checker against edited Markdown files.
2. Generate or update the pull request backlog report.
3. Confirm the changelog names dead-link fixes, additions, removals, and maintenance changes.
4. Tag the release from a clean working tree.

Suggested release command after GitHub authentication is available:

```bash
gh release create v2026.05-revival.1 --title "Revival 2026.05.1" --notes-file RELEASE_NOTES.md
```

## Ownership Model

The maintainer role is to protect the signal of the collection. That means saying no to weak additions, removing stale resources when evidence supports removal, and keeping automation strict enough to prevent quiet decay.
