# OpenClaw Skills

> 高质量的 OpenClaw Agent Skills 精选集

## 简介

本仓库收录了部分适配openclaw的 Skill，会持续新增在真实场景下使用没问题的skill。

## 目录结构

```
openclaw-skills/
├── README.md
├── openclaw-assistant/        # OpenClaw 全能辅助
├── knowledge-harvester/       # 知识收割机
├── feishu-schema-designer/    # 飞书多维表格应用架构师
└── ...
```

## Skills 列表

### 1. openclaw-assistant

OpenClaw 全能辅助技能。

**功能：**
- 自我能力评估
- SKILL.md 生成
- 架构与配置咨询
- 安全审查

**安装：**
```bash
cp -r openclaw-assistant ~/.openclaw/skills/
```

### 2. knowledge-harvester

知识收割机 - 从多种来源自动采集和整理知识。

**功能：**
- 自动化知识采集
- 多源整合（网页、文档、GitHub）
- 结构化输出

**使用场景：**
- 研究行业趋势
- 竞品分析
- 技术调研

**安装：**
```bash
cp -r knowledge-harvester ~/.openclaw/skills/
```

### 3. skill-forge

生产级 Skill 创建元技能。

**功能：**
- 7 阶段创建流程
- 三层渐进式披露架构
- 复杂度分级 (Lite/Standard/Enterprise)
- 50+ 项质量审计点
- 21 条反模式检测

**安装：**
```bash
cp -r skill-forge ~/.openclaw/skills/
```

### 4. skill-auditor

Skill 审计工具 - 多维度质量保证检查。

**功能：**
- 7 个审计维度
- 自动化验证脚本
- 量化评分体系 (A+ ~ D)
- 回归检测

**安装：**
```bash
cp -r skill-auditor ~/.openclaw/skills/
```

### 5. feishu-schema-designer

飞书多维表格应用架构师工作流剧本 - 从原始资料/自然语言需求到真实可用的飞书 base 应用的端到端编排。

**功能：**
- 消化资料 → 推理设计 → 业务追问
- 程序化校验 + 业务效果预览
- 自动建表/字段/视图/工作流/仪表盘/表单/角色
- 输出云文档使用手册

**使用场景：**
- 把零散资料/需求落地为飞书 base 应用
- 搭建飞书 CRM / 项目管理 / 库存系统
- 飞书多维表格应用架构设计

> 设计与编排层，CRUD 执行委托给 lark-base / lark-doc 系列 skill。

**安装：**
```bash
cp -r feishu-schema-designer ~/.openclaw/skills/
```

## 快速开始

1. 克隆本仓库：
```bash
git clone https://github.com/Kingxiao/openclaw-skills.git
```

2. 安装需要的 Skill：
```bash
cp -r <skill-name> ~/.openclaw/skills/
```

3. 重启 OpenClaw Gateway：
```bash
openclaw gateway restart
```

## 关于 OpenClaw

OpenClaw 是一个开源的 AI Agent 框架。

- 官网：https://openclaw.ai
- GitHub：https://github.com/openclaw/openclaw
- 文档：https://docs.openclaw.ai

## 许可证

MIT License

## 联系方式

- GitHub Issues: https://github.com/Kingxiao/openclaw-skills/issues
