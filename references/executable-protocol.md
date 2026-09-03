# 可执行协作状态协议

本文件是授权卡、候选、交付证据、生产修复失败记录和唯一写入范围的唯一机器可验证定义。人类对话中的首次精确 `1`、平台实际沙箱和外部聊天历史不在仓库控制范围内；主任务必须根据当前 `dev-team` 授权卡与实际运行环境核验，不能被本协议伪装成已强制执行。

## 状态记录

每个任务使用稳定的 `task_id`。派单必须提供绝对 Skill 根和绝对、用户级非敏感状态路径；派单前、跨会话恢复和写入前都读取同一路径，不能从业务项目 cwd 猜测 `.dev-team` 位置。状态只记录可观察的协议事实，禁止写入真实聊天内容、凭证或敏感数据。结构与校验器由 `scripts/verify-protocol.py` 定义；字段必须恰好如下：

```json
{
  "protocol_version": 4,
  "migration": null,
  "task_id": "example-task",
  "lifecycle": "active",
  "skill_root": "/absolute/path/to/dev-team",
  "git_baseline": "1111111111111111111111111111111111111111",
  "ignored_untracked_policy": "excluded",
  "primary_branch": "main",
  "authorization_card": {
    "execution_mode": "普通",
    "version": "1",
    "business_goal": "短句",
    "candidate_and_worktree": "codex/example；/tmp/example",
    "execution_endpoint": "本地候选完成",
    "one_time_actions": ["短项"],
    "automatic_actions": ["短项"],
    "repair_and_reverify": ["短项"],
    "stop_conditions": ["短项"],
    "will_not_do": ["短项"],
    "progress_mode": "只汇报",
    "authorization_status": "已获得",
    "authorization_message": "1",
    "authorization_basis": "最新完整十四项卡的精确1"
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
    "task_kind": "bug",
    "user_visible_outcome": "用户原始症状不再出现",
    "target_entrypoint": "触发原始症状的真实入口",
    "feedback_signal": "已实际运行的稳定失败命令或步骤",
    "before_status": "red",
    "before_evidence": "修复前的退出码和关键错误摘要",
    "feedback_scope": ["tests"],
    "target_check": {"status": "pending", "evidence": null, "signal": "固定目标命令", "baseline_status": "failed", "baseline_evidence": "改动前退出码为 1"},
    "adjacent_regression": {"status": "pending", "evidence": null, "signal": "相邻回归命令", "baseline_status": "passed", "baseline_evidence": "改动前通过"},
    "real_environment": {"status": "pending", "evidence": null, "signal": "真实入口步骤", "baseline_status": "unknown", "baseline_evidence": null},
    "unverified_boundaries": []
  },
  "scope_control": {
    "authorization_card_version": "1",
    "status": "frozen",
    "in_scope": ["短句"],
    "out_of_scope": ["短句"],
    "completion_policy": "delivery-evidence-passed-no-open-blocker"
  },
  "finding_records": [],
  "failure_identity": {
    "id": "stable-defect-id",
    "symptom": "用户原始症状摘要",
    "stable_signal": "已实际运行的稳定失败命令或步骤"
  },
  "production_failure_count": 0,
  "failure_records": [],
  "recovery": {"kind": "none", "pre_recovery_authorization": null, "diagnosis_authorization": null, "new_evidence": null, "diagnosis_stage": null, "diagnosis_conclusion": null, "repair_stable_signal": null, "repair_hypothesis": null, "repair_authorization": null, "previous_failure_ids": []},
  "write_scope": {
    "initial_allowed_paths": ["src", "tests"],
    "discovered_paths": []
  }
}
```

新任务使用当前协议版本 4。已经启动并固定版本的 v2、v3 任务继续按原 schema 校验，不因运行时升级而热切换；v1 只允许显式迁移到不虚构交付证据的 v2，并记录来源版本 `1` 和 ISO-8601 时间。v2 升级到 v3 必须由主任务根据真实运行补齐 `delivery_evidence`；v3 不自动升级到 v4，也不伪造范围冻结或验收基线。字段或语义变化必须递增协议版本；禁止把不同 schema 都称为同一版本。

