# 可执行协作状态协议

`scripts/verify-protocol.py` 是唯一机器协议实现；本文件解释字段和操作。校验器验证记录结构、一致性与实时 Git，不能证明用户聊天授权、命令真的运行、模型内部身份或沙箱隔离。主任务核对这些原始事实，执行员回报，验收员独立抽查。

## 一份记录

每任务固定 `task_id` 与绝对用户级状态路径，由主任务维护。派单、写入和跨上下文恢复读取同一文件，带准确权威 Skill 根；记录必要非敏感授权摘要/消息位置和证据，不复制无关聊天或秘密。已有字段的严格结构由脚本解析；本例展示 v5 小修记录（路径与证据须替换为真实事实）：

```json
{
  "protocol_version": 5,
  "migration": null,
  "task_id": "protocol-test",
  "lifecycle": "active",
  "skill_root": "/tmp/dev-team",
  "git_baseline": "1111111111111111111111111111111111111111",
  "ignored_untracked_policy": "excluded",
  "primary_branch": "main",
  "authorization_card": {
    "execution_mode": "普通",
    "version": "1",
    "business_goal": "修正文档错字",
    "candidate_and_worktree": "codex/example；/tmp/example",
    "execution_endpoint": "本地候选完成",
    "one_time_actions": [
      "修改 allowed/initial.txt 中的错字"
    ],
    "automatic_actions": [
      "复验"
    ],
    "repair_and_reverify": [
      "修复范围内问题"
    ],
    "stop_conditions": [
      "范围变化"
    ],
    "will_not_do": [
      "提交"
    ],
    "progress_mode": "只汇报",
    "authorization_status": "已获得",
    "authorization_message": "请修正 allowed/initial.txt 中的错字并验证",
    "authorization_basis": "主任务核对当前明确执行请求，范围仅为该文件"
  },
  "candidate": {
    "branch": "codex/example",
    "worktree": "/tmp/example",
    "isolation": "当前目录候选分支",
    "state": "开发中",
    "closeout_state": "继续开发",
    "blocks_new_business_goal": true
  },
  "delivery_evidence": {
    "task_kind": "documentation",
    "user_visible_outcome": "修正文档错字",
    "target_entrypoint": "allowed/initial.txt",
    "feedback_signal": "检查文档差异",
    "before_status": "captured",
    "before_evidence": "已读取原始文本 initial",
    "feedback_scope": [
      "allowed"
    ],
    "target_check": {
      "status": "pending",
      "evidence": null,
      "signal": "检查 allowed/initial.txt 的实际内容与差异",
      "baseline_status": "unknown",
      "baseline_evidence": null
    },
    "adjacent_regression": {
      "status": "pending",
      "evidence": null,
      "signal": "检查关联文档引用",
      "baseline_status": "unknown",
      "baseline_evidence": null
    },
    "real_environment": {
      "status": "not-applicable",
      "evidence": "局部文档修改没有外部运行环境",
      "signal": "核对该任务是否有外部运行环境",
      "baseline_status": "unknown",
      "baseline_evidence": null
    },
    "unverified_boundaries": [],
    "verification_mode": "standard"
  },
  "scope_control": {
    "authorization_card_version": "1",
    "status": "frozen",
    "in_scope": [
      "修正文档错字"
    ],
    "out_of_scope": [
      "不处理其他协议规则"
    ],
    "completion_policy": "delivery-evidence-passed-no-open-blocker"
  },
  "finding_records": [],
  "failure_identity": null,
  "production_failure_count": 0,
  "failure_records": [],
  "recovery": {
    "kind": "none",
    "pre_recovery_authorization": null,
    "diagnosis_authorization": null,
    "new_evidence": null,
    "diagnosis_stage": null,
    "diagnosis_conclusion": null,
    "repair_stable_signal": null,
    "repair_hypothesis": null,
    "repair_authorization": null,
    "previous_failure_ids": []
  },
  "write_scope": {
    "initial_allowed_paths": [
      "allowed"
    ],
    "discovered_paths": []
  },
  "task_assessment": {
    "difficulty": "small",
    "operation_risk": "reversible"
  },
  "authorization_context": {
    "source": "explicit-request",
    "intent": "execute",
    "granted_actions": [
      {
        "action": "workspace-write",
        "target": "allowed/initial.txt"
      }
    ],
    "planned_actions": [
      {
        "action": "workspace-write",
        "target": "allowed/initial.txt"
      }
    ]
  },
  "collaboration": {
    "writer": "main",
    "dispatches": [],
    "independent_review": {
      "status": "not-applicable",
      "reviewer_id": null,
      "evidence": "局部可逆文档小修，由主任务复核"
    }
  },
  "quality_exceptions": [],
  "diagnostic_events": []
}
```

