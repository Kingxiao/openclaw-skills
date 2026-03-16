---
name: skill-forge
description: >
  生产级 Skill 创建元技能。创建、审计、修复、改进 AI Agent Skill，
  将领域知识编码为可复用的结构化指令集。
  Use when user says "帮我创建一个 skill"、"create a new skill"、
  "审查这个 skill 的质量"、"review this skill"、"skill 模板"、
  "批量生成 skill"。触发关键词：创建 skill、新建 skill、skill 质量审计、
  skill 审核、SKILL.md、skill-forge、元技能、meta-skill。
  核心能力：7 阶段创建流程、三层渐进式披露架构、50+ 项质量审计、
  21 条反模式检测、自动化验证脚本。适用于 OpenClaw 平台。
metadata:
  version: "1.2.0"
  last_updated: "2026-03-15"
  category: "meta-skill"
  complexity_support: "lite | standard | enterprise"
  standard: "Agent Skills Open Standard (2025)"
---

# Skill-Forge — 生产级 Skill 创建元技能

## 第一性原理

**Skill 的本质**：将人类专家的领域知识编码为 LLM 可消费的结构化指令集，使 Agent 在特定领域达到专家级输出。

**为什么需要 Skill？** → LLM 是通才，通才的弱点是在专业领域的深度不足。Skill 补偿这个缺陷——它是领域专家的"经验晶体"，注入后 Agent 从通才变为该领域的专家。

**为什么 Skill 质量至关重要？** → 低质量 Skill 比没有 Skill 更危险。错误的领域指导会被 Agent 放大执行，导致系统性偏差。Skill 是 Agent 的"基因组件"——基因缺陷会遗传到所有输出。

**渐进式披露的底层逻辑**：LLM 的 context window 是稀缺资源。Skill 必须按需加载，只在需要时才展开深层信息。这不是可选的优化——这是架构层面的硬约束。

---

## 当前状态 (2026年3月)

- **标准基础**：Anthropic Agent Skills Open Standard (2025) + 官方《The Complete Guide to Building Skills for Claude》
- **渐进式披露**：三层架构 (L1 frontmatter / L2 body / L3 references) 为官方推荐核心设计原则
- **分发方式**：Claude.ai Settings > Skills 上传、Claude Code `.claude/skills/` 目录、Skills API `/v1/skills` 端点
- **跨平台兼容**：同一 SKILL.md 格式可用于 Claude Code、Claude.ai、Gemini Antigravity、Cursor (需适配)

---

## 创建流程（7 个阶段）

创建 Skill 必须严格按以下顺序执行。跳过任何阶段将导致质量缺陷。

### 阶段 1：需求分析与领域调研

**目标**：确认 Skill 的边界与当前最新实践。

- 明确回答：这个 Skill 要解决什么问题？目标用户是谁？
- **必须联网搜索**该领域截至当前日期的最新状态。不要依赖训练数据。
  - 搜索该技术/领域的最新版本、已知突破性变更、废弃 API
  - 搜索当前行业最佳实践与社区共识
  - 搜索常见陷阱 (pitfalls) 和反模式
- 判定 Skill 复杂度等级（决定后续阶段的深度）：

| 等级 | 适用场景 | 结构 | 代表案例 |
|------|----------|------|----------|
| **Lite** | 单一框架/库的规范约束 | 仅 SKILL.md (≤100行) | NestJS, React, Taro |
| **Standard** | 一个完整技术栈或方法论 | SKILL.md + references/ | Python FastAPI 全栈, DevOps |
| **Enterprise** | 深度工程体系 + 安全 + 性能 | SKILL.md + references/ + scripts/ | Zig enterprise, K8s platform |

### 阶段 2：架构设计

**目标**：设计 Skill 的信息架构，确保渐进式披露正确。

三层架构（必须遵守）：

```
L1 — YAML Frontmatter（始终加载到 system prompt）
│    仅含: name, description, metadata
│    用途: Agent 判断"这个 skill 是否与当前任务相关"
│
L2 — SKILL.md Body（skill 相关时加载）
│    核心规范、关键代码示例、已知陷阱
│    约束: ≤ 500 行。超出部分必须下沉到 L3
│
L3 — references/ 目录（按需加载）
     深度参考文档、完整 API 指南、安全指南
     用途: 仅在需要深入某子主题时读取
```

**信息分配决策树**：
1. Agent 是否需要仅凭此信息判断 skill 相关性？ → L1
2. Agent 是否在 80% 的相关场景中需要此信息？ → L2
3. 此信息仅在特定深入场景需要？ → L3

