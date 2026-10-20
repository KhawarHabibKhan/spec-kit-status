# Spec Kit Status

A read-only Spec Kit extension showing local artifacts and task bookkeeping.
It does not query GitHub, grant implementation authorization, or assess acceptance.

## Installation

The catalog and upstream v1.0.0 tag still contain the old implementation.
Install this maintained compatibility branch explicitly:

```bash
specify extension add status --from https://github.com/3pepe3/spec-kit-status/archive/refs/heads/fix/current-speckit-layout.zip
```

For reproducible installations, replace the branch archive with a reviewed
commit archive (`https://github.com/3pepe3/spec-kit-status/archive/<commit>.zip`).
Use `--force` only when intentionally replacing an installation after preserving
local customizations. Local development uses `specify extension add /path/to/checkout --dev`.

## Usage

Use `/speckit.status.show` (alias `/speckit.status`), optionally followed by a
feature selector such as `003` or `003-media`. The command instructions pass the
selector to the script. For Codex installations that expose extension commands
as skills, use `$speckit-status-show` (alias `$speckit-status`) with the same
optional selector. To invoke scripts directly from this extension checkout:

```bash
bash scripts/bash/status.sh --feature 003
```

```powershell
./scripts/powershell/status.ps1 -Feature 003
```

Scripts inspect the nearest ancestor containing `.specify/`, or the directory
selected by `SPECIFY_INIT_DIR`. Select a feature in this order:

1. Explicit `--feature` / `-Feature` argument.
2. `SPECIFY_FEATURE_DIRECTORY` native directory override.
3. `.specify/feature.json` native `feature_directory` pointer.
4. Legacy `SPECIFY_FEATURE` environment variable.
5. Legacy numbered Git branch, only when no native context exists.

Native directory selections accept `specs/NNN-name` or its absolute path. They must name an existing numbered directory directly under `specs/`; symlinked, missing and outside paths fail. The explicit feature argument and legacy selections accept `NNN` or `NNN-name`. An exact `specs/NNN-name/` directory wins; otherwise the three-digit prefix must
match one directory. Invalid, missing or ambiguous selections return a JSON
error and nonzero exit. Without a selector, main/master, detached HEAD and
non-Git projects show the all-feature summary and `phase: no_feature`. There is
no latest-feature fallback. Bash `--help` / `-h` and PowerShell `-Help` print usage instead of JSON. Bash `--json` and PowerShell `-Json` are accepted; regular output is already JSON. `PYTHON` can select one Python executable path.

## Output and scope

Normal output is a single JSON document, including errors detected by the script.
It includes project/branch information, agent discovery, `script_type`, selected
feature artifacts/tasks/phase, `features` for every numbered directory and an
aggregate `summary`. Empty task files report `no_tasks` / `ROADMAP_PENDING`.
All checked tasks report `tasks_checked`, never acceptance: `acceptance` is
always `NOT_ASSESSED`, and `live_status` is always `NOT_QUERIED`.

Task and checklist counters recognize `- [ ]`, `- [x]` and `- [X]` (also `*` bullet forms) followed by
whitespace or end of line. Backtick and tilde fenced examples, including longer
fences, are excluded. These are Markdown checkbox counts, not validation of task
IDs, prerequisites, acceptance evidence or complete Markdown semantics.

Current layouts `.specify/scripts/bash/`, `.specify/scripts/powershell/` and
Codex `.agents/skills/speckit-*/SKILL.md` are recognized. Legacy Codex
`.codex/prompts/` commands remain supported. Shared `.agents/skills/` alone does
not identify Amp; Amp requires `.agents/commands/`.

Installed extensions are counted from `.specify/extensions/.registry`'s
`extensions` object. A missing registry reports `null`; malformed JSON or
unsupported container/entry shapes fail. Optional native integration state and
feature pointers are type-checked. All diagnostics remain local and read-only.
Both platform wrappers use the same `scripts/status.py` engine; `jq` is not required.

## Requirements and verification

Verified against Spec Kit1.2.2. Python3.9+ is required, with Bash or PowerShell
for its corresponding wrapper. Git is optional for normal use and required by
the fixture suite. Python/startup failures are tooling failures; valid CLI
options produce one JSON object and exit0 on success or1 on scan errors.
Invalid CLI arguments use the parser's exit2 and usage output.

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/bash/status.sh
```

The same fixture contract runs against PowerShell when `pwsh` is installed;
otherwise those tests explicitly skip. PowerShell source has been updated for
parity, but runtime parity is unverified in environments without that runtime.

Source/license metadata and its inherited limitation are recorded in [NOTICE.md](NOTICE.md).
