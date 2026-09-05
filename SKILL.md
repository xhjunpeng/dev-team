---
name: dev-team
description: 手动调用的通用开发协作路由器；按任务风险选择最小团队，协调开发、UI、验证、Git 候选和安全收口。
disable-model-invocation: true
---

# 通用开发协作

主任务负责需求、授权、准确候选、阶段安排和最终复核。先分开判断任务难度与操作影响，再选择最小团队：局部可逆小修由主任务直做；普通功能由一个执行员实现；高风险任务由全新只读验收员独立验收。同一业务目标同一阶段只有一个写入者，子 Agent 不创建下一层 Agent，默认最多两个子 Agent 同时活动。

## 开始与恢复

1. 读取 [routing.md](references/routing.md) 选择快速、标准或严格路径。讨论和分析保持只读；明确普通执行请求可授权范围内必要读写验证。高风险动作须有准确对象、影响、回滚和明确同意。授权规则见 [dispatch-packet.md](references/dispatch-packet.md)，`1` 是快捷方式，不是唯一同意表达。
2. 写入或依赖项目事实时读取 [project-discovery.md](references/project-discovery.md)：确认适用项目技术约束、真实入口与已有成果。指令冲突按平台优先级处理；本 Skill 提供协作流程，项目的技术、安全、构建与验收约束仍适用，同一事项不叠加重复流程。
3. 涉及候选、派单或写入时读取 [executable-protocol.md](references/executable-protocol.md) 与 [candidate-ledger.md](references/candidate-ledger.md)，使用一份固定任务记录。新任务用 v5，已有 v2–v4 保持原版本；恢复时重核可能变化的授权、Git、范围、模型与权限事实。
4. 写入前读取 [engineering-quality.md](references/engineering-quality.md)，确定权威实现、复用和替换项、固定验收及已批准例外。目标、范围或验收未决时留在主任务。
5. 创建、恢复或处理 Git 候选时读取 [git-lifecycle.md](references/git-lifecycle.md)；准备派单时读取 [dispatch-packet.md](references/dispatch-packet.md) 和 [model-policy.md](references/model-policy.md)。主任务保留用户选定模型，派发参数必须与真实可用能力一致。
6. 需要专业方法时读取 [specialist-routing.md](references/specialist-routing.md)，每阶段最多一个主要专项 Skill。UI 读取 [ui-routing.md](references/ui-routing.md)；Bug 或多次失败读取 [recovery.md](references/recovery.md)。

## 阶段职责

- 主任务对聊天授权事实负责，并核对真实 diff、命令结果和当前候选；协议通过和执行员总结都不能代替验收。
- 项目勘察员只回答明确事实问题；普通功能使用一个开发执行员，需设计判断的页面使用界面制作员。角色默认模型与实际能力检查统一见模型策略。
- 独立验收员从全新上下文检查稳定候选，分别报告功能、实现质量和未验证边界。它只建议发现分类，不自行扩大范围或派单。

## 执行到授权终点

已授权范围内的必要准备、实现、验证和返工连续执行。子 Agent 返回是阶段完成；主任务仍有授权工作时继续，不要求用户再发消息唤醒。仍有活动子 Agent 时只发进度并等待。只有达到终点或命中真实停止条件才结束，停止时说明原因、候选状态、已保留结果和准确下一步。

固定检查完成且没有当前阻塞或未决范围变化，即停止返工；无关发现只记录。输出收口状态（继续开发 / 建议收口 / 阻塞）与是否阻止新目标。提交、推送、PR、合并和清理分别核对动作与准确对象；本地候选完成、PR 可评审都不自动授权后续 Git 动作。