设计 Skill 目录结构：

```
<skill-name>/
├── SKILL.md              # [必须] L1 + L2
├── references/           # [Standard+] L3 深度参考
│   ├── <topic-a>.md
│   └── <topic-b>.md
├── scripts/              # [Enterprise] 辅助脚本
│   └── <script>.sh
└── examples/             # [可选] 参考实现
    └── <example>/
```

### 阶段 3：编写 SKILL.md

**YAML Frontmatter 规范**（L1）：

```yaml
---
name: <kebab-case-name>          # 必须。与目录名一致。仅小写字母+数字+连字符。≤64字符
description: >                    # 必须。≤1024字符。描述功能 + 触发条件
  描述这个 skill 做什么，以及何时应该被激活。
  列出具体的触发关键词和文件类型。
metadata:                         # 推荐
  version: "1.0.0"                # 语义化版本
  last_updated: "YYYY-MM-DD"      # 最后更新日期
  language: "<lang>"              # 如适用
  category: "<category>"          # 分类标签
---
```

**frontmatter 命名规则**：
- `name` 仅包含 `[a-z0-9-]`，不含保留词(anthropic, claude, openai, gemini)
- `description` 必须包含明确的触发条件描述——Agent 靠这段文字决定是否加载

**Body 编写规范**（L2）：

1. **开头写第一性原理** — 不是"这个框架的介绍"，而是"为什么这样做"的底层逻辑
2. **核心规范用表格/列表** — 提高 LLM 的解析精度
3. **代码示例必须可运行** — 不写伪代码，写真实的最小可运行代码
4. **已知陷阱 (Known Pitfalls)** — 必须有独立章节。这是 Skill 最高价值的部分
5. **引用深层文档** — 用 `> 详见 references/<file>.md` 指向 L3
6. **≤ 500 行硬限制** — 超出截断到 references/

**Body 推荐结构**：

```markdown
# <Skill Name>

## 第一性原理 / 核心哲学
(为什么这样做，一切规范的底层逻辑推演)

## 当前状态 (xxxx年xx月)
(版本、生态、重大变更，必须基于调研)

## 1. <核心主题 A>
(规范、代码示例、注意事项)

## 2. <核心主题 B>
...

## N. Known Pitfalls
(编号列表，每条一句话 + 修复方案)

## 参考文档
(列出 references/ 中可用的深度文档)
```

### 阶段 4：编写 References（Standard 及以上）

**每个 reference 文件的规范**：
- 文件名用 `kebab-case.md`
- 聚焦单一子主题（如 `security.md`、`memory-patterns.md`）
- 开头一句话说明本文档的范围
- 可以长——这里没有行数限制，因为按需加载
- 包含完整代码示例、表格、决策矩阵

### 阶段 5：编写 Scripts（Enterprise）

**适用场景**：
- 验证脚本（lint、structure check）
- 代码生成器（scaffold）
- 构建/部署辅助

**脚本规范**：
- 首行 shebang（`#!/usr/bin/env bash`）
- `set -euo pipefail`（bash 严格模式）
- 头部注释说明用途
- 支持 `--help` 参数
- 返回码遵循 UNIX 惯例（0=成功, 1=失败）

### 阶段 6：质量审计

**必须**在提交前执行。使用以下检查清单：

> 完整审计清单详见 `references/quality-checklist.md`

**快速自检**（每个 skill 必过的最低标准）：

- [ ] `SKILL.md` 存在且以 YAML frontmatter 开头
- [ ] `name` 字段 kebab-case，≤64 字符，与目录名一致
- [ ] `description` 非空，≤1024 字符，包含触发条件
- [ ] Body ≤ 500 行
- [ ] 无硬编码 API key / 密码 / token
- [ ] 核心代码示例对应的版本号与调研结果一致
- [ ] Known Pitfalls 章节存在（≥3 条）
- [ ] 所有 `references/` 引用的文件实际存在

### 阶段 7：版本管理与提交

```bash
# 在 skills 仓库根目录
git add <skill-name>/
git commit -m "feat(<skill-name>): add <skill-name> skill v<version>

- <简述核心内容>
- Complexity: <Lite|Standard|Enterprise>
- Based on research as of <YYYY-MM-DD>"
```

**版本升级规则**：
- PATCH (x.x.1): 修复错误、更新过时信息
- MINOR (x.1.0): 新增章节、新增 reference 文件
- MAJOR (1.0.0): 重构架构、重大内容变更

---

## Skill 复杂度快速参考

