## Unreleased compatibility follow-up

- Validate Spec Kit1.2.2 native project selection, persisted feature pointers,
  environment overrides, integration state and numbered feature paths.
- Return JSON diagnostics for malformed metadata; reject unsafe feature paths.
- Preserve script-family health checks and task bookkeeping without acceptance claims.
- Keep Bash and PowerShell on a shared Python engine, with Python3.9+ required.
- Retain existing PR regression coverage and add native state/no-write fixtures.
- Document maintained fork installation and inherited license metadata limitations.

# Changelog

## Unreleased

- Recognize current script directories and Codex Spec Kit skills; retain legacy prompts.
- Select explicitly, then by environment, then by numbered branch; reject ambiguous
  or missing matches and remove the silent latest-feature fallback.
- Return JSON without status chatter, plus an all-feature task summary.
- Ignore fenced checkbox examples and separate checked bookkeeping from acceptance.
- Add shared Bash/PowerShell fixture contracts; PowerShell runtime tests explicitly
  skip when pwsh is unavailable, rather than claiming verified parity.

## v1.0.0 (2026-03-16)

- Initial release
- Project info: name, AI agent detection, script type
- Current feature detection (git branch, SPECIFY_FEATURE env var, specs/ scan)
- SDD artifact status (spec.md, plan.md, tasks.md, research.md, data-model.md, quickstart.md, contracts/, checklists/)
- Task progress parsing (completed/total with percentage)
- Workflow phase detection (Not Started → Plan → Tasks → Implement → Complete)
- Extensions summary (installed count)
- Full bash/PowerShell parity with JSON output
