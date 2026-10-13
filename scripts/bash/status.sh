#!/usr/bin/env bash
set -e

# ============================================================================
# Spec Kit Status — Show project status and SDD workflow progress
# ============================================================================

# --- Helpers ----------------------------------------------------------------

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\r'/\\r}"
    printf '%s' "$s"
}

has_jq() { command -v jq >/dev/null 2>&1; }

# --- Locate project root ----------------------------------------------------

find_repo_root() {
    local dir="$1"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.git" ] || [ -d "$dir/.specify" ]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if git rev-parse --show-toplevel >/dev/null 2>&1; then
    REPO_ROOT=$(git rev-parse --show-toplevel)
    HAS_GIT=true
else
    REPO_ROOT="$(find_repo_root "$SCRIPT_DIR")"
    if [ -z "$REPO_ROOT" ]; then
        echo '{"error":"Could not determine repository root"}' >&2
        exit 1
    fi
    HAS_GIT=false
fi

SPECIFY_DIR="$REPO_ROOT/.specify"
if [ ! -d "$SPECIFY_DIR" ]; then
    echo '{"error":"Not a spec-kit project (no .specify/ directory)"}' >&2
    exit 1
fi

PROJECT_NAME=$(basename "$REPO_ROOT")

# --- Detect AI agent(s) -----------------------------------------------------

AGENTS_JSON="[]"
declare -a AGENT_KEYS=("copilot" "claude" "gemini" "cursor-agent" "qwen" "opencode" "codex" "windsurf" "kilocode" "auggie" "codebuddy" "qodercli" "roo" "kiro-cli" "amp" "shai" "tabnine" "agy" "bob" "vibe" "kimi")
declare -a AGENT_NAMES=("GitHub Copilot" "Claude Code" "Gemini CLI" "Cursor" "Qwen Code" "opencode" "Codex CLI" "Windsurf" "Kilo Code" "Auggie CLI" "CodeBuddy" "Qoder CLI" "Roo Code" "Kiro CLI" "Amp" "SHAI" "Tabnine CLI" "Antigravity" "IBM Bob" "Mistral Vibe" "Kimi Code")
declare -a AGENT_FOLDERS=(".github" ".claude" ".gemini" ".cursor" ".qwen" ".opencode" ".codex" ".windsurf" ".kilocode" ".augment" ".codebuddy" ".qoder" ".roo" ".kiro" ".agents" ".shai" ".tabnine/agent" ".agent" ".bob" ".vibe" ".kimi")
declare -a AGENT_CMD_DIRS=("agents" "commands" "commands" "commands" "commands" "command" "prompts" "workflows" "workflows" "commands" "commands" "commands" "commands" "prompts" "commands" "commands" "commands" "workflows" "commands" "prompts" "skills")

detected_agents=""
for i in "${!AGENT_KEYS[@]}"; do
    folder="${AGENT_FOLDERS[$i]}"
    agent_dir="$REPO_ROOT/$folder"
    if [ "${AGENT_KEYS[$i]}" = "amp" ] && [ -f "$REPO_ROOT/.agents/skills/speckit-specify/SKILL.md" ]; then
        continue
    fi
    if [ "${AGENT_KEYS[$i]}" = "codex" ] && [ -f "$REPO_ROOT/.agents/skills/speckit-specify/SKILL.md" ]; then
        folder=".agents"
        agent_dir="$REPO_ROOT/$folder"
        AGENT_CMD_DIRS[$i]="skills"
    fi
    if [ -d "$agent_dir" ]; then
        cmd_dir="$agent_dir/${AGENT_CMD_DIRS[$i]}"
        has_commands=false
        if [ -d "$cmd_dir" ] && [ -n "$(ls -A "$cmd_dir" 2>/dev/null)" ]; then
            has_commands=true
        fi
        entry="$(printf '{"key":"%s","name":"%s","folder":"%s","has_commands":%s}' \
            "$(json_escape "${AGENT_KEYS[$i]}")" \
            "$(json_escape "${AGENT_NAMES[$i]}")" \
            "$(json_escape "$folder/")" \
            "$has_commands")"
        if [ -z "$detected_agents" ]; then
            detected_agents="$entry"
        else
            detected_agents="$detected_agents,$entry"
        fi
    fi
done
AGENTS_JSON="[$detected_agents]"

# --- Detect script type ------------------------------------------------------

SCRIPT_TYPE="none"
has_bash=false
has_ps=false
[ -d "$SPECIFY_DIR/scripts/bash" ] && has_bash=true
[ -d "$SPECIFY_DIR/scripts/powershell" ] && has_ps=true

if $has_bash && $has_ps; then
    SCRIPT_TYPE="sh + ps"
elif $has_bash; then
    SCRIPT_TYPE="sh"
elif $has_ps; then
    SCRIPT_TYPE="ps"
fi

# --- Detect current feature --------------------------------------------------

CURRENT_BRANCH=""
FEATURE_DIR=""
SPECS_DIR="$REPO_ROOT/specs"

# Keep the Git branch separate from the selected feature. Current Spec Kit
# resolves a directory override or persisted feature pointer, even on main.
if [ "$HAS_GIT" = true ]; then
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || true)
fi
if [ -n "${SPECIFY_FEATURE_DIRECTORY:-}" ]; then
    FEATURE_DIR="$SPECIFY_FEATURE_DIRECTORY"
