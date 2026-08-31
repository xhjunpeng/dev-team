#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
agent_dir=${1:-/Users/jumper/.codex/agents}
runtime_skill_dir=${2:-/Users/jumper/.codex/skills/dev-team}

python3 - "$skill_dir" "$agent_dir" "$runtime_skill_dir" <<'PY'
from pathlib import Path
import filecmp
import re
import sys
import tomllib

skill_dir = Path(sys.argv[1])
agent_dir = Path(sys.argv[2])
runtime_skill_dir = Path(sys.argv[3])

required = [
    "SKILL.md",
    "references/glossary.md",
    "references/project-discovery.md",
    "references/engineering-quality.md",
    "references/git-lifecycle.md",
    "references/candidate-ledger.md",
    "references/routing.md",
    "references/dispatch-packet.md",
    "references/model-policy.md",
    "references/ui-routing.md",
    "references/recovery.md",
    "tests/scenarios.md",
]
for relative in required:
    path = skill_dir / relative
    if not path.is_file():
        raise SystemExit(f"MISSING: {path}")
    runtime_path = runtime_skill_dir / relative
    if not runtime_path.is_file():
        raise SystemExit(f"RUNTIME_SKILL_MISSING: {runtime_path}")
    if not filecmp.cmp(path, runtime_path, shallow=False):
        raise SystemExit(f"RUNTIME_SKILL_DIFFERS: {relative}")

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
if skill_dir.name != frontmatter["name"]:
    raise SystemExit("SKILL_DIRECTORY_NAME_MISMATCH")
if "[TODO:" in skill_text[frontmatter_match.end():]:
    raise SystemExit("SKILL_UNFINISHED_TODO")

for marker in (
    "name: dev-team",
    "disable-model-invocation: true",
    "快速、标准或严格路径",
    "engineering-quality.md",
    "第三次修复仍失败后硬停止",
):
    if marker not in skill_text:
        raise SystemExit(f"SKILL_MARKER_MISSING: {marker}")

expected = {
    "team-explorer.toml": ("项目勘察员", "gpt-5.6-luna", "medium", "read-only"),
    "team-developer.toml": ("开发执行员", "gpt-5.6-terra", "medium", "workspace-write"),
    "team-ui-maker.toml": ("界面制作员", "gpt-5.6-terra", "high", "workspace-write"),
    "team-reviewer.toml": ("独立验收员", "gpt-5.6-terra", "high", "read-only"),
}
for filename, values in expected.items():
    template = skill_dir / "templates" / "agents" / filename
    installed = agent_dir / filename
    for path in (template, installed):
        if not path.is_file():
            raise SystemExit(f"AGENT_MISSING: {path}")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        actual = (
            data.get("name"),
            data.get("model"),
            data.get("model_reasoning_effort"),
            data.get("sandbox_mode"),
        )
        if actual != values:
            raise SystemExit(f"AGENT_CONFIG_MISMATCH: {path}: {actual!r}")
        instructions = data.get("developer_instructions", "")
        for marker in ("协作模式：已启用", "任务包版本：1", "不要创建子 Agent"):
            if marker not in instructions:
                raise SystemExit(f"AGENT_GATE_MISSING: {path}: {marker}")
        role_markers = {
            "team-developer.toml": ("最小可维护实现", "技术债变化"),
            "team-ui-maker.toml": ("最小可维护实现", "后置覆盖", "技术债变化"),
            "team-reviewer.toml": ("功能结果", "实现质量", "新增技术债"),
        }
        for marker in role_markers.get(filename, ()):
            if marker not in instructions:
                raise SystemExit(f"AGENT_QUALITY_GATE_MISSING: {path}: {marker}")
    if not filecmp.cmp(template, installed, shallow=False):
        raise SystemExit(f"AGENT_COPY_DIFFERS: {filename}")

print("VERIFY_RESULT=PASS")
PY
