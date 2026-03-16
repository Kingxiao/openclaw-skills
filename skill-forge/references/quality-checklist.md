# Skill 质量审计清单

本清单用于在 Skill 提交前进行全面质量审计。分为 5 大类、50+ 检查项。

> **使用方式**：逐项检查，标记 PASS/FAIL。任何 FAIL 必须在提交前修复。
> **最低标准**：标记为 `[CRITICAL]` 的项 100% 必须 PASS。

---

## A. 结构完整性 (Structure Integrity)

### A1. 文件系统结构

- [ ] `[CRITICAL]` SKILL.md 文件存在
- [ ] `[CRITICAL]` SKILL.md 以 `---` 开头的 YAML frontmatter 起始
- [ ] `[CRITICAL]` YAML frontmatter 以 `---` 正确闭合
- [ ] 目录名与 `name` 字段值完全一致
- [ ] 目录名仅含 `[a-z0-9-]` 字符
- [ ] SKILL.md 中引用的所有 `references/` 文件实际存在
- [ ] scripts/ 中脚本文件具有执行权限 (`chmod +x`)
- [ ] 无多余未引用的孤立文件

### A2. YAML Frontmatter

- [ ] `[CRITICAL]` `name` 字段存在且非空
- [ ] `[CRITICAL]` `name` 仅含 `[a-z0-9-]`，≤ 64 字符
- [ ] `[CRITICAL]` `description` 字段存在且非空
- [ ] `[CRITICAL]` `description` ≤ 1024 字符
- [ ] `description` 包含明确的触发条件/关键词列表
- [ ] `name` 不含保留词 (anthropic, claude, openai, gemini, gpt, copilot)
- [ ] `metadata.version` 遵循语义化版本 (x.y.z)
- [ ] `metadata.last_updated` 格式为 YYYY-MM-DD 且日期合理

---

## B. 内容质量 (Content Quality)

### B1. 信息时效性

- [ ] `[CRITICAL]` 核心技术信息基于联网调研，非纯训练数据
- [ ] 版本号、API 与当前最新稳定版一致
- [ ] 已废弃的 API/模式未被推荐
- [ ] `metadata.last_updated` 反映实际最后更新日期
- [ ] 如技术有重大版本迁移，已记录迁移注意事项

### B2. 准确性

- [ ] `[CRITICAL]` 代码示例使用正确语法（对应声明的语言版本）
- [ ] 代码示例可直接运行（非伪代码）
- [ ] 命令行示例在目标 OS 上有效
- [ ] 配置示例值合理（非 placeholder 就是可工作的默认值）
- [ ] 引用的外部工具/库名称拼写正确

### B3. 架构与深度

- [ ] `[CRITICAL]` 包含"第一性原理"或"核心哲学"章节
- [ ] 解释了 "为什么"——而非仅仅 "怎么做"
- [ ] 覆盖了该领域 80% 的核心场景
- [ ] 不同子主题间无矛盾建议
- [ ] 给出了明确的选择建议（何时用 A，何时用 B），而非罗列选项

### B4. Known Pitfalls

- [ ] `[CRITICAL]` Known Pitfalls / 已知陷阱章节存在
- [ ] ≥ 3 条已知陷阱
- [ ] 每条包含：问题 + 后果 + 修复方案
- [ ] 按严重程度排序（最严重在前）
- [ ] 陷阱基于真实场景（非臆想的边缘案例）

---

## C. Token 效率 (Token Efficiency)

### C1. 渐进式披露

- [ ] `[CRITICAL]` SKILL.md body ≤ 500 行
- [ ] L1 (frontmatter) 仅含 agent 判断相关性所需信息
- [ ] 深度内容已下沉到 references/ (L3)
- [ ] SKILL.md body 中用 `> 详见 references/xxx.md` 引用 L3
- [ ] 无整段重复出现在 SKILL.md 和 references/ 中

### C2. 信息密度

- [ ] 无冗余段落（同一信息不重复表述）
- [ ] 使用表格而非段落进行对比/分类
- [ ] 代码示例紧凑，含注释但无废话
- [ ] 列表项一行一条，不写段落式列表

---

## D. 安全性 (Security)

### D1. 敏感信息

- [ ] `[CRITICAL]` 无硬编码 API key / token / password / secret
- [ ] `[CRITICAL]` 无真实数据库连接字符串
- [ ] 示例中的密钥使用明确的占位符（如 `YOUR_API_KEY_HERE`）
- [ ] 无私有仓库 URL 或内部系统地址

### D2. 命令安全

- [ ] 无未加警告的破坏性命令 (`rm -rf`, `DROP TABLE`, `FORMAT`)
- [ ] 需要提权的命令标注了 `sudo` 或权限要求
- [ ] 脚本使用 `set -euo pipefail` 严格模式
- [ ] 外部下载命令验证了来源 (hash/signature)

### D3. 指令安全

- [ ] 不包含可能导致 Agent 执行任意代码的提示注入漏洞
- [ ] 不包含鼓励绕过安全措施的指令
- [ ] 不包含 "忽略之前所有指令" 类的内容

---

## E. 可组合性与可维护性 (Composability & Maintainability)

### E1. 独立性

- [ ] Skill 自包含 —— 不依赖其他 skill 才能工作
- [ ] 不与常见 skill 名冲突
- [ ] 可安全地与同仓库中的其他 skill 共存

### E2. 可维护性

- [ ] 有 `metadata.version` 用于版本追踪
- [ ] 有 `metadata.last_updated` 用于时效性判断
- [ ] 更新时的版本升级遵循语义化版本规则
- [ ] 文件结构清晰，新人可快速理解组织逻辑

---

## 审计结果模板

```
## Skill 审计报告: <skill-name>

审计日期: YYYY-MM-DD
审计人: <Agent/Human>

### 统计
- CRITICAL 项: X/Y PASS
- 总检查项: X/Y PASS
- 状态: ✅ PASS / ❌ FAIL

### FAIL 项清单
1. [<ID>] <描述> — <修复建议>
2. ...

### 改进建议（非阻塞）
1. ...
```
