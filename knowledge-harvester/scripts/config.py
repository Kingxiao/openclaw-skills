"""
Knowledge Harvester — 统一路径与常量配置

所有脚本从此模块导入路径常量，避免多处重复定义。

路径优先级：
  1. 环境变量 OPENCLAW_DIR → 自定义安装位置
  2. 默认 ~/.openclaw
"""

from __future__ import annotations

import os
from datetime import timezone, timedelta
from pathlib import Path

# ── 时区 ──────────────────────────────────────────────────
SHANGHAI_TZ = timezone(timedelta(hours=8))

# ── 路径（支持 OPENCLAW_DIR 环境变量覆盖）────────────────
OPENCLAW_DIR = Path(os.environ.get("OPENCLAW_DIR", Path.home() / ".openclaw"))
SKILL_DIR = OPENCLAW_DIR / "extensions" / "ai-skills" / "knowledge-harvester"
KNOWLEDGE_DIR = OPENCLAW_DIR / "knowledge"
NOTES_DIR = KNOWLEDGE_DIR / "notes"
DRAFTS_DIR = KNOWLEDGE_DIR / "skill-drafts"
LOGS_DIR = KNOWLEDGE_DIR / "logs"

# ── 文件路径 ──────────────────────────────────────────────
SOURCES_YAML = SKILL_DIR / "sources.yaml"
TAXONOMY_FILE = SKILL_DIR / "taxonomy.yaml"
HARVEST_LOG = LOGS_DIR / "harvest.jsonl"
PENDING_ITEMS = LOGS_DIR / "pending_items.json"
CHECKPOINT_FILE = LOGS_DIR / "fetch_checkpoint.json"

# ── HTTP 配置 ─────────────────────────────────────────────
HTTP_TIMEOUT = 30
USER_AGENT = "OpenClaw-KnowledgeHarvester/2.2 (+https://github.com/openclaw)"
