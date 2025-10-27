# scripts/ai_pr_check.py
import os
import re
import json
import sys
import ast
import hashlib
import difflib
from pathlib import Path
import requests
import subprocess

try:
    import yaml  # pyyaml
except Exception:
    yaml = None

# --------------------- env + config ---------------------
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO = os.environ.get('REPO')
PR_NUMBER = int(os.environ.get('PR_NUMBER', '0'))
BASE_DIR = Path(os.environ.get('BASE_DIR', '.'))
HEAD_DIR = Path(os.environ.get('HEAD_DIR', '.'))
OPENAPI_BASE = Path(os.environ.get('OPENAPI_BASE', ''))
OPENAPI_HEAD = Path(os.environ.get('OPENAPI_HEAD', ''))
CONFIG_PATH = HEAD_DIR / '.dupacheck.yml'

DEFAULT_CFG = {
    'exclude_paths': ['**/migrations/**', '**/tests/**', '**/.venv/**', '**/.git/**', '**/node_modules/**'],
    'file_extensions': ['.py', '.js', '.ts', '.tsx'],
    'api_similarity_threshold': 0.8,
    'func_similarity_threshold': 0.9,  # stricter to reduce noise
    'max_near_matches': 2,
    'fail_on_blocker': False,
    'enable_ai_reasoning': False,
    # New flags:
    'enable_dependency_check': True,
    'enable_signature_check': True,
}

cfg = DEFAULT_CFG.copy()
if CONFIG_PATH.exists() and yaml:
    with open(CONFIG_PATH, 'r') as f:
        cfg.update(yaml.safe_load(f) or {})

# --------------------- helpers ---------------------
def path_included(p: Path):
    p_str = p.as_posix()
    for pat in cfg['exclude_paths']:
        if Path(HEAD_DIR).joinpath(p_str).match(pat) or Path(BASE_DIR).joinpath(p_str).match(pat):
            return False
    return True

class Normalizer(ast.NodeTransformer):
    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id='X', ctx=node.ctx), node)
    def visit_Attribute(self, node):
        self.generic_visit(node)
        node.attr = 'X'
        return node
    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value='C'), node)

NORMALIZER = Normalizer()