elif [ -f "$SPECIFY_DIR/feature.json" ]; then
    FEATURE_DIR=$(python3 -c 'import json,sys; value=json.load(open(sys.argv[1])).get("feature_directory"); assert isinstance(value,str) and value, "Missing feature_directory"; print(value)' "$SPECIFY_DIR/feature.json")
elif [ -n "${SPECIFY_FEATURE:-}" ]; then
    FEATURE_DIR="$SPECS_DIR/$SPECIFY_FEATURE"
elif [[ "$CURRENT_BRANCH" =~ ^([0-9]{3})- ]]; then
    if [ -d "$SPECS_DIR/$CURRENT_BRANCH" ]; then
        FEATURE_DIR="$SPECS_DIR/$CURRENT_BRANCH"
    else
        matches=()
        for dir in "$SPECS_DIR/${BASH_REMATCH[1]}-"*/; do
            [ -d "$dir" ] && matches+=("$dir")
        done
        if [ ${#matches[@]} -gt 1 ]; then
            echo 'Ambiguous feature prefix; select SPECIFY_FEATURE_DIRECTORY explicitly' >&2
            exit 1
        fi
        [ ${#matches[@]} -eq 0 ] || FEATURE_DIR="${matches[0]}"
    fi
fi
if [ -n "$FEATURE_DIR" ]; then
    [[ "$FEATURE_DIR" = /* ]] || FEATURE_DIR="$REPO_ROOT/$FEATURE_DIR"
    if [ ! -d "$FEATURE_DIR" ]; then
        echo 'Selected feature directory does not exist' >&2
        exit 1
    fi
    FEATURE_DIR="$(cd "$FEATURE_DIR" && pwd -P)"
    case "$FEATURE_DIR" in
        "$REPO_ROOT"/specs/*) ;;
        *) echo 'Selected feature is outside this project specs directory' >&2; exit 1 ;;
    esac
fi

# --- Artifact checks -------------------------------------------------------

has_spec=false; has_plan=false; has_tasks=false
has_research=false; has_datamodel=false; has_quickstart=false
has_contracts=false; contract_count=0
has_checklists=false; checklist_count=0; checklists_all_pass=true

tasks_completed=0; tasks_total=0

if [ -n "$FEATURE_DIR" ] && [ -d "$FEATURE_DIR" ]; then
    [ -f "$FEATURE_DIR/spec.md" ] && has_spec=true
    [ -f "$FEATURE_DIR/plan.md" ] && has_plan=true
    [ -f "$FEATURE_DIR/tasks.md" ] && has_tasks=true
    [ -f "$FEATURE_DIR/research.md" ] && has_research=true
    [ -f "$FEATURE_DIR/data-model.md" ] && has_datamodel=true
    [ -f "$FEATURE_DIR/quickstart.md" ] && has_quickstart=true

    if [ -d "$FEATURE_DIR/contracts" ] && [ -n "$(ls -A "$FEATURE_DIR/contracts" 2>/dev/null)" ]; then
        has_contracts=true
        contract_count=$(find "$FEATURE_DIR/contracts" -maxdepth 1 -type f | wc -l | tr -d ' ')
    fi

    if [ -d "$FEATURE_DIR/checklists" ]; then
        for cl in "$FEATURE_DIR/checklists"/*.md; do
            [ -f "$cl" ] || continue
            checklist_count=$((checklist_count + 1))
            has_checklists=true
            if grep -q '^\s*-\s*\[ \]' "$cl" 2>/dev/null; then
                checklists_all_pass=false
            fi
        done
    fi

    # Parse task progress
    if [ "$has_tasks" = true ]; then
        fence=""
        while IFS= read -r line || [ -n "$line" ]; do
            if [[ "$line" =~ ^[[:space:]]*(\`{3,}|~{3,}) ]]; then
                marker="${BASH_REMATCH[1]}"
                if [ -z "$fence" ]; then
                    fence="$marker"
                elif [ "${marker:0:1}" = "${fence:0:1}" ] && [ ${#marker} -ge ${#fence} ]; then
                    fence=""
                fi
                continue
            fi
            [ -z "$fence" ] || continue
            if [[ "$line" =~ ^[[:space:]]*[-*+][[:space:]]+\[([[:space:]xX])\] ]]; then
                tasks_total=$((tasks_total + 1))
                if [[ "${BASH_REMATCH[1]}" =~ [xX] ]]; then
                    tasks_completed=$((tasks_completed + 1))
                fi
            fi
        done < "$FEATURE_DIR/tasks.md"
    fi
fi

# --- Detect workflow phase ---------------------------------------------------

PHASE="unknown"
PHASE_HINT=""

if [ -z "$FEATURE_DIR" ] || [ ! -d "$FEATURE_DIR" ]; then
    PHASE="no_feature"
    PHASE_HINT="Run /speckit.specify to create a feature"
elif [ "$has_tasks" = true ] && [ "$tasks_total" -gt 0 ] && [ "$tasks_completed" -eq "$tasks_total" ]; then
    PHASE="complete"
    PHASE_HINT="All tasks done. Review your implementation."
elif [ "$has_tasks" = true ]; then
    PHASE="implement"
    PHASE_HINT="Ready for /speckit.implement"
elif [ "$has_plan" = true ]; then
    PHASE="tasks"
    PHASE_HINT="Ready for /speckit.tasks"
elif [ "$has_spec" = true ]; then
    PHASE="plan"
    PHASE_HINT="Ready for /speckit.clarify or /speckit.plan"
else
    PHASE="not_started"
    PHASE_HINT="Run /speckit.specify to create a spec"
fi

# --- Extensions summary ------------------------------------------------------

installed_count=0
EXTENSIONS_DIR="$SPECIFY_DIR/extensions"
REGISTRY_FILE="$EXTENSIONS_DIR/.registry"
if [ -f "$REGISTRY_FILE" ]; then
    if has_jq; then
        installed_count=$(jq '.extensions | length' "$REGISTRY_FILE" 2>/dev/null || echo 0)
    else
        installed_count=$(grep -c '"installed_at"' "$REGISTRY_FILE" 2>/dev/null || echo 0)
    fi
fi

# --- Feature count -----------------------------------------------------------

feature_count=0
if [ -d "$SPECS_DIR" ]; then
    for dir in "$SPECS_DIR"/*/; do
        [ -d "$dir" ] && feature_count=$((feature_count + 1))
    done
fi

# --- Output JSON -------------------------------------------------------------

FEATURE_NAME=""
if [ -n "$FEATURE_DIR" ] && [ -d "$FEATURE_DIR" ]; then
    FEATURE_NAME=$(basename "$FEATURE_DIR")
fi

if has_jq; then
    jq -cn \
        --arg project_name "$PROJECT_NAME" \
        --arg has_git "$HAS_GIT" \
        --arg current_branch "$CURRENT_BRANCH" \
        --arg feature_name "$FEATURE_NAME" \
        --arg script_type "$SCRIPT_TYPE" \
        --argjson agents "$AGENTS_JSON" \
        --arg has_spec "$has_spec" \
        --arg has_plan "$has_plan" \
        --arg has_tasks "$has_tasks" \
        --arg has_research "$has_research" \
        --arg has_datamodel "$has_datamodel" \
        --arg has_quickstart "$has_quickstart" \
        --arg has_contracts "$has_contracts" \
        --argjson contract_count "$contract_count" \
        --arg has_checklists "$has_checklists" \
        --argjson checklist_count "$checklist_count" \
        --arg checklists_all_pass "$checklists_all_pass" \
        --argjson tasks_completed "$tasks_completed" \
        --argjson tasks_total "$tasks_total" \
        --arg phase "$PHASE" \
        --arg phase_hint "$PHASE_HINT" \
        --argjson installed_extensions "$installed_count" \
        --argjson feature_count "$feature_count" \
        '{
            project_name: $project_name,
            has_git: ($has_git == "true"),
            current_branch: $current_branch,
            feature_name: $feature_name,
            script_type: $script_type,
            agents: $agents,
            artifacts: {
                spec: ($has_spec == "true"),
                plan: ($has_plan == "true"),
                tasks: ($has_tasks == "true"),
                research: ($has_research == "true"),
                data_model: ($has_datamodel == "true"),
                quickstart: ($has_quickstart == "true"),
                contracts: ($has_contracts == "true"),
                contract_count: $contract_count,
                checklists: ($has_checklists == "true"),
                checklist_count: $checklist_count,
                checklists_all_pass: ($checklists_all_pass == "true")
            },
            tasks: {
                completed: $tasks_completed,
                total: $tasks_total
            },
            phase: $phase,
            phase_hint: $phase_hint,
            installed_extensions: $installed_extensions,
            feature_count: $feature_count
        }'
else
    cat <<ENDJSON
{"project_name":"$(json_escape "$PROJECT_NAME")","has_git":$HAS_GIT,"current_branch":"$(json_escape "$CURRENT_BRANCH")","feature_name":"$(json_escape "$FEATURE_NAME")","script_type":"$(json_escape "$SCRIPT_TYPE")","agents":$AGENTS_JSON,"artifacts":{"spec":$has_spec,"plan":$has_plan,"tasks":$has_tasks,"research":$has_research,"data_model":$has_datamodel,"quickstart":$has_quickstart,"contracts":$has_contracts,"contract_count":$contract_count,"checklists":$has_checklists,"checklist_count":$checklist_count,"checklists_all_pass":$checklists_all_pass},"tasks":{"completed":$tasks_completed,"total":$tasks_total},"phase":"$(json_escape "$PHASE")","phase_hint":"$(json_escape "$PHASE_HINT")","installed_extensions":$installed_count,"feature_count":$feature_count}
ENDJSON
fi
