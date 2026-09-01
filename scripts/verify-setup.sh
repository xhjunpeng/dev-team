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
import re
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
    "SKILL.md",
    "references/glossary.md",
    "references/project-discovery.md",
    "references/engineering-quality.md",
    "references/specialist-routing.md",
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
    if not source_only:
        runtime_path = runtime_skill_dir / relative
        if not runtime_path.is_file():
            raise SystemExit(f"RUNTIME_SKILL_MISSING: {runtime_path}")
        if not filecmp.cmp(path, runtime_path, shallow=False):
            raise SystemExit(f"RUNTIME_SKILL_DIFFERS: {relative}")
if "[TODO:" in skill_text[frontmatter_match.end():]:
    raise SystemExit("SKILL_UNFINISHED_TODO")

for marker in (
    "name: dev-team",
    "disable-model-invocation: true",
    "快速、标准或严格路径",
    "engineering-quality.md",
    "specialist-routing.md",
    "阶段职责",
    "需求与计划就绪",
    "连续执行授权",
    "连续模式在启动任何操作前，主任务必须按其中的连续卡模板原样逐行渲染，并使用其固定枚举与终点必需动作；没有完整卡不得启动",
    "子 Agent 返回只表示其派单阶段结束，不表示主任务或业务目标完成",
    "不等待用户消息唤醒，也不得把普通进度写成“下一步：无需操作”",
    "收口授权判定以 [specialist-routing.md](references/specialist-routing.md) 为准",
):
    if marker not in skill_text:
        raise SystemExit(f"SKILL_MARKER_MISSING: {marker}")

dispatch_text = (skill_dir / "references/dispatch-packet.md").read_text(encoding="utf-8")
for marker in (
    "需求与计划就绪",
    "使用对象或对象群：",
    "可观察的验收标准：",
    "唯一写入者：",
    "交回主任务/停止条件：",
    "故障派单字段",
    "写入类别：只读诊断 / 诊断工具写入 / 生产修复",
    "恢复目标类型：否 / 诊断 / 生产修复",
    "恢复诊断结论（生产修复才填）：",
):
    if marker not in dispatch_text:
        raise SystemExit(f"DISPATCH_PACKET_MARKER_MISSING: {marker}")
for marker in ("[specialist-routing.md](specialist-routing.md)", "[recovery.md](recovery.md)"):
    if marker not in dispatch_text:
        raise SystemExit(f"DISPATCH_PACKET_AUTHORITY_POINTER_MISSING: {marker}")
for marker in ("不能以 `tdd`", "恢复字段只在失败次数达到 3"):
    if marker in dispatch_text:
        raise SystemExit(f"DISPATCH_PACKET_PARALLEL_RULE: {marker}")
for marker in (
    "连续执行授权",
    "执行模式：普通 / 连续执行",
    "连续清单版本：",
    "业务目标：",
    "准确候选与 worktree：",
    "执行终点：本地候选完成 / PR 可评审 / 已合并并清理 / 自定义",
    "本次一次性授权动作：",
    "满足条件后自动执行的动作：",
    "自动修复与复验策略：",
    "必须停止的情况：",
    "明确不会执行：",
    "进度汇报方式：只汇报 / 需要确认",
    "授权状态：未获得 / 已获得",
    "授权消息：",
    "授权依据：",
    "明确连续授权",
    "已有实施授权",
    "提案确认",
    "全局规则已授予当前明确范围内的本地实施授权",
    "枚举行硬门槛：执行模式行必须逐字且整行仅为“执行模式：普通”或“执行模式：连续执行”；授权状态行必须逐字且整行仅为“授权状态：未获得”或“授权状态：已获得”",
    "不得使用“连续执行提案”“待用户确认”“模拟执行”等同义状态",
    "父连续清单版本：",
    "父业务目标：",
    "父准确候选与 worktree：",
    "本阶段允许动作：",
    "新会话或新线程不得仅凭摘要、截图或旧卡继承授权",
    "渲染硬门槛：展示给用户的初始卡和替代卡必须按上述十四个原始字段标签、原始顺序逐行呈现",
    "不得用同义标题、说明性列表、合并项或另起十四项替代",
    "字段值未知时明确写“待只读核对”，但标签不得省略",
    "缺少任何原始标签或使用未允许的枚举值的卡不是完整卡，不得启动、请求或接受精确1",
    "提案确认的未授权卡在授权依据中",
    "授权消息记录触发授权的原始消息或精确1",
    "版本递增的完整替代连续执行清单",
    "不能用简略动作列表、摘要或“新清单”替代",
    "缺任一字段不得请求或接受新的精确1",
    "主任务终点门禁",
    "子 Agent 返回只表示本派单阶段结束，不表示主任务或业务目标完成",
    "未达到执行终点且未命中停止条件时，主任务必须继续等待、恢复或派发下一阶段",
    "不得把批次完成当作整体完成、要求用户消息唤醒，或把普通进度写成“下一步：无需操作”",
    "动作边界与终点预设",
    "授权只覆盖当前版本的连续执行清单",
    "没有列出的提交、推送、PR、合并或删除不能借连续授权执行",
    "同一故障仍以 [recovery.md](recovery.md) 的熔断为准",
    "“本次一次性授权动作”或“满足条件后自动执行的动作”必须逐字包含“调用 `shoukou` 收口审计”，缺失则卡不完整，不得启动",
    "语义授权边界",
    "不是冻结的文件白名单",
    "按既有锁文件恢复本地依赖",
    "迁移相关代码函数/文件",
    "数据、数据库结构、部署或其他高风险迁移",
):
    if marker not in dispatch_text:
        raise SystemExit(f"CONTINUOUS_EXECUTION_MARKER_MISSING: {marker}")
