#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
source_only=false
if [ "${1:-}" = "--source-only" ]; then
    source_only=true
    shift
fi
agent_dir=${1:-/Users/jumper/.codex/agents}
runtime_skill_dir=${2:-/Users/jumper/.codex/skills/dev-team}

python3 - "$skill_dir" "$agent_dir" "$runtime_skill_dir" "$source_only" <<'PY'
from pathlib import Path
import filecmp
import os
import re
import subprocess
import sys
import tomllib

skill_dir = Path(sys.argv[1])
agent_dir = Path(sys.argv[2])
runtime_skill_dir = Path(sys.argv[3])
source_only = sys.argv[4] == "true"

skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
frontmatter_match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", skill_text, re.DOTALL)
if not frontmatter_match:
    raise SystemExit("SKILL_FRONTMATTER_INVALID")

frontmatter = {}
for line in frontmatter_match.group(1).splitlines():
    key, separator, value = line.partition(":")
    if not separator or not key.strip() or key != key.strip():
        raise SystemExit(f"SKILL_FRONTMATTER_LINE_INVALID: {line!r}")
    if key in frontmatter:
        raise SystemExit(f"SKILL_FRONTMATTER_DUPLICATE: {key}")
    frontmatter[key] = value.strip()

expected_frontmatter = {
    "name": "dev-team",
    "description": "手动调用的通用开发协作路由器；按任务风险选择最小团队，协调开发、UI、验证、Git 候选和安全收口。",
    "disable-model-invocation": "true",
}
if frontmatter != expected_frontmatter:
    raise SystemExit(f"SKILL_FRONTMATTER_MISMATCH: {frontmatter!r}")
if not source_only and runtime_skill_dir.name != frontmatter["name"]:
    raise SystemExit("RUNTIME_SKILL_DIRECTORY_NAME_MISMATCH")

required = [
    ".gitignore",
    "SKILL.md",
    "references/glossary.md",
    "references/project-discovery.md",
    "references/engineering-quality.md",
    "references/executable-protocol.md",
    "references/specialist-routing.md",
    "references/git-lifecycle.md",
    "references/candidate-ledger.md",
    "references/routing.md",
    "references/dispatch-packet.md",
    "references/model-policy.md",
    "references/ui-routing.md",
    "references/recovery.md",
    "tests/scenarios.md",
    "scripts/verify-protocol.py",
    "scripts/verify-setup.sh",
    "tests/test_protocol.py",
    "tests/fixtures/protocol/valid.json",
    "tests/fixtures/protocol/non-main-direct-write.json",
    "tests/fixtures/protocol/mismatched-failure-count.json",
    "tests/fixtures/protocol/missing-card-field.json",
]
required += [str(path.relative_to(skill_dir)) for path in sorted((skill_dir / "tests/fixtures/protocol").glob("*.json")) if str(path.relative_to(skill_dir)) not in required]
required += [str(path.relative_to(skill_dir)) for path in sorted((skill_dir / "templates/agents").glob("*.toml"))]
for relative in required:
    path = skill_dir / relative
    if not path.is_file():
        raise SystemExit(f"MISSING: {path}")
    if not source_only:
        runtime_path = runtime_skill_dir / relative
        if not runtime_path.is_file():
            raise SystemExit(f"RUNTIME_SKILL_MISSING: {runtime_path}")
        if not filecmp.cmp(path, runtime_path, shallow=False):
            raise SystemExit(f"RUNTIME_SKILL_DIFFERS: {relative}")
if "[TODO:" in skill_text[frontmatter_match.end():]:
    raise SystemExit("SKILL_UNFINISHED_TODO")

verification_roots = [("SOURCE", skill_dir)]
if not source_only:
    verification_roots.append(("RUNTIME", runtime_skill_dir))
for label, root in verification_roots:
    cache_dirs = sorted(path for path in root.rglob("__pycache__") if path.is_dir())
    if cache_dirs:
        raise SystemExit(f"PYTHON_CACHE_PRESENT: {label}: {cache_dirs[0]}")

# Validate package contracts and execute behavior tests; prose is reviewed by agents.
import runpy
protocol = runpy.run_path(str(skill_dir / "scripts/verify-protocol.py"))
role_files = {
    "team-explorer.toml": ("项目勘察员", "explorer"),
    "team-developer.toml": ("开发执行员", "developer"),
    "team-ui-maker.toml": ("界面制作员", "ui-maker"),
    "team-reviewer.toml": ("独立验收员", "reviewer"),
}
for filename, (name, role) in role_files.items():
    template = skill_dir / "templates/agents" / filename
    for path in ((template,) if source_only else (template, agent_dir / filename)):
        if not path.is_file():
            raise SystemExit(f"AGENT_MISSING: {path}")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        actual = (data.get("model"), data.get("model_reasoning_effort"), data.get("sandbox_mode"))
        if data.get("name") != name or actual != protocol["ROLE_MODELS"][role]:
            raise SystemExit(f"AGENT_CONFIG_MISMATCH: {path}: {actual!r}")
        if not isinstance(data.get("developer_instructions"), str) or not data["developer_instructions"].strip():
            raise SystemExit(f"AGENT_INSTRUCTIONS_EMPTY: {path}")
    if not source_only and not filecmp.cmp(template, agent_dir / filename, shallow=False):
        raise SystemExit(f"AGENT_COPY_DIFFERS: {filename}")

# Every local Markdown pointer must resolve. No exact Chinese prose is a gate.
for path in [skill_dir / "SKILL.md", *sorted((skill_dir / "references").glob("*.md"))]:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        if not (path.parent / target.split("#", 1)[0]).is_file():
            raise SystemExit(f"REFERENCE_MISSING: {path}: {target}")

for label, root in verification_roots:
    result = subprocess.run(
        (sys.executable, str(root / "tests/test_protocol.py")),
        text=True, capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "DEV_TEAM_SKIP_RUNTIME_DRIFT": "1"},
    )
    if result.returncode != 0 or "PROTOCOL_SCENARIOS=PASS" not in result.stdout:
        raise SystemExit(f"{label}_PROTOCOL_TEST_FAILED: {result.stderr.strip() or result.stdout.strip()}")
print("VERIFY_RESULT=PASS")
PY
