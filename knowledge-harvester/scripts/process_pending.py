#!/usr/bin/env python3
"""
Knowledge Harvester — 处理历史 PENDING 条目

将 harvest.jsonl 中的 PENDING 条目提取到待处理列表，
解决历史条目未被筛选的问题。

用法：
    python process_pending.py --limit 50    # 处理最近50条
    python process_pending.py --all          # 处理所有 PENDING
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import HARVEST_LOG, PENDING_ITEMS, SHANGHAI_TZ

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("process_pending")


def load_pending_from_history(limit: int | None = None) -> list[dict]:
    """从 harvest.jsonl 加载 PENDING 条目"""
    if not HARVEST_LOG.exists():
        log.warning(f"  日志文件不存在: {HARVEST_LOG}")
        return []

    pending = []
    cutoff = (datetime.now(SHANGHAI_TZ) - timedelta(days=7)).isoformat()
    
    with open(HARVEST_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # 只取 PENDING 条目
                if entry.get("decision") == "PENDING":
                    # 可选：只取最近7天的
                    ts = entry.get("ts", "")
                    if ts and ts >= cutoff:
                        pending.append(entry)
            except json.JSONDecodeError:
                continue
    
    log.info(f"  找到 {len(pending)} 条 PENDING 条目 (最近7天)")
    
    if limit:
        pending = pending[:limit]
    
    return pending


def main():
    parser = argparse.ArgumentParser(description="处理历史 PENDING 条目")
    parser.add_argument("--limit", type=int, default=50, help="处理数量限制")
    parser.add_argument("--all", action="store_true", help="处理所有 PENDING")
    args = parser.parse_args()

    limit = None if args.all else args.limit
    
    log.info("=== 处理历史 PENDING 条目 ===")
    items = load_pending_from_history(limit)
    
    if not items:
        log.info("  没有待处理的 PENDING 条目")
        return
    
    # 输出到 pending_items.json
    output = {
        "generated_at": datetime.now(SHANGHAI_TZ).isoformat(),
        "run_id": f"PROCESS_PENDING_{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        "mode": "process_pending",
        "stats": {
            "total": len(items),
            "source": "harvest.jsonl history"
        },
        "items": items
    }
    
    PENDING_ITEMS.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_ITEMS, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    log.info(f"  已写入 {len(items)} 条到 {PENDING_ITEMS}")
    log.info("  下一步: 请对这些条目执行快筛 (Step 2)")


if __name__ == "__main__":
    main()