for line in dispatch_text.splitlines():
    if "必须停止" in line and "迁移" in line and "数据、数据库结构、部署或其他高风险迁移" not in line:
        raise SystemExit(f"CONTINUOUS_EXECUTION_UNQUALIFIED_MIGRATION_STOP: {line}")

discovery_text = (skill_dir / "references/project-discovery.md").read_text(encoding="utf-8")
for marker in (
    "连续任务前置准备",
    "共享入口、相邻测试接缝或需要迁移的函数/文件",
    "工作树已有锁文件",
    "按既有锁文件恢复本地依赖不等于变更依赖或锁文件",
):
    if marker not in discovery_text:
        raise SystemExit(f"CONTINUOUS_DISCOVERY_MARKER_MISSING: {marker}")
continuous_card_labels = (
    "执行模式：普通 / 连续执行",
    "连续清单版本：",
    "业务目标：",
    "准确候选与 worktree：",
    "执行终点：本地候选完成 / PR 可评审 / 已合并并清理 / 自定义",
    "本次一次性授权动作：",
    "满足条件后自动执行的动作：",
    "自动修复与复验策略：",
    "必须停止的情况：",
    "明确不会执行：",
    "进度汇报方式：只汇报 / 需要确认",
    "授权状态：未获得 / 已获得",
    "授权消息：",
    "授权依据：",
)
label_positions = [dispatch_text.find(label) for label in continuous_card_labels]
if -1 in label_positions or label_positions != sorted(label_positions):
    raise SystemExit("CONTINUOUS_CARD_LABEL_SEQUENCE_INVALID")
for marker in ("连续清单有且只有两种启动路径", "替代卡按上述两种启动路径取得授权", "收到用户对最新清单的精确 `1` 后，执行到所列终点", "上述十个字段", "原授权已失效、用户的新变更请求和等待精确1"):
    if marker in dispatch_text:
        raise SystemExit(f"CONTINUOUS_EXECUTION_OLD_RULE: {marker}")
for marker in ("以dispatch有效卡为准", "收口消费既有授权", "审计前提满足时", "审计前提通过时消费既有授权"):
    if marker in dispatch_text:
        raise SystemExit(f"DISPATCH_SHOUKOU_DECISION_DUPLICATED: {marker}")

ledger_text = (skill_dir / "references/candidate-ledger.md").read_text(encoding="utf-8")
for marker in ("连续清单版本：", "连续执行终点：", "连续授权消息/依据：", "连续授权状态：", "旧会话摘要、截图或转述不是授权记录"):
    if marker in ledger_text:
        raise SystemExit(f"CANDIDATE_LEDGER_CONTINUOUS_AUTHORITY: {marker}")

glossary_text = (skill_dir / "references/glossary.md").read_text(encoding="utf-8")
if "[recovery.md](recovery.md)" not in glossary_text:
    raise SystemExit("GLOSSARY_RECOVERY_POINTER_MISSING")
if "一个可证伪假设、一次有边界的代码改动" in glossary_text or "诊断工具写入不计生产修复尝试" in glossary_text:
    raise SystemExit("GLOSSARY_PARALLEL_REPAIR_ATTEMPT_DEFINITION")

recovery_text = (skill_dir / "references/recovery.md").read_text(encoding="utf-8")
for marker in ("故障身份与稳定红色失败信号", "诊断工具写入与生产修复尝试", "诊断记录", "可靠复现信号：", "可证伪假设及预测：", "交回主任务的条件：", "第三次仍失败", "恢复目标", "不是重试入口"):
    if marker not in recovery_text:
        raise SystemExit(f"RECOVERY_MARKER_MISSING: {marker}")

specialist_text = (skill_dir / "references/specialist-routing.md").read_text(encoding="utf-8")
for marker in (
    "每个阶段最多选择一个主要专项 Skill",
    "$to-spec",
    "`implement` 与开发执行员职责重复",
    "不自动安装、启用、禁用或更新任何 Skill",
    "故障诊断门槛",
    "不得派发生产修复",
    "先做审计；当前有效连续卡已准确覆盖当前候选的提交、合并、清理动作且审计前提通过时消费既有授权。未覆盖、失效、对象不一致或审计前提失败时停止并重新出卡/取得授权；卡的有效性见 `dispatch-packet.md`",
):
    if marker not in specialist_text:
        raise SystemExit(f"SPECIALIST_ROUTING_MARKER_MISSING: {marker}")

