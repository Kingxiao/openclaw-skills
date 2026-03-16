# Skill Auditor

全面的 AI Agent Skills 审计工具。对技能进行多维度质量保证检查，确保 Skill 符合生产级质量标准。

## 功能

- **7 个审计维度**：格式、安全、质量、能力、回归、断言、Rubric 评分
- **自动化验证脚本**：一键生成审计报告
- **量化评分体系**：6 维加权评分，满分 100 分
- **回归检测**：版本对比，检测破坏性变更

## 使用方法

```bash
# 审计单个技能
python scripts/audit_skill.py /path/to/skill-name

# 生成 Markdown 报告
python scripts/audit_skill.py /path/to/skill-name --format markdown --output report.md

# 仅运行安全检查
python scripts/audit_skill.py /path/to/skill-name --check security

# 对比两个版本（回归检测）
python scripts/audit_skill.py /path/to/skill-v2 --baseline /path/to/skill-v1
```

## 目录结构

```
skill-auditor/
├── SKILL.md              # 主技能文件
├── references/           # 审计标准和评分规则
│   ├── audit_rubrics.md
│   ├── quality_criteria.md
│   └── security_patterns.md
└── scripts/
    ├── audit_skill.py    # 主审计脚本
    ├── evaluators/       # 各维度评估器
    ├── validators/       # 验证器
    └── scorers/         # 评分器
```

## 审计维度

| 维度 | 说明 |
|------|------|
| 格式验证 | SKILL.md 结构、frontmatter 规范 |
| 安全检查 | 密钥泄露、提示注入、危险代码 |
| 质量评估 | 可读性、清晰性、完整性 |
| 能力分析 | 触发词覆盖、功能范围 |
| 回归检测 | 版本对比、破坏性变更 |
| 断言验证 | 自然语言规则验证 |
| Rubric 评分 | 量化加权评分体系 |

## 评分等级

| 等级 | 分数 | 说明 |
|------|------|------|
| A+ | 90-100 | 优秀，可直接使用 |
| A | 80-89 | 良好，轻微改进建议 |
| B | 70-79 | 中等，需要改进 |
| C | 60-69 | 及格，重大问题需修复 |
| D | <60 | 不合格，不建议使用 |

## 详细文档

- [SKILL.md](./SKILL.md) - 完整技能定义
- [references/](./references/) - 审计标准和评分规则
- [scripts/audit_skill.py](./scripts/audit_skill.py) - 审计脚本源码

## 版本

- **Version**: 1.1.1
- **Last Updated**: 2026-03-15