def normalize_func(src: str) -> str:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ''
    # strip docstrings
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            if (
                isinstance(node.body[0], ast.Expr)
                and isinstance(getattr(node.body[0], 'value', None), ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]
    tree = NORMALIZER.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.dump(tree, include_attributes=False)

def fingerprint(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def get_git_diff_functions(base_dir: Path, head_dir: Path, file_path: str):
    """Get only the functions that were added or modified in this PR"""
    try:
        result = subprocess.run([
            'git', 'diff', '--no-index', '--unified=0',
            str(base_dir / file_path), str(head_dir / file_path)
        ], capture_output=True, text=True, cwd=head_dir)
        diff_output = result.stdout
        added_lines = []
        current_line_num = 0
        for line in diff_output.split('\n'):
            if line.startswith('@@'):
                match = re.search(r'\+(\d+)(?:,(\d+))?', line)
                if match:
                    current_line_num = int(match.group(1))
            elif line.startswith('+') and not line.startswith('+++'):
                added_lines.append(current_line_num)
                current_line_num += 1
            elif not line.startswith('-'):
                current_line_num += 1
        return added_lines
    except Exception as e:
        print(f"Git diff failed for {file_path}: {e}", file=sys.stderr)
        return []

def py_functions_from_file(path: Path, only_lines: list = None):
    """Extract functions, optionally filtering by line numbers"""
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, 'lineno', 1)
            end = getattr(node, 'end_lineno', start)
            if only_lines is not None:
                function_lines = set(range(start, end + 1))
                modified_lines = set(only_lines)
                if not function_lines.intersection(modified_lines):
                    continue  # Skip functions that weren’t modified
            segment = '\n'.join(src.splitlines()[start - 1:end])
            norm = normalize_func(segment)
            if norm:
                funcs.append({
                    'name': node.name,
                    'start': start,
                    'end': end,
                    'norm': norm,
                    'fp': fingerprint(norm),
                    'is_new_or_modified': only_lines is not None
                })
    return funcs

FUNC_DEF_RE_JS = re.compile(
    r"export\s+(?:default\s+)?function\s+(\w+)\s*\(|"
    r"export\s+(?:const|let|var)\s+(\w+)\s*=\s*\((?:[^)]*)\)\s*=>",
    re.MULTILINE,
)

# --------------------- get changed files and their diffs ---------------------
headers = {'Authorization': f'Bearer {GITHUB_TOKEN}', 'Accept': 'application/vnd.github+json'} if GITHUB_TOKEN else {}
changed_files = []
if GITHUB_TOKEN and REPO and PR_NUMBER:
    url = f'https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/files'
    page = 1
    while True:
        resp = requests.get(url, headers=headers, params={'per_page': 100, 'page': page})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        for f in data:
            changed_files.append(f['filename'])
        page += 1
else:
    for ext in cfg['file_extensions']:
        changed_files += [str(p.relative_to(HEAD_DIR)) for p in HEAD_DIR.rglob(f'*{ext}')]

changed_files = [f for f in changed_files if path_included(Path(f))]

# --------------------- build base branch function index ---------------------
base_index = {}
base_name_to_norms = {}

for p in BASE_DIR.rglob('*.py'):
    if not path_included(p.relative_to(BASE_DIR)):
        continue
    for f in py_functions_from_file(p):
        base_index.setdefault(f['fp'], []).append({
            'file': str(p.relative_to(BASE_DIR)),
            'name': f['name'],
            'start': f['start'],
            'end': f['end']
        })
        base_name_to_norms.setdefault(f['name'], []).append({
            'norm': f['norm'],
            'file': str(p.relative_to(BASE_DIR)),
            'name': f['name'],
            'fp': f['fp']
        })

# ALSO index all functions from HEAD branch files (for same-file duplicate detection)
head_all_funcs_index = {}
for rel in changed_files:
    if not rel.endswith('.py'):
        continue
    head_path = HEAD_DIR / rel
    if not head_path.exists():
        continue
    all_funcs = py_functions_from_file(head_path)
    for f in all_funcs:
        f['file'] = rel
        head_all_funcs_index.setdefault(f['fp'], []).append({
            'file': rel,
            'name': f['name'],
            'start': f['start'],
            'end': f['end']
        })

# --------------------- analyze only NEW/MODIFIED functions ---------------------
head_new_or_modified_funcs = []
for rel in changed_files:
    if not rel.endswith('.py'):
        continue
    head_path = HEAD_DIR / rel
    base_path = BASE_DIR / rel
    if not head_path.exists():
        continue
    if not base_path.exists():
        for f in py_functions_from_file(head_path):
            f['file'] = rel
            f['is_new_or_modified'] = True
            head_new_or_modified_funcs.append(f)
    else:
        modified_lines = get_git_diff_functions(BASE_DIR, HEAD_DIR, rel)
        if modified_lines:
            for f in py_functions_from_file(head_path, modified_lines):
                f['file'] = rel
                head_new_or_modified_funcs.append(f)
        else:
            head_funcs = py_functions_from_file(head_path)
            base_funcs = py_functions_from_file(base_path)
            base_func_fps = {f['fp']: f for f in base_funcs}
            for f in head_funcs:
                base_func = base_func_fps.get(f['fp'])
                if not base_func or base_func['name'] != f['name']:
                    f['file'] = rel
                    f['is_new_or_modified'] = True
                    head_new_or_modified_funcs.append(f)

# --------------------- API endpoints ---------------------
def load_openapi(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def paths_methods(spec):
    out = set()
    paths = (spec or {}).get('paths', {})
    for p, methods in paths.items():
        for m in methods.keys():
            out.add((m.lower(), p))
    return out

base_api = paths_methods(load_openapi(OPENAPI_BASE))
head_api = paths_methods(load_openapi(OPENAPI_HEAD))
new_api = sorted(list(head_api - base_api))

# --------------------- JS/TS component analysis ---------------------
def get_js_modified_components(base_dir: Path, head_dir: Path, file_path: str):
    try:
        base_path = base_dir / file_path
        head_path = head_dir / file_path
        if not base_path.exists():
            return get_js_components_from_file(head_path)
        base_components = {comp['name']: comp for comp in get_js_components_from_file(base_path)}
        head_components = get_js_components_from_file(head_path)
        new_or_modified = []
        for comp in head_components:
            if comp['name'] not in base_components:
                new_or_modified.append(comp)
        return new_or_modified
    except Exception:
        return []

def get_js_components_from_file(path: Path):
    if not path.exists():
        return []
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    components = []
    for m in FUNC_DEF_RE_JS.finditer(src):
        name = m.group(1) or m.group(2)
        if name:
            components.append({'name': name})
    return components

head_changed_components = []
for rel in changed_files:
    if Path(rel).suffix in {'.js', '.ts', '.tsx'}:
        new_comps = get_js_modified_components(BASE_DIR, HEAD_DIR, rel)
        for comp in new_comps:
            comp['file'] = rel
            head_changed_components.append(comp)

base_component_names = {}
for p in BASE_DIR.rglob('*'):
    if p.suffix in {'.js', '.ts', '.tsx'} and path_included(p.relative_to(BASE_DIR)):
        for comp in get_js_components_from_file(p):
            base_component_names.setdefault(comp['name'], set()).add(str(p.relative_to(BASE_DIR)))

# --------------------- Dependency Impact Analysis ---------------------
def get_function_calls_from_file(path: Path):
    """Return list of function names that are called in this file"""
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(src)
    except Exception:
        return []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    return calls

def get_function_signature(node):
    """Return normalized function signature as tuple (argnames, defaults)"""
    args = [a.arg for a in node.args.args]
    defaults = [ast.dump(d) for d in node.args.defaults]
    return (args, defaults)

def py_signatures_from_file(path: Path):
    """Extract function signatures for comparison"""
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(src)
    except Exception:
        return {}
    signatures = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            signatures[node.name] = get_function_signature(node)
    return signatures

dependency_warnings = []
signature_warnings = []

if cfg.get('enable_dependency_check', True):
    print("Analyzing function call dependencies...", file=sys.stderr)
    call_graph = {}
    for p in HEAD_DIR.rglob('*.py'):
        if not path_included(p.relative_to(HEAD_DIR)):
            continue
        called_funcs = get_function_calls_from_file(p)
        for func in called_funcs:
            call_graph.setdefault(func, set()).add(str(p.relative_to(HEAD_DIR)))
    for f in head_new_or_modified_funcs:
        called_in = call_graph.get(f['name'], set())
        if called_in:
            dependency_warnings.append(
                f"⚠️ Function `{f['name']}` was modified in `{f['file']}` and is called in: {', '.join(sorted(called_in))}. "
                f"Review these call sites for potential issues (return type, args, logic)."
            )

if cfg.get('enable_signature_check', True):
    print("Checking for function signature changes...", file=sys.stderr)
    for rel in changed_files:
        if not rel.endswith('.py'):
            continue
        base_path = BASE_DIR / rel
        head_path = HEAD_DIR / rel
        if not (base_path.exists() and head_path.exists()):
            continue
        base_signs = py_signatures_from_file(base_path)
        head_signs = py_signatures_from_file(head_path)
        for func, sig in head_signs.items():
            if func in base_signs and sig != base_signs[func]:
                signature_warnings.append(
                    f"⚠️ Function signature changed for `{func}` in `{rel}`.\n"
                    f"    Old: args={base_signs[func][0]}, defaults={base_signs[func][1]}\n"
                    f"    New: args={sig[0]}, defaults={sig[1]}"
                )

# --------------------- build report ---------------------
blockers, warnings, infos = [], [], []

print(f"Analyzing {len(head_new_or_modified_funcs)} new/modified functions...", file=sys.stderr)

# 1) Exact duplicate Python functions (check against base branch AND same file)
for f in head_new_or_modified_funcs:
    matches = base_index.get(f['fp'], [])
    if matches:
        for m in matches:
            if f['file'] == m['file'] and f['name'] == m['name']:
                continue
            if f['file'] == m['file']:
                blockers.append(
                    f"🚫 Exact duplicate function in SAME FILE: `{f['name']}` at lines {f['start']}-{f['end']} "
                    f"matches existing `{m['name']}` at lines {m['start']}-{m['end']} in `{f['file']}`"
                )
            else:
                blockers.append(
                    f"🚫 Exact duplicate function across files: `{f['name']}` in `{f['file']}:{f['start']}-{f['end']}` "
                    f"matches `{m['name']}` in `{m['file']}:{m['start']}-{m['end']}`"
                )

# 2) Near-duplicate Python functions (check against base branch AND same file)
for f in head_new_or_modified_funcs:
    candidates = base_name_to_norms.get(f['name'], [])
    sims = []
    for c in candidates:
        if f['fp'] == c['fp']:
            continue
        if c['file'] == f['file'] and c['name'] == f['name']:
            continue
        ratio = difflib.SequenceMatcher(a=f['norm'], b=c['norm']).ratio()
        if ratio >= cfg['func_similarity_threshold']:
            sims.append((ratio, c, 'base'))
    head_same_file_funcs = [
        func for func_list in head_all_funcs_index.values()
        for func in func_list
        if func['file'] == f['file'] and func['name'] != f['name']
    ]
    for other_func in head_same_file_funcs:
        if f['fp'] == other_func.get('fp', ''):
            continue
        other_head_path = HEAD_DIR / other_func['file']
        if other_head_path.exists():
            try:
                src = other_head_path.read_text(encoding='utf-8', errors='ignore')
                lines = src.splitlines()
                start_idx = other_func['start'] - 1
                end_idx = other_func['end']
                segment = '\n'.join(lines[start_idx:end_idx])
                other_norm = normalize_func(segment)
                if other_norm:
                    ratio = difflib.SequenceMatcher(a=f['norm'], b=other_norm).ratio()
                    if ratio >= cfg['func_similarity_threshold']:
                        sims.append((ratio, {
                            'name': other_func['name'],
                            'file': other_func['file'],
                            'start': other_func['start'],
                            'end': other_func['end']
                        }, 'same_file'))
            except Exception:
                pass
    sims.sort(key=lambda x: x[0], reverse=True)
    for ratio, c, source_type in sims[: cfg['max_near_matches']]:
        if source_type == 'same_file':
            warnings.append(
                f"⚠️ Near-duplicate within SAME FILE: `{f['name']}` at lines {f['start']}-{f['end']} "
                f"~{int(ratio*100)}% similar to `{c['name']}` at lines {c.get('start','?')}-{c.get('end','?')} in `{f['file']}`"
            )
        else:
            warnings.append(
                f"⚠️ Near-duplicate function `{f['name']}` in `{f['file']}:{f['start']}-{f['end']}` "
                f"~{int(ratio*100)}% similar to `{c['name']}` in `{c['file']}`"
            )

# 3) API duplicates (unchanged logic)
for method, path_ in new_api:
    if (method, path_) in base_api:
        blockers.append(f"🚫 API already exists: `{method.upper()} {path_}` is present in base branch")
    else:
        base_like = [
            bp for (bm, bp) in base_api
            if bm == method and re.sub(r"\{[^}]+\}", "{}", bp) == re.sub(r"\{[^}+\}", "{}", path_)
        ]
        if base_like:
            warnings.append(f"⚠️ API may overlap: `{method.upper()} {path_}` ~ similar to `{method.upper()} {base_like[0]}`")

# 4) Component name duplicates
for comp in head_changed_components:
    if comp['name'] in base_component_names:
        where = ', '.join(sorted(list(base_component_names[comp['name']])))
        warnings.append(f"⚠️ Component name `{comp['name']}` in `{comp['file']}` already exists in: {where}")

# 5) Dependency & signature warnings
if dependency_warnings:
    sections = []
    sections.append("## ⚠️ Dependency Impact (Function Calls)\n" + '\n'.join(f"- {w}" for w in dependency_warnings))
else:
    sections = []

if signature_warnings:
    sections.append("## ⚠️ Function Signature Changes\n" + '\n'.join(f"- {w}" for w in signature_warnings))

# --------------------- output ---------------------
# Build sections for duplicate logic + existing logic
dup_sections = []
if blockers:
    dup_sections.append("## 🚫 Duplicates Found (Blockers)\n" + '\n'.join(f"- {b}" for b in blockers))
if warnings:
    dup_sections.append("## ⚠️ Potential Overlaps (Review)\n" + '\n'.join(f"- {w}" for w in warnings))

summary_lines = [
    f"- Analyzed **{len(head_new_or_modified_funcs)} new/modified functions** (not all functions in changed files)",
    f"- Checked **{len(changed_files)} changed files** against base branch",
    f"- Found **{len(blockers)} exact duplicates** and **{len(warnings)} potential overlaps**"
]

dup_sections.append("## 📊 Analysis Summary\n" + '\n'.join(summary_lines))
dup_sections.append("## 🔍 What Was Checked\n- Only **new or modified functions** in this PR are compared against existing codebase\n- **Same-file duplicates**: New functions checked against other functions in the same file\n- **Cross-file duplicates**: New functions checked against all existing functions in base branch\n- OpenAPI endpoints: base vs head comparison for new/changed routes\n- Component names: new/modified components checked against existing ones")

# Combine all sections
body = (
    f"### 🔍 Smart Duplicate & Dependency Logic Guard\n"
    f"**PR #{PR_NUMBER}** - Analyzing only new/modified code\n\n"
    + "\n\n".join(dup_sections + sections)
    + "\n\n_Config: `.dupacheck.yml` • thresholds and exclusions are adjustable._"
)

print(body)

# Post PR comment
if GITHUB_TOKEN and REPO and PR_NUMBER:
    url = f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments"
    r = requests.post(url, headers={'Authorization': f'Bearer {GITHUB_TOKEN}', 'Accept': 'application/vnd.github+json'}, json={'body': body})
    try:
        r.raise_for_status()
        print("✅ Posted PR comment successfully", file=sys.stderr)
    except Exception as e:
        print('❌ Failed to post PR comment:', r.text, file=sys.stderr)

# Exit code for CI
if blockers and cfg.get('fail_on_blocker'):
    print("❌ Exiting with error due to blockers", file=sys.stderr)
    sys.exit(1)
else:
    print("✅ Check completed successfully", file=sys.stderr)
    sys.exit(0)
