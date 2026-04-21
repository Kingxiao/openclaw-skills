"""
Knowledge Harvester — 统一路径与常量配置

所有脚本从此模块导入路径常量，避免多处重复定义。

路径优先级：
  1. 环境变量 OPENCLAW_DIR → 自定义安装位置
  2. 默认 ~/.openclaw
"""

from __future__ import annotations

import os
import sys
from datetime import timezone, timedelta
from pathlib import Path

# ── venv 自动发现 ────────────────────────────────────────
# 按优先级查找 venv 的 site-packages，注入 sys.path，
# 这样即使用系统 python3 运行也能找到 feedparser 等依赖。
def _inject_venv_packages():
    """自动发现项目 venv 并将其 site-packages 加入 sys.path。"""
    _script_dir = Path(__file__).resolve().parent
    _candidates = [
        _script_dir / ".venv",                          # scripts/.venv (首选)
        _script_dir.parent.parent.parent.parent / "knowledge" / ".venv",  # ~/.openclaw/knowledge/.venv
    ]
    for venv_dir in _candidates:
        if not venv_dir.is_dir():
            continue
        # 查找 lib/python*/site-packages
        lib_dir = venv_dir / "lib"
        if not lib_dir.is_dir():
            continue
        for pydir in sorted(lib_dir.iterdir(), reverse=True):
            sp = pydir / "site-packages"
            if sp.is_dir() and str(sp) not in sys.path:
                sys.path.insert(0, str(sp))
                return

_inject_venv_packages()

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
