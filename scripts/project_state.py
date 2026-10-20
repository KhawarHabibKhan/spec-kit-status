"""Read-only project and feature context compatible with Spec Kit 1.2.2."""
import json
import os
from pathlib import Path
import re


def read_object(path, required=False):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        if required:
            raise ValueError('Missing ' + str(path))
        return None
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('Invalid or unreadable ' + str(path)) from exc
    if not isinstance(value, dict):
        raise ValueError('Expected JSON object in ' + str(path))
    return value


def project_root():
    override = os.environ.get('SPECIFY_INIT_DIR')
    if override:
        root = Path(override).resolve()
        if not (root / '.specify').is_dir():
            raise ValueError('SPECIFY_INIT_DIR has no .specify directory')
        return root
    start = Path.cwd().resolve()
    for root in (start, *start.parents):
        if (root / '.specify').is_dir():
            return root
    raise ValueError('Not a spec-kit project (no .specify directory)')


def native_state(root):
    state = read_object(root / '.specify/integration.json')
    if state is not None:
        schema = state.get('integration_state_schema', 1)
        if not isinstance(schema, int) or isinstance(schema, bool) or schema > 1:
            raise ValueError('Unsupported native integration state schema')
        for key in ('integration', 'agent'):
            if key in state and not isinstance(state[key], str):
                raise ValueError('Invalid native integration ' + key)
    override = os.environ.get('SPECIFY_FEATURE_DIRECTORY')
    if override:
        return state, override
    pointer = read_object(root / '.specify/feature.json')
    selector = None
    if pointer is not None:
        selector = pointer.get('feature_directory')
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError('Invalid feature_directory in .specify/feature.json')
    return state, os.environ.get('SPECIFY_FEATURE_DIRECTORY') or selector


def resolve_feature(root, selector, legacy=False):
    if not selector:
        return None
    if not isinstance(selector, str):
        raise ValueError('Invalid feature selector')
    specs = root / 'specs'
    if legacy:
        if not re.fullmatch(r'[0-9]{3}(?:-[A-Za-z0-9-]+)?', selector):
            raise ValueError('Feature must be NNN or NNN-name')
        candidate = specs / selector
        if not candidate.is_dir():
            matches = sorted(p for p in specs.glob(selector[:3] + '-*') if p.is_dir())
            if len(matches) > 1:
                raise ValueError('Ambiguous feature prefix: ' + selector)
            if not matches:
                raise ValueError('No specification directory for: ' + selector)
            candidate = matches[0]
    else:
        candidate = Path(selector)
        if not candidate.is_absolute():
            candidate = root / candidate
    # Inspect the lexical path too: resolving first would conceal symlinks.
    if candidate.is_symlink() or candidate.resolve() != candidate.absolute() or not candidate.is_dir():
        raise ValueError('Missing or unsafe active feature')
    if candidate.parent != specs or not re.match(r'^[0-9]{3}-', candidate.name):
        raise ValueError('Feature must be a numbered directory directly under specs/')
    return candidate
