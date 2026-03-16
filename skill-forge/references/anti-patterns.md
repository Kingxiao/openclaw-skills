# Skill 反模式大全

本文档记录创建 Skill 时的 21 条常见反模式（Anti-Patterns），每条包含：问题描述、后果、修复方案和示例。

> **使用方式**：创建或审计 Skill 时，逐条对照排查。发现匹配项必须修复。

---

## 架构反模式

### AP-01: Context 膨胀 (Context Bloat)

**问题**：将所有内容塞进 SKILL.md body，不使用 references/ 目录。

**后果**：
- SKILL.md 超过 500 行，每次加载消耗大量 token
- Agent 可能因上下文过长导致"中间丢失"（lost-in-the-middle）现象
- 无关信息干扰 Agent 对核心指令的执行

**修复**：严格执行 L2/L3 分层。SKILL.md body ≤ 500 行，深度内容下沉到 `references/`。

### AP-02: 过度泛化 (Over-Generalization)

**问题**：一个 Skill 试图覆盖过广的领域（如 "全栈开发" skill）。

**后果**：每条指令都过于模糊，Agent 无法执行精确操作。效果还不如不加 Skill。

**修复**：收窄边界。一个 Skill 聚焦一个领域/技术栈。如需覆盖多个，创建多个独立 Skill。

### AP-03: 过度特化 (Over-Specialization)

**问题**：Skill 只适用于极窄的场景（如 "React 18.2.0 中 useEffect 的第三个参数" ）。

**后果**：触发条件极少被满足，投入产出比极低。

**修复**：将 Skill 范围设定在"一个完整的技术/方法论"粒度。

### AP-04: 扁平结构 (Flat Structure)

**问题**：所有文件平铺在 skill 目录根层，不按 references/scripts/examples 分类。

**后果**：Agent 无法判断哪些文件是核心指令、哪些是辅助参考。渐进式披露失效。

**修复**：严格遵循标准目录结构。

---

## 内容反模式

### AP-05: 闭门造车 (No Research)

**问题**：直接基于训练数据/记忆编写 Skill，不做联网调研。

**后果**：
- 版本号过时（推荐已废弃的 API）
- 遗漏重大生态变化（如 Zig 迁移到 Codeberg）
- Agent 执行的代码在目标版本上编译/运行失败

**修复**：阶段 1 必须联网搜索，确认版本号、API、最佳实践的最新状态。

### AP-06: 伪代码示例 (Pseudo-Code Examples)

**问题**：代码示例使用伪代码或省略关键部分（`// ... do something`）。

**后果**：Agent 无法判断正确的语法，可能生成不可编译/运行的代码。

**修复**：所有代码示例必须是可运行的最小完整版本。标注语言和版本。

### AP-07: 无根推荐 (Groundless Recommendations)

**问题**：直接给出 "使用 X 库" 的推荐，但不解释为什么。

**后果**：Agent 盲目遵从推荐，在不适用场景中也使用 X 库。

**修复**：每个推荐必须附带适用场景和选择理由。最好用决策表格呈现。

### AP-08: 信息过时 (Stale Information)

**问题**：Skill 创建后未根据技术演进更新。

**后果**：推荐的做法已过时，新版本中可能导致 bug 或安全漏洞。

**修复**：`metadata.last_updated` 必须反映真实更新日期。定期审计（至少每季度一次）。

### AP-09: 无 Pitfalls (Missing Pitfalls)

**问题**：省略 Known Pitfalls 章节。

**后果**：Agent 会踩入已知陷阱，因为它不知道这些陷阱存在。Pitfalls 是 Skill 最高价值的部分——Agent 最容易犯的错就是这些。

**修复**：必须包含 ≥ 3 条 Pitfalls，含问题+后果+修复。

---

## 安全反模式

### AP-10: 明文密钥 (Hardcoded Secrets)

**问题**：Skill 中包含真实的 API key、数据库密码、私钥等。