### Lite（≤100 行 SKILL.md，无 references/）

适用于：单一框架的编码规范、一个 CLI 工具的使用指南。

```
<skill-name>/
└── SKILL.md
```

### Standard（≤500 行 SKILL.md + references/）

适用于：完整技术栈、开发方法论、包含多个子主题的领域。

```
<skill-name>/
├── SKILL.md
└── references/
    ├── <子主题-a>.md
    └── <子主题-b>.md
```

### Enterprise（SKILL.md + references/ + scripts/ + examples/）

适用于：深度工程体系、含安全/性能/部署的全生命周期指导。

```
<skill-name>/
├── SKILL.md
├── references/
│   ├── security.md
│   ├── performance.md
│   └── ...
├── scripts/
│   └── validate.sh
└── examples/
    └── quickstart/
```

---

## 反模式速查

> 完整列表详见 `references/anti-patterns.md`

| 反模式 | 后果 | 修复 |
|--------|------|------|
| Context 膨胀 — 所有内容堆在 SKILL.md | Token 浪费，Agent 性能下降 | 下沉到 references/ |
| 闭门造车 — 不调研直接写 | 信息过时，误导 Agent | 阶段 1 必须联网搜索 |
| 无验证闭环 — 不跑审计直接提交 | 结构错误上线 | 阶段 6 审计必须执行 |
| 过度泛化 — 一个 skill 覆盖所有 | 每条指令都模糊 | 收窄边界，一个 skill 一个领域 |
| 忽略安全 — 包含明文密钥或危险命令 | 安全事故 | 审计清单中的安全检查项 |

---

## 安全约束

1. **密钥零容忍**：生成的 Skill 中不得包含任何硬编码的 API key、token 或密码，一律使用环境变量注入
2. **提示注入防护**：生成的 Skill 若涉及处理外部内容（网页/文档/用户输入），必须包含提示注入防护声明
3. **脚本安全**：Enterprise 级 Skill 的 `scripts/` 中不得包含 `eval`、`exec`、`rm -rf /` 等危险操作
4. **权限最小化**：`allowed-tools` 仅声明实际需要的工具，不使用通配符

---

## 使用示例

### 示例 1：创建新 Skill

用户说：「帮我创建一个 NestJS 后端开发 skill」

执行步骤：
1. 阶段 1 — 联网搜索 NestJS 最新版本、最佳实践、已知 breaking changes
2. 阶段 2 — 判定为 Standard 级（完整技术栈），设计 SKILL.md + references/ 结构
3. 阶段 3 — 编写 frontmatter（name: `nestjs-backend`）+ body（核心模块、DTO、Guard 规范）
4. 阶段 4 — 编写深度参考文档（如 database、testing 等子主题）
5. 阶段 6 — 运行快速自检清单
6. 阶段 7 — 版本化提交 v1.0.0

输出：`nestjs-backend/` 目录，包含 SKILL.md + 2 个 reference 文件

### 示例 2：审计现有 Skill

用户说：「审查一下这个 skill 的质量」

执行步骤：
1. 读取目标 SKILL.md 及 references/ 目录
2. 按阶段 6 快速自检逐项检查
3. 如有 `scripts/validate-skill.sh`，运行自动化验证
4. 输出审计报告：PASS/FAIL 项 + 改进建议

---

## Troubleshooting

### Skill 不触发

**症状**：Skill 已安装但从不自动加载。

**排查**：
1. 检查 `description` 是否包含用户实际会说的触发短语
2. 确认 `description` 不超过 1024 字符
3. 测试方法：问 Claude "When would you use the [skill-name] skill?" — 如果 Claude 答不上来，说明 description 不够具体

### Skill 过度触发

**症状**：无关任务也加载了此 Skill。

**排查**：
1. `description` 中是否使用了过于宽泛的关键词（如 "代码"、"开发"）
2. 添加否定触发（如 "Do NOT use for general coding tasks"）
3. 收窄 Skill 边界，拆分为多个专精 Skill

### SKILL.md Body 超 500 行

**症状**：内容写着写着就超了。

**修复**：将以下内容下沉到 `references/`：完整 API 参考、大段代码示例、决策矩阵、安全指南。SKILL.md body 只保留 80% 场景需要的核心指令。

---

## 参考文档

深度指导请按需阅读：

- `references/skill-anatomy.md` — Skill 目录结构与每个文件的详细规范
- `references/quality-checklist.md` — 完整的 50+ 项质量审计清单
- `references/anti-patterns.md` — 21 条常见反模式与修复方案
