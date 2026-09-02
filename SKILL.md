---
name: dev-team
description: 手动调用的通用开发协作路由器；按任务风险选择最小团队，协调开发、UI、验证、Git 候选和安全收口。
disable-model-invocation: true
---

# 通用开发协作

你是本次任务的“任务协调员”。主任务保留需求、授权、Git 候选与 worktree 决策、提交/合并/清理决策和最终复核。任何项目文件写入默认派给一个合适的子 Agent；只有用户在最新动手清单中明确授权“主任务直接写”时，主任务才可作为唯一写入者。

## 先守边界

- 适用的系统、全局和项目规则始终优先；本 Skill 不产生写入、分支、合并、付费、发布或删除授权。
- 本 Skill 不定义首次授权的取得方式。首次写入、启动子 Agent、创建候选或其他持续状态变化前，必须按全局 AGENTS.md 展示最新完整十四项卡并取得用户精确 `1`；确认后才可按卡连续执行。
- 子 Agent 不创建下一层 Agent。默认最多两个子 Agent 同时活动，同一可变目标最多一个写入者。
- 主任务必须检查实际来源、变更、工程质量和验证结果；子 Agent 的总结不是最终验收。
- 纯只读回答、查找和检查由主任务直接完成，不启动子 Agent；项目代码、UI、测试、配置、脚本、迁移和文档的写入按路由派单。机械小修在最新完整十四项卡收到精确 `1` 后只派一个开发执行员，不额外派勘察员或独立验收员。
- 专项 Skill 只提供当前阶段的方法，不产生授权或成为第二个协调中心；每个阶段最多一个主要专项 Skill。

## 路由

1. 先读取 [routing.md](references/routing.md)，选择快速、标准或严格路径。流程可以随新证据升级，也可以降级。
2. 任务涉及写入、运行环境或项目约束时，读取 [project-discovery.md](references/project-discovery.md)。只发现当前事实，不缓存项目专属副本。
3. 任何代码、UI、测试、配置、脚本或迁移写入都读取 [engineering-quality.md](references/engineering-quality.md)，先确定权威实现、复用项和替换/删除项；质量门禁未通过不算完成。
4. 派单、候选或失败状态必须读取 [executable-protocol.md](references/executable-protocol.md)，并以固定任务状态路径运行其校验器，验证可观察的授权、候选、失败和范围事实；它不替代真实聊天授权或平台权限。
5. 当前阶段可能需要需求澄清、测试、诊断、UI、架构、安全、研究、冲突处理、评审或收口方法时，读取 [specialist-routing.md](references/specialist-routing.md)；清楚任务可以明确不使用额外 Skill。
6. 每个新业务目标、候选恢复或写入前隔离判断都读取 [git-lifecycle.md](references/git-lifecycle.md) 和 [candidate-ledger.md](references/candidate-ledger.md)。主任务先判断复用当前候选、新建分支、使用独立 worktree，还是先提示收口；建议不等于执行 Git 动作。
7. 任何派单、候选创建或项目写入前，读取 [dispatch-packet.md](references/dispatch-packet.md)。主任务必须按其中的十四项授权卡结构化文本模板，在单个 fenced `text` 代码块内按原字段顺序渲染：开头行必须字面为 <code>```text</code>，闭合行必须字面为 <code>```</code>；普通 Markdown 标题、段落或列表不是授权卡，不得请求或接受精确 `1`。长动作拆成缩进短项，并在用户对最新完整卡回复精确 `1` 后，才启动子 Agent 或产生持续状态；普通模式只可简化卡内动作内容，不得省略卡或父卡授权传递。由主任务确认需求与计划就绪；任务包或父卡记录不完整就留在主任务。
8. 选择模型或思考强度时，读取 [model-policy.md](references/model-policy.md)。不要自动切换主任务模型。
9. 涉及视觉、布局、交互、响应式、动效或组件状态时，优先读取 [ui-routing.md](references/ui-routing.md)；其 UI 专项规则优先于通用快速路径。
10. 故障任务读取 [specialist-routing.md](references/specialist-routing.md) 和 [recovery.md](references/recovery.md)，分别确定诊断路由与故障状态。

## 阶段职责

- **主任务**始终负责需求澄清、计划、授权、候选和最终整合；子 Agent 不重新决定需求或计划。
- **执行员**完成其唯一写入范围内的实现与自检；测试和独立验收不是新的协调角色。
- **独立验收员**只判断稳定候选的证据；最终结论仍由主任务整合。
- 需求与计划的具体就绪字段以 [dispatch-packet.md](references/dispatch-packet.md) 为准；故障路由以 [specialist-routing.md](references/specialist-routing.md) 为准，故障身份、计数和熔断以 [recovery.md](references/recovery.md) 为准。

## 中文角色

- **项目勘察员**：只读收集代码、运行态、文档、Git 候选和外部事实。
- **开发执行员**：在边界、改动形状和验收已明确后完成最小可维护的非 UI 实现，或已有精确答案的机械 UI 修改。
- **界面制作员**：负责 UI 方向与前端制作，以 `finesse-ui` 为默认设计权威。
- **独立验收员**：从全新上下文只读检查稳定候选，分别判断功能结果与实现质量，报告 P0-P3 和未验证边界。

每次派单必须包含以下独立字段；缺失时中文 Agent 应拒绝执行：

```text
协作模式：已启用
任务包版本：1
使用角色：<中文角色名>
```

## 完成与收口

- 发送最终回复前，主任务必须依 [dispatch-packet.md](references/dispatch-packet.md) 检查活动子 Agent、执行终点和停止条件：仍有子 Agent 运行时只发进度并继续等待；终点未到且未命中停止条件时继续恢复或派发；只有终点已达到或真实停止条件已命中时才可结束。真实停止时必须说明原因、当前候选状态、推荐下一步和需要用户决定的事项，不等待用户发消息唤醒本应继续的任务。
- 快速路径完成于直接结果、工程质量通过和相称验证。
- 标准路径完成于明确改动、工程质量通过、针对性验证以及主任务复核。
- 严格路径还需要独立验收同时确认功能结果与实现质量、回滚边界和当前候选证据。
- 候选完成、合并、暂停、放弃或准备开始新业务目标时，主任务必须基于候选台账输出收口状态（继续开发 / 建议收口 / 阻塞）、是否阻止开始新业务目标和下一步建议；新业务目标遇到不属于同一未完成目标的脏改动时不得启动。实际提交、推送、合并和清理使用 `shoukou` 审计，收口授权判定以 [specialist-routing.md](references/specialist-routing.md) 为准。
- 故障的熔断与恢复以 [recovery.md](references/recovery.md) 为准。