**后果**：密钥泄露。Skill 可能被共享或提交到公开仓库。

**修复**：使用占位符 (`YOUR_API_KEY_HERE`)。提示从环境变量/密钥管理器读取。

### AP-11: 危险命令无警告 (Unguarded Dangerous Commands)

**问题**：`rm -rf /`, `DROP DATABASE`, `FORMAT C:` 等命令直接写出,无警告。

**后果**：Agent 可能直接执行，造成数据丢失。

**修复**：破坏性命令必须标注 `⚠️ 危险操作` 警告，并添加安全防护建议。

### AP-12: 提示注入漏洞 (Prompt Injection Vectors)

**问题**：Skill 内容包含类似 "忽略之前的指令" 的文本，或包含可被恶意输入利用的模板。

**后果**：攻击者可能通过构造输入让 Agent 执行非预期操作。

**修复**：审计所有文本内容，移除任何可被解释为指令覆盖的内容。

---

## 格式反模式

### AP-13: Frontmatter 缺失 (Missing Frontmatter)

**问题**：SKILL.md 不以 YAML frontmatter 开头，直接写 markdown。

**后果**：L1 加载失效，Agent 无法判断此 Skill 的相关性，Skill 永远不会被激活。

**修复**：SKILL.md 必须以 `---` 开头的 YAML frontmatter 起始。

### AP-14: 触发条件模糊 (Vague Trigger Description)

**问题**：`description` 写得过于模糊，如 "帮助你写更好的代码"。

**后果**：每个任务都可能触发此 Skill（误触发），或永远不触发（触发失败）。

**修复**：`description` 必须包含具体的关键词列表（文件类型、命令名、技术名词）。

### AP-15: Name 与目录不匹配 (Name-Directory Mismatch)

**问题**：YAML 中 `name: react-frontend` 但目录名是 `react/` 或 `React-Frontend/`。

**后果**：某些平台会无法正确索引 Skill。

**修复**：`name` 字段值必须与目录名完全一致。

---

## 效率反模式

### AP-16: 信息重复 (Information Duplication)

**问题**：同一信息同时出现在 SKILL.md body 和 references/ 文件中。

**后果**：Token 浪费，且维护时容易出现两处不一致。

**修复**：SKILL.md body 中只写摘要 + 引用链接，完整内容仅在 references/ 中。

### AP-17: 叙事文风 (Narrative Style)

**问题**：Skill 用散文式长段落编写，而非结构化的列表/表格。

**后果**：LLM 解析精度下降，关键信息被淹没在文字中。

**修复**：优先使用：表格 > 编号列表 > 项目列表 > 段落。

### AP-18: 超大单文件 (Monolithic File)

**问题**：单个 reference 文件超过 1000 行。

**后果**：Agent 加载时消耗过多 token，且关注点分散。

**修复**：按子主题拆分为多个 reference 文件。

---

## 运维反模式

### AP-19: 无版本控制 (No Versioning)

**问题**：Skill 没有 `metadata.version` 字段。

**后果**：无法追踪变更历史，多人协作时无法判断是否为最新版本。

**修复**：必须包含语义化版本号，每次修改按规则递增。

### AP-20: 无日期标记 (No Date Stamp)

**问题**：Skill 没有 `metadata.last_updated` 字段。

**后果**：无法判断信息时效性。半年前创建的 Skill 可能已过时但无人知晓。

**修复**：必须包含更新日期，每次修改同步更新。

### AP-21: 未经审计直接提交 (No Audit Before Commit)

**问题**：创建完 Skill 直接 `git commit`，不执行质量审计。

**后果**：结构缺陷、内容错误、安全隐患带入仓库。下游 Agent 使用后问题被放大。

**修复**：提交前必须完成 `quality-checklist.md` 中所有 CRITICAL 项检查。Enterprise 级 Skill 必须运行 `validate-skill.sh`。