`authorization_card` 保留既有 14 个内部字段，v5 不要求用户逐字填写或固定展示格式。授权版本与 `scope_control.authorization_card_version` 相等；候选分支和绝对 worktree 与 card 完全匹配。终点可以是本地候选完成、PR 可评审、已合并并清理，或 `自定义：` 加准确条件，终点本身不授权动作。

## v5 动作授权

`task_assessment` 分开 difficulty（small/normal/complex）和 operation_risk（read-only/reversible/high-risk）。`authorization_context.source` 为 explicit-request、explicit-consent 或 shortcut；intent 为 execute 或 discuss。shortcut 的消息须为 `1`；自然语言授权记录非空消息与依据，不用 NLP 裁定聊天真实性。

`granted_actions` 是已获授权的动作，`planned_actions` 是本阶段将执行的动作。动作必须是脚本 ACTION_KINDS 中的明确种类，target 是准确对象，禁用通配符。每个 planned 的 action/target 必须与 grant 完全匹配；没有计划动作时只记录状态或只读观察，不构成写入授权。

- workspace-write 的 target 为规范仓库相对文件或明确目录，目录覆盖其后代；不能使用 `.` 泛授权根目录。实际累计 diff 还须同时在 write_scope 和已授权 workspace-write 对象内。
- read/verify 只允许只读读取与无外部副作用检查。会生成本地源码/夹具的检查需相应 workspace-write；高风险验证或外部执行使用相应动作，不能包装为 verify。
- Git/外部对象采用可核验的精确字符串，如 `origin:codex/example->main`、`origin:codex/example`、绝对 worktree 路径、生产资源 ID。机器匹配动作/对象，不替代真实远端解析、保护规则或执行时核对。
- HIGH_RISK_ACTIONS 中的合并、删除、强推、部署、数据/结构迁移、生产写入、付款、密钥/安全改变和恢复修复，即使自报 reversible 也要求授权 grant 中有非空 impact 与 rollback。自报 high-risk 的其他写入同样要求这两项。无法回滚时明确写不可回滚及后果，并由用户明确同意，不得填含糊占位。

讨论或 read-only 风险不允许计划写入或实际新 diff；本地记录不能为高风险动作提供真实聊天许可。PR grant 不匹配 merge，文件甲不匹配文件乙。跨阶段使用同一授权：已完成 diff 由累计 grants 覆盖，当前 planned 不要求重新列出全部历史动作。

## 协作与例外

`collaboration.writer` 为 main、当前执行员 ID 或 null；`dispatches` 仅记录当前有效派发，包含 id、role、model、effort、permission 与工具请求/回执摘要 observation。role 为 developer/ui-maker/reviewer/explorer，默认模型与权限见 ROLE_MODELS。只读角色不能改为可写，普通功能不能由 main 写，不能同时存在多个写入者。结束旧执行员后才更新当前派发；历史回执留在交接证据中，不新建一套任务状态。

模型/档位覆盖时增加 override，包含 reason、authorization_card_version、authorization_evidence；必须符合当前授权并经工具能力核验，不能用自报模型名证明真实运行。模型策略详见 [model-policy.md](model-policy.md)。

`independent_review` 保存 status、reviewer_id、evidence；通过必须指向当前只读 reviewer，不能是写入者。高风险完成必须 passed；合并、删除、部署、真实迁移、生产写入、付款或密钥操作等实际外部执行，在 planned_actions 阶段就需要 passed，不能用“开发中”绕过。安全代码和恢复修复可以先实现再验收，但不能借此执行外部高风险动作。其他任务不适用时给理由；已经决定需要验收而仍 pending/failed 也不能完成。`quality_exceptions` 记录实现取舍的 id、reason、boundary、exit_condition、authorization_card_version、authorization_evidence、status（pending/approved）；未批准例外不能完成，已批准也不能放松固定检查或安全门禁。

## 交付证据

v5 的 `delivery_evidence` 增加 verification_mode：

| task_kind | verification_mode | 实现前证据 |
| --- | --- | --- |
| bug | bug-repro | red，原始症状/信号必须与 failure_identity 一致 |
| bug | bug-diagnosis | captured 的日志/追踪与未验证边界，只能修改 feedback_scope，结果是可诊断性 |
| visual | existing-ui | captured 的准确现有页面/状态 |
| visual | new-ui | not-applicable，解释不存在旧页面 |
| feature/refactor/documentation/operations | standard | 相称的 captured/baseline-green/red/not-applicable，不能用 pending 宣称实现就绪 |

