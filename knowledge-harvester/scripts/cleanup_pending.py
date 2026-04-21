#!/usr/bin/env python3
"""清理 harvest.jsonl 中的历史 PENDING 记录。

策略：
  - >24h 的 PENDING → 标记为 LEGACY_PENDING（过时，不再处理）
  - ≤24h 的 PENDING → 重新放回 pending_items.json 让 Layer 2 重新处理
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from config import SHANGHAI_TZ, LOGS_DIR, HARVEST_LOG, PENDING_ITEMS

NOW = datetime.now(SHANGHAI_TZ)
CUTOFF = NOW - timedelta(hours=24)


def parse_ts(ts_str: str) -> datetime | None:
    """解析时间戳字符串。"""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


def main():
    if not HARVEST_LOG.exists():
        print("❌ harvest.jsonl 不存在")
        return

    # 备份原文件
    backup = HARVEST_LOG.with_suffix(".jsonl.bak")
    shutil.copy2(HARVEST_LOG, backup)
    print(f"📦 已备份到 {backup}")

    # 读取所有记录
    records: list[dict] = []
    with HARVEST_LOG.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # 分类处理
    requeue_items: list[dict] = []
    legacy_count = 0
    kept_pending = 0
    updated_records: list[dict] = []

    for rec in records:
        if rec.get("decision") != "PENDING":
            updated_records.append(rec)
            continue

        ts = parse_ts(rec.get("ts", ""))
        if ts is None or ts < CUTOFF:
            # >24h 或无时间戳 → 标记为 LEGACY_PENDING
            rec["decision"] = "LEGACY_PENDING"
            rec["cleanup_note"] = f"marked legacy at {NOW.isoformat()}"
            updated_records.append(rec)
            legacy_count += 1
        else:
            # ≤24h → 重新入队，从日志中移除 PENDING 状态
            requeue_items.append({
                "source": rec.get("source", ""),
                "url": rec.get("url", ""),
                "title": rec.get("title", ""),
                "fetched_at": rec.get("ts", ""),
            })
            # 保留记录但标记为 REQUEUED
            rec["decision"] = "REQUEUED"
            rec["cleanup_note"] = f"requeued at {NOW.isoformat()}"
            updated_records.append(rec)
            kept_pending += 1

    # 写回 harvest.jsonl
    with HARVEST_LOG.open("w", encoding="utf-8") as f:
        for rec in updated_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 重新写入 pending_items.json（合并现有 items）
    if requeue_items:
        pending_data = {}
        if PENDING_ITEMS.exists():
            with PENDING_ITEMS.open(encoding="utf-8") as f:
                pending_data = json.load(f)

        existing_items = pending_data.get("items", [])
        # 去重：按 url
        existing_urls = {item.get("url") for item in existing_items}
        new_items = [item for item in requeue_items if item["url"] not in existing_urls]

        pending_data["items"] = existing_items + new_items
        pending_data["stats"] = pending_data.get("stats", {})
        pending_data["stats"]["pending"] = len(pending_data["items"])
        pending_data["stats"]["requeued_from_cleanup"] = len(new_items)
        pending_data["cleanup_at"] = NOW.isoformat()

        with PENDING_ITEMS.open("w", encoding="utf-8") as f:
            json.dump(pending_data, f, ensure_ascii=False, indent=2)

        print(f"📥 重新入队 {len(new_items)} 条到 pending_items.json")

    # 汇总
    print(f"\n{'='*50}")
    print(f"清理完成!")
    print(f"  LEGACY_PENDING (>24h): {legacy_count}")
    print(f"  REQUEUED (≤24h):       {kept_pending}")
    print(f"  总记录数:              {len(updated_records)}")
    print(f"{'='*50}")

    # 验证
    print("\n🔍 验证清理结果...")
    from collections import Counter
    decisions = Counter()
    with HARVEST_LOG.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                decisions[rec.get("decision", "UNKNOWN")] += 1

    print("  决策分布:")
    for d, c in decisions.most_common():
        print(f"    {d}: {c}")

    remaining_pending = decisions.get("PENDING", 0)
    if remaining_pending == 0:
        print("\n✅ 没有残留 PENDING 记录")
    else:
        print(f"\n⚠️  仍有 {remaining_pending} 条 PENDING 记录")


if __name__ == "__main__":
    main()