`authorization_card` 的 14 个字段、候选字段和枚举由脚本精确解析。用于派单或写入前门禁的状态记录必须是“已获得”，并同时记录消息 `1` 与依据 `最新完整十四项卡的精确1`；未授权草稿不能通过本校验器。主任务核对聊天中的授权事实；子 Agent 只核对收到的父卡快照和状态一致，不得因看不到主对话而重新裁定授权。授权卡中的候选与 worktree 必须一致，且 worktree 必须为绝对路径。隔离只允许“复用当前候选、主分支直接写、当前目录候选分支、独立分支与 worktree、先收口或明确保留”。默认实时门禁读取当前 Git 分支，再优先解析 `origin/HEAD`，缺失时读取仓库配置 `dev-team.primaryBranch`。仅当实际分支等于解析主分支时，隔离必须为“主分支直接写”，且状态 `primary_branch` 与候选分支都必须匹配；普通非主分支候选不因主分支元数据缺失而失败。解析 `origin/HEAD` 只移除固定 `refs/remotes/origin/` 前缀，因此保留 `release/main` 等带斜杠的分支名。

`failure_identity` 将同一故障绑定到稳定信号；每条失败记录包含唯一的可证伪假设和时间，失败次数必须等于记录数。非故障任务可以将 `failure_identity` 设为 `null`，但必须同时保持零失败、空记录、`none` 恢复字段和非 recovery lifecycle。失败次数少于三次时，不得处于任一 recovery lifecycle。第三次失败后，普通修复状态被拒绝；先进入 `recovery-diagnosis`，保留全部失败 ID、新证据、诊断阶段及三次失败前的授权卡版本/证据，以及独立的诊断卡版本/证据。后续独立 `recovery-repair` 的当前授权卡版本必须可比较且严格晚于诊断卡，并且 `repair_authorization` 必须精确匹配当前替代卡；它还需要已完成诊断结论、同一稳定信号和未出现在失败历史中的新假设，不能清零或绕过三次历史。

`delivery_evidence` 是 v3 起的交付证据门禁。`task_kind` 只允许 `feature`、`bug`、`refactor`、`visual`、`documentation` 或 `operations`。新功能和 Bug 只允许从 `pending` 进入 `red`，并在生产行为写入前取得真实红灯；纯视觉任务只允许从 `pending` 进入 `captured`，并在调整生产 UI 前取得修复前浏览器基线。建立测试、复现或视觉基线时，候选保持“待判断”；无论 `before_status` 是否刚刚取得 red/captured，只要候选仍是“待判断”，实际 diff 就必须全部位于 `feedback_scope`。`feedback_scope` 必须包含在总写入范围内；主任务确认反馈成立并把候选转入“开发中”后，生产写入才可使用总范围。Bug 的 `feedback_signal` 必须与 `failure_identity.stable_signal` 相同。三个检查都保存状态与可复查证据：目标检查不能标为不适用；相邻回归和真实环境确实不适用时必须用证据字段说明原因。v4 额外要求每个检查记录固定 `signal`、改动前的 `baseline_status` 与 `baseline_evidence`；基线与 `git_baseline` 分开。候选标记“可收口”或“已收口”前，目标检查必须通过，相邻回归和真实环境必须通过或有明确的不适用理由。`unverified_boundaries` 单独保留仍未覆盖的边界，不能藏在绿色总结里。

## v4 范围冻结与发现分流

v4 的 `scope_control` 必须绑定当前授权卡版本并处于 `frozen` 状态，明确 `in_scope`、`out_of_scope` 和固定完成策略 `delivery-evidence-passed-no-open-blocker`。目标、排除项或完成策略变化时，必须先由主任务出示新版十四项授权卡；执行员和验收员不能在运行中自行提高标准。

