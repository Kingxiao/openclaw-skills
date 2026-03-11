# OpenClaw Skills

> 高质量的 OpenClaw Agent Skills 精选集

## 简介

本仓库收录了我创建和维护的高质量 OpenClaw Skills，涵盖 AI 咨询、自动化、知识管理等多个领域。

## 目录结构

```
openclaw-skills/
├── README.md
├── openclaw-assistant/    # OpenClaw 全能辅助
├── knowledge-harvester/    # 知识收割机
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