scenario_text = (skill_dir / "tests/scenarios.md").read_text(encoding="utf-8")
for marker in ("明确机械小修", "未知根因 Bug", "普通功能实现", "项目未采用 Matt 体系", "需求与计划就绪", "只读故障诊断", "测试与验收分工", "未知根因先诊断", "错误的诊断工具路由", "第三次失败后的伪装修复", "有新条件的恢复目标", "连续本地候选", "连续 PR 可评审", "连续验收回环", "未列合并", "明确条件合并与当前候选清理", "简单机械小修", "有效连续收口", "未覆盖或失效的收口", "明确全部授权", "UI 无关键选择直通", "UI 关键选择停止", "连续授权传递缺失", "替代卡与跨会话恢复", "准确候选动作", "自定义字段、状态或收口动作", "UI Design Read 已确认但写入权限未获得", "共享权威入口", "锁文件依赖恢复", "代码函数/文件迁移继续", "数据、数据库结构、部署类迁移停止", "真实越界", "源码候选目录验证", "明确开发请求继承实施授权", "子 Agent 批次返回但仍有剩余", "达到连续执行终点", "真实停止条件优先"):
    if marker not in scenario_text:
        raise SystemExit(f"SPECIALIST_SCENARIO_MISSING: {marker}")
for line in scenario_text.splitlines():
    if "预期立即停止" in line and "迁移" in line and "数据、数据库结构、部署或其他高风险迁移" not in line:
        raise SystemExit(f"SPECIALIST_SCENARIO_UNQUALIFIED_MIGRATION_STOP: {line}")

expected = {
    "team-explorer.toml": ("项目勘察员", "gpt-5.6-luna", "medium", "read-only"),
    "team-developer.toml": ("开发执行员", "gpt-5.6-terra", "medium", "workspace-write"),
    "team-ui-maker.toml": ("界面制作员", "gpt-5.6-terra", "high", "workspace-write"),
    "team-reviewer.toml": ("独立验收员", "gpt-5.6-terra", "high", "read-only"),
}
for filename, values in expected.items():
    template = skill_dir / "templates" / "agents" / filename
    paths = (template,) if source_only else (template, agent_dir / filename)
    for path in paths:
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
            "team-explorer.toml": ("专项 Skill", "不安装、启用或模拟", "specialist-routing.md", "recovery.md", "完整读取 `diagnosing-bugs`", "诊断记录", "工具写入请求", "连续授权传递", "父连续清单版本"),
            "team-developer.toml": ("最小可维护实现", "技术债变化", "专项 Skill", "Matt `implement`", "自动化测试和功能自检", "specialist-routing.md", "recovery.md", "逐项核对派单字段", "拒绝写入并交回任务协调员", "连续授权传递", "父连续清单版本"),
            "team-ui-maker.toml": ("最小可维护实现", "后置覆盖", "技术债变化", "专项 Skill", "`prototype`", "交互、响应式和浏览器自检", "specialist-routing.md", "recovery.md", "逐项核对派单字段", "拒绝并交回任务协调员", "连续授权传递", "父连续清单版本", "[ui-routing.md](../../references/ui-routing.md) 定义的 Design Read 状态", "Design Read 状态不是“已确认”时", "操作权限：工作区写入", "写入授权：已获得", "Design Read 已确认仅取消二次设计确认，不替代写入授权"),
            "team-reviewer.toml": ("功能结果", "实现质量", "新增技术债", "专项 Skill", "`code-review`", "独立核查关键测试、功能或浏览器证据", "specialist-routing.md", "recovery.md", "按其核查派单、证据、计数、候选和恢复记录", "连续授权传递", "父连续清单版本"),
        }
        for marker in role_markers.get(filename, ()):
            if marker not in instructions:
                raise SystemExit(f"AGENT_QUALITY_GATE_MISSING: {path}: {marker}")
        if filename in ("team-developer.toml", "team-ui-maker.toml"):
            for marker in ("语义授权边界", "不是冻结的", "按既有锁文件恢复本地依赖", "突破明确排除项"):
                if marker not in instructions:
                    raise SystemExit(f"AGENT_CONTINUOUS_SCOPE_GATE_MISSING: {path}: {marker}")
        for marker in ("失败次数达到 3", "允许的 diagnosing-bugs 阶段：1–4", "恢复诊断结论"):
            if marker in instructions:
                raise SystemExit(f"AGENT_PARALLEL_FAULT_RULE: {path}: {marker}")
    if not source_only and not filecmp.cmp(template, agent_dir / filename, shallow=False):
        raise SystemExit(f"AGENT_COPY_DIFFERS: {filename}")

print("VERIFY_RESULT=PASS")
PY
