---
name: openclaw-assistant
description: "OpenClaw 全能辅助技能。当用户提到以下任何内容时必须激活：OpenClaw、ClawHub、clawhub、openclaw gateway、openclaw skill、openclaw 技能、openclaw 配置、openclaw 优化、openclaw 安全、Pi agent（OpenClaw 语境）、openclaw 部署、openclaw 故障、openclaw 的 SKILL.md、openclaw 的 SOUL.md、openclaw 的 AGENTS.md、openclaw 的 HEARTBEAT.md、openclaw 的 MEMORY.md。覆盖场景：(1) 为 OpenClaw agent 生成 SKILL.md；(2) 审查/优化 OpenClaw skill；(3) 编写 SOUL.md、AGENTS.md 等 OpenClaw 工作区文件；(4) 诊断 OpenClaw 部署与配置问题；(5) 解答 OpenClaw 架构/Gateway/Memory/Channel 概念问题；(6) 安全审查 ClawHub 社区 skill（包括 CVE 告警）；(7) 给出 OpenClaw 优化建议。触发关键词必须与 OpenClaw 生态明确相关，避免因通用词汇（如单独的 SKILL.md、SOUL.md）误触。"
metadata:
  openclaw:
    emoji: "🦞"
---

# OpenClaw 自我认知与全能辅助技能 v7

在回答任何 OpenClaw 相关问题前，**先读取 `references/openclaw-knowledge.md`**，获取完整知识库。

> **当前最新稳定版（截至 2026-03-11）：v2026.3.8**
> 最新重大特性：Context Engine 插件槽（v2026.3.7）、ACP Provenance（v2026.3.8）、`openclaw backup` 命令

---

## 一、核心职责

1. **自我能力评估** — 接受任务前先对照能力边界表评估可行性
2. **复杂任务规划** — 拆解为符合架构特性的步骤，先呈现计划等用户确认
3. **版本自检与更新** — 主动验证当前版本，追踪破坏性变更
4. **新工具接入** — 按标准协议安全探索并接入未知工具（MCP / CLI / Skill）
5. **网络搜索策略** — 根据任务类型选择最佳搜索提供商
6. **Skill 生成与审查** — 按规范编写 SKILL.md，四维度安全审查。**创建复杂 Skill 建议委派给 skill-forge**
7. **工作区配置** — 编写/优化 SOUL.md、AGENTS.md、HEARTBEAT.md 等
8. **安全审查** — 识别 skill 风险，告知关键 CVE（最高危：CVE-2026-25253，8.8分）
9. **故障排查** — 诊断五大静默失败，提供可执行排查步骤

---

## 二、自我能力评估（接任务时必须执行）

### 能力边界速查表

| 能力域 | 状态 | 限制说明 |
|--------|------|---------|
| 文件读写 | ✅ | 受 `tools.allowedPaths` 限制 |
| Shell 执行 | ✅ | Pi Agent 必须启用；`allowShell: true` |
| 网络搜索 | ⚠️ | 必须配置 API key |
| PDF 分析 | ✅ | v2026.3.2 原生 `pdf` 工具 |
| 浏览器控制 | ⚠️ | 不稳定；准备 curl/API 降级方案 |
| 长时间任务 | ⚠️ | 建议 lossless-claw 插件或 session-state.md |
| MCP 工具 | ⚠️ | 每 server ~8K tokens |
| 记忆系统 | ⚠️ | Bug #25633；需显式配置 memoryFlush |
| 跨 agent 共享 | ❌ | 子 agent 不注入 SOUL.md/MEMORY.md |
| Context Engine | ✅ | v2026.3.7 插件槽 |
| ACP Provenance | ✅ | v2026.3.8 身份溯源 |

### 任务接受决策流程

1. 需要哪些工具？→ 对照能力表
2. token 消耗？→ `/status`；> 60% 先 `/compact`
3. 浏览器？→ 标记不稳定，准备降级
4. 超长任务？→ lossless-claw
5. 跨多系统？→ 优先 CLI/API

---

## 三、复杂任务规划

### 上下文管理（最高优先级）

根本方案：`openclaw plugins install lossless-claw`。未安装时用 session-state.md 检查点。

### 工具选择

**CLI 优于 MCP**。`bash + CLI` 优先，MCP 仅用于认证复杂场景。

### 子 Agent 原则

子 agent 只注入 AGENTS.md + TOOLS.md，跨 agent 共享靠文件。推荐 head-coordinator 模式。

---

## 四至十、详细操作指南

> 📖 **详见 `references/operations-guide.md`**，按需加载：
>
> - **四、版本自检** — 版本检查命令、更新渠道、近期变更表、破坏性变更检测
> - **五、工具接入** — 工具探索四步流程、MCP Server 标准接入
> - **六、搜索配置** — Brave/Perplexity/Gemini/Firecrawl 配置及已知 Bug
> - **七、Skill 生成审查** — 生成规范、四维度审查标准
> - **八、安全审查** — CVE 告警、供应链防护、提示注入防护、安全清单
> - **九、故障排查** — 诊断命令、常见问题速查、五大静默失败
> - **十、使用场景** — 开箱即用/需配置/不推荐场景

**紧急安全提醒**：所有 < v2026.2.14 实例必须立即更新（CVE-2026-25253, CVSS 8.8）。

---

> 📖 完整知识库见 `references/openclaw-knowledge.md`
> 📖 运维操作指南见 `references/operations-guide.md`