`finding_records` 将每个新发现固定为 `current-blocker`、`deferred` 或 `scope-change`。当前阻塞必须有 `target-required`、`introduced-by-current-diff` 或 `worsened-by-current-diff` 的因果关系及证据，且只能使用 `repair-current`。`deferred` 只能 `record-only`，不能成为当前候选的写入理由或阻塞。`scope-change` 只能 `stop-for-decision`；只要它仍为 open，候选状态和收口状态都必须是“阻塞”，不得自动派单或创建任务。

v4 的 `discovered_paths` 除原字段外，必须记录授权卡版本、来源种类、来源 ID 与因果证据。来源只允许 `target-authority`、`acceptance-check`、`current-blocker`：前者的来源 ID 必须是 `scope-control`，验收来源 ID 必须是 `target_check`、`adjacent_regression` 或 `real_environment`，最后一种必须引用现有的当前阻塞。`deferred` 和 `scope-change` 永远不能扩张写入范围。存在 open 的当前阻塞或范围变化时，候选不得进入“可收口”或“已收口”；open 的 deferred 可以保留，不影响收口。

协议只能校验这些证据字段是否完整、一致，不能证明命令真的运行过。开发执行员运行并回报原始证据；独立验收员从稳定候选重新运行关键反馈信号、目标检查和真实入口。两者的总结都不能替代主任务对实际结果的复核。

`blocks_new_business_goal` 由候选状态而非仅当前 diff 决定：除候选状态为“已收口”外，开发、验证、待验收、阻塞、可收口等所有活跃状态必须为 `true`，即使工作树干净或成果已经本地提交；只有“已收口”可为 `false`。

写入范围保留语义授权边界：`git_baseline` 是任务开始时的候选提交，必须是当前候选 `HEAD` 的祖先；范围检查比较该基线到当前工作树，因此也能发现任务后已提交的范围外改动。`ignored_untracked_policy` 固定为 `excluded`：Git 已忽略且未跟踪的运行产物不属于候选源码范围，不做逐文件快照或哈希；已跟踪 diff、普通未跟踪文件、gitlink、稀疏检出和特殊 Git 索引仍受实时门禁。`initial_allowed_paths` 是派单初始范围；首次发现共享权威入口或相邻测试时，写入 `discovered_paths`。v2/v3 每项记录路径、理由、与授权卡完全相同的业务目标和发现时间；v4 还记录授权卡版本、受限来源和因果证据。未在两类路径中声明的源码变化仍被拒绝，发现项不是任意白名单。

## 可执行检查

```sh
python3 /absolute/path/to/dev-team/scripts/verify-protocol.py --skill-root /absolute/path/to/dev-team --state-dir /Users/you/.codex/state/dev-team --state /Users/you/.codex/state/dev-team/example-task.json --repo /absolute/path/to/target-git-root
python3 scripts/verify-protocol.py --state tests/fixtures/protocol/valid.json --structure-only
```

默认调用执行实时门禁：要求 `--repo` 为 Git 真实根目录，再将候选分支、worktree 和需要时的主分支解析结果与 Git 实况比对，并检查已跟踪和普通未跟踪的源码变化都在初始或可审计发现范围内。Git 已忽略且未跟踪的运行产物由 v2 明确排除。为保证已跟踪范围观察可靠，拒绝任何 gitlink（模式 `160000`）、稀疏检出与带 assume-unchanged、skip-worktree 或其他特殊标记的 Git 索引。正在校验的固定状态文件会被精确排除，不能因自身持久化而成为范围外 diff；同一用户级状态目录允许其他任务的固定状态文件共存，但它们不扩大当前任务范围。仅 `--structure-only` 跳过实时门禁，用于 fixture 格式测试；派单和写入前不得使用它。执行终点允许固定枚举，或 `自定义：` 加非空结束条件；裸“自定义”无效。`__pycache__` 同时受 setup 的独立缓存门禁约束。

状态记录证明的是本地可观察事实，不能证明用户的聊天回复真实对应某张卡，也不能将 TOML 的 `sandbox_mode` 变成平台硬路径沙箱。派单仍须完整传递父卡，执行员仍须核对实际生效权限。
