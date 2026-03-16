# Skill 解剖学 — 目录结构与文件规范详解

本文档详细拆解一个生产级 Skill 的每个组成部分，覆盖目录结构、文件命名、内容格式、字段语义等所有技术细节。

---

## 1. 目录结构规范

### 命名规则

- 目录名 = `name` 字段值（YAML frontmatter 中定义）
- 仅允许字符：`[a-z0-9-]`（小写字母、数字、连字符）
- 长度限制：≤ 64 字符
- 禁止保留词：anthropic, claude, openai, gemini, gpt, copilot
- 示例：`zig-enterpri先se`, `react-frontend`, `k8s-platform`, `python-fastapi`

### 完整结构（Enterprise 级）

```
<skill-name>/
├── SKILL.md                    # [必须] 主指令文件
│                                #   - YAML frontmatter（L1 元数据）
│                                #   - Markdown body（L2 核心指令）
│
├── references/                  # [Standard+] L3 深度参考文档
│   ├── <topic>.md              #   - 每文件聚焦单一子主题
│   ├── <another-topic>.md      #   - 文件名 kebab-case
│   └── ...                     #   - 无行数限制（按需加载）
│
├── scripts/                     # [Enterprise] 辅助脚本
│   ├── validate.sh             #   - 结构/质量验证
│   ├── scaffold.sh             #   - 代码脚手架生成
│   └── ...                     #   - 必须可执行，含 shebang
│
├── examples/                    # [可选] 参考实现
│   └── quickstart/             #   - 可运行的最小示例
│       ├── README.md
│       └── ...
│
└── assets/                      # [可选] 静态资源
    ├── templates/              #   - 模板文件
    └── diagrams/               #   - 架构图
```

### 渐进式披露层级映射

| 层级 | 文件 | 加载时机 | Token 预算 |
|------|------|----------|-----------|
| **L1** | SKILL.md YAML frontmatter | 始终加载 | ~50-150 tokens |
| **L2** | SKILL.md markdown body | skill 匹配时加载 | ~2000-4000 tokens |
| **L3** | references/*.md | 需要深入时按需加载 | 无上限 |
| **L3** | scripts/*.sh | 需要执行时加载 | 最小化 |

---

## 2. YAML Frontmatter 字段详解

### 必须字段

#### `name` (string)

```yaml
name: my-skill-name
```

- **语义**：Skill 的唯一标识符
- **约束**：
  - 必须与目录名完全一致
  - 仅 `[a-z0-9-]`
  - ≤ 64 字符
  - 不含保留词
- **用途**：Agent 用于索引和引用此 skill

#### `description` (string)

```yaml
description: >
  一段话描述这个 skill 的功能和触发条件。
  包含关键词列表帮助 Agent 判断相关性。
```

- **语义**：告诉 Agent "何时应该激活此 Skill"
- **约束**：
  - 非空
  - ≤ 1024 字符
  - 不含 XML 标签
- **最佳实践**：
  - 前半段写功能描述
  - 后半段写触发关键词（文件扩展名、命令名、技术名词）
  - 用 YAML 折叠风格 `>` 避免换行问题

### 推荐字段

#### `metadata` (object)

```yaml
metadata:
  version: "1.0.0"
  last_updated: "2026-03-05"
  language: "python"
  category: "backend"
  zig_version: "0.15.x"       # 领域特定字段
```

- `version` — 语义化版本号
- `last_updated` — 最后更新日期(YYYY-MM-DD)，用于判断时效性
- `language` — 主要编程语言（如适用）
- `category` — 分类标签
- 可添加领域特定字段

### 可选字段

#### `allowed-tools` (list)

```yaml
allowed-tools:
  - mcp::filesystem
  - mcp::shell
```

- **语义**：白名单机制，限定此 skill 可调用的 MCP 工具
- **用途**：安全隔离

#### `argument-hint` (string)

```yaml
argument-hint: "<project-path>"
```

- **语义**：如果存在，此 skill 可作为 slash command 调用 (e.g., `/skill-name <arg>`)
- **不存在时**：skill 仅通过上下文匹配自动激活

---

## 3. Markdown Body 编写规范

### 结构模板

```markdown
# <Skill 标题>

## 第一性原理 / 核心哲学
为什么这样做？一切规范的底层逻辑。
让 Agent 理解 "为什么" 而不仅仅是 "怎么做"。

## 当前状态 (<年月>)
基于调研的最新版本、生态、重大变更。
必须标明信息来源时间。

## 1. <核心主题 A>
### 子标题
规范描述 + 代码示例

## 2. <核心主题 B>
...

## N. Known Pitfalls
1. **<问题>** — <后果> → <修复方案>
2. ...

## 参考文档
- `references/<file>.md` — <一句话描述>
```

### 编写准则

1. **每个章节必须有可操作的输出**
   - ❌ "你应该注意性能" → ✅ "使用 `ArenaAllocator` 处理请求周期内存，避免逐个 free"

2. **代码示例必须标注语言和版本**
   - ❌ `code block without lang` → ✅ ````zig` (0.15+)

3. **表格优于段落**（用于对比、选择、分类）

4. **Known Pitfalls 是最高价值章节**
   - 每条必须含：问题描述 + 后果 + 修复方案
   - 至少 3 条
   - 排序：按严重程度降序

5. **引用 L3 文档的标准写法**
   ```markdown
   > 完整指南详见 `references/security.md`
   ```

---

## 4. 与 Anthropic Agent Skills 开放标准的对齐

本 Skill 体系完全兼容 Anthropic 2025 年发布的 Agent Skills 开放标准：

| 标准要求 | 本体系实现 |
|----------|-----------|
| 目录命名 kebab-case | ✅ 强制 `[a-z0-9-]` |
| SKILL.md 为入口 | ✅ 必须文件 |
| YAML frontmatter + markdown body | ✅ 双区结构 |
| name ≤ 64 char | ✅ 硬限制 |
| description ≤ 1024 char | ✅ 硬限制 |
| 渐进式披露 | ✅ L1/L2/L3 三层 |
| references/ 目录 | ✅ L3 实现方式 |
| scripts/ 目录 | ✅ Enterprise 支持 |
| 可组合性 | ✅ 每个 skill 独立、可与其他 skill 并存 |

### 与其他 Agent 平台的兼容性

本标准的 Skill 同时兼容：
- **Claude Code** `.claude/skills/` 目录
- **Gemini Antigravity** `skills/` 目录
- **Cursor** `.cursor/rules/` (需适配)
- **Forge** `prompts/skills/` 目录

目录结构和 SKILL.md 格式是跨平台的通用标准。