“待判断”阶段所有实际 diff 限 feedback_scope，无论 before_status 是否已更新；主任务核对证据后转入开发中。bug-diagnosis 在全部阶段持续限制反馈范围，不能夹带生产修复。基线未知用 unknown，不适用给理由，不伪造历史证据。

每个固定检查保留 signal、status/evidence、baseline_status/baseline_evidence。目标检查必须通过；相邻回归和真实环境检查须通过或有明确不适用理由。仍需运行的关键检查不能被写成边界后强行通过。协议不解释证据文本中的真假，由真实命令和独立复核验证。

## v4/v5 范围冻结与发现分流

`scope_control` 绑定当前授权版本，status=frozen，保存 in_scope/out_of_scope 和固定 completion_policy=delivery-evidence-passed-no-open-blocker。实现者和验收者不能自行提高标准。

`finding_records` 使用 current-blocker / deferred / scope-change。当前阻塞必须有 target-required、introduced-by-current-diff 或 worsened-by-current-diff 因果证据，且 action=repair-current。deferred 仅 record-only；scope-change 仅 stop-for-decision，open 时必须阻塞候选及收口并停止写入，不能自动创建任务。

`discovered_paths` 保存 path、reason、business_goal、discovered_at、authorization_card_version、source_kind/source_id、causal_evidence。来源限 target-authority（scope-control）、acceptance-check（固定三个检查 ID）或 current-blocker（现有阻塞 ID）。无关发现和新增范围不扩张当前路径；v5 同时要求明确授权对象，不能靠新路径记录获得动作权限。

候选可收口/已收口前固定检查完成，无 open 当前阻塞或范围变化；open deferred 不阻塞。blocks_new_business_goal 只有已收口时为 false，其他状态为 true。任务本地完成不等于已提交、已合并或已启用。

## 原始故障与恢复

failure_identity 绑定原始症状和信号；failure_records 每条为独一可证伪假设、原始验证失败和时间，production_failure_count 等于记录数。v5 diagnostic_events 仅记录 environment/tool/syntax 与证据和时间，不计入原始修复失败。不能把实际证伪的假设改名为工具问题规避三次停止。

三次失败后的普通修复被拒绝；恢复先 recovery-diagnosis，携带全部失败 ID、新证据、旧授权快照和独立诊断授权；随后 recovery-repair 要求完成诊断、同一信号、新假设和晚于诊断的当前授权。v5 的恢复快照仍使用 card_version/authorization_message/authorization_basis，接受非空自然语言；修复计划另需准确故障 ID 的 recovery-repair 高风险授权。v2–v4 继续精确1校验。详见 [recovery.md](recovery.md)。

## 固定旧版本

新任务用 v5。v2–v4 不自动热迁移，明确按版本分派：v2 没有交付证据；v3 新增交付证据，只在已收口强制完成检查；v4 还对可收口执行固定检查、范围冻结、发现分流和路径因果门禁。v3/v4 feature/bug 必须 red，visual 必须 captured；v2–v4 授权继续完整旧卡与精确1。v1 仅显式迁移到 v2，记录来源版本和时间，不伪造交付证据。升级需要主任务补真实事实并显式决定，不能仅修改版本号。

## 实时门禁

```sh
python3 /absolute/path/to/dev-team/scripts/verify-protocol.py --skill-root /absolute/path/to/dev-team --state-dir /Users/you/.codex/dev-team/state --state /Users/you/.codex/dev-team/state/example-task.json --repo /absolute/path/to/target-git-root
python3 scripts/verify-protocol.py --state tests/fixtures/protocol/v5-explicit-request-valid.json --structure-only
```

默认验证 Git 真实根、基线为当前 HEAD 祖先、准确分支/worktree 与主分支解析、累计已跟踪与普通未跟踪 diff 范围。ignored_untracked_policy=excluded 保留 v2 起对 Git 已忽略未跟踪产物的排除；固定状态文件精确排除，不扩张其他文件范围。拒绝 gitlink、稀疏检出与 assume-unchanged/skip-worktree 等特殊索引。--structure-only 仅供夹具结构测试，不能替代派单、写入或恢复门禁。

运行 `python3 tests/test_protocol.py` 验证历史正反例及 v5 行为；`bash scripts/verify-setup.sh --source-only` 检查源码，完整安装验证另核对模板、运行时复制与测试。安装验证通过不等于已安装、模型已实际运行或业务已验收。
