# Skill Forge

生产级 Skill 创建元技能。用于创建、审计、修复、改进 AI Agent Skill，将领域知识编码为可复用的结构化指令集。

## 功能

- **7 阶段创建流程**：从需求分析到发布的完整流程
- **三层渐进式披露架构**：L1 (frontmatter) / L2 (body) / L3 (references)
- **复杂度分级**：Lite / Standard / Enterprise 三种等级
- **质量检查清单**：50+ 项质量审计点
- **反模式检测**：21 条常见错误模式

## 使用方法

### 创建新 Skill

```bash
# 使用验证脚本
bash scripts/validate-skill.sh /path/to/new-skill
```

### 目录结构

```
skill-forge/
├── SKILL.md              # 主技能文件 (L1 + L2)
├── references/           # L3 深度参考
│   ├── anti-patterns.md
│   ├── quality-checklist.md
│   └── skill-anatomy.md
└── scripts/
    └── validate-skill.sh
```

## 详细文档

- [SKILL.md](./SKILL.md) - 完整技能定义
- [references/](./references/) - 深度参考资料

## 要求

- 遵循 [Agent Skills Open Standard (2025)](https://docs.anthropic.com/en/docs/claude-code/agent-skills)
- 使用渐进式披露架构

## 版本

- **Version**: 1.2.0
- **Last Updated**: 2026-03-15
