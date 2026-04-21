#!/usr/bin/env python3
"""
Knowledge Harvester — Layer 1: 确定性采集（模块化 Adapter 架构）

架构：
  sources.yaml 的 `type` 字段 → adapters/ 目录下对应的 adapter 模块
  core 只负责: 读配置 → 路由到 adapter → 去重 → 断点续传 → 输出

新增采集方式 = adapters/ 下新建 .py 文件 + 在 sources.yaml 添加条目
零修改本文件

依赖: feedparser, pyyaml
安装: uv pip install feedparser pyyaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# 添加 scripts/ 到路径以支持 adapters 包导入
SCRIPTS_DIR = Path(__file__).parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import adapters

from config import (
    SHANGHAI_TZ, SOURCES_YAML, HARVEST_LOG, PENDING_ITEMS,
    CHECKPOINT_FILE, HTTP_TIMEOUT, USER_AGENT,
)

log = logging.getLogger("fetch_sources")


# ── 去重数据库 ─────────────────────────────────────────────
RETAIN_DAYS = 90  # 保留最近 N 天的去重记录


class DeduplicationDB:
    """基于 harvest.jsonl 的 URL 去重（支持日志轮转）。"""

    def __init__(self, logfile: Path):
        self.logfile = logfile
        self.seen_urls: set[str] = set()
        self._load()

    def _load(self):
        if not self.logfile.exists():
            return
        cutoff = (datetime.now(SHANGHAI_TZ) - timedelta(days=RETAIN_DAYS)).isoformat()
        for line in self.logfile.read_text(encoding="utf-8").splitlines():
            if not (line := line.strip()):
                continue
            try:
                entry = json.loads(line)
                url = entry.get("url", "")
                # 只加载 cutoff 之后的记录到内存去重集合
                ts = entry.get("ts", "")
                if url and ts >= cutoff:
                    self.seen_urls.add(self._norm(url))
            except json.JSONDecodeError:
                continue

    @staticmethod
    def _norm(url: str) -> str:
        url = url.strip().rstrip("/")
        if "://" in url:
            scheme_host, _, rest = url.partition("://")
            if "/" in rest:
                host, _, path = rest.partition("/")
                url = f"{scheme_host.lower()}://{host.lower()}/{path}"
            else:
                url = f"{scheme_host.lower()}://{rest.lower()}"
        return url

    def is_seen(self, url: str) -> bool:
        return self._norm(url) in self.seen_urls

    def mark_seen(self, url: str):
        self.seen_urls.add(self._norm(url))

    def record(self, entry: dict):
        self.logfile.parent.mkdir(parents=True, exist_ok=True)
        with self.logfile.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if entry.get("url"):
            self.mark_seen(entry["url"])

    def rotate(self):
        """归档超期记录：保留近 RETAIN_DAYS 天的行，超期行挪到 .archive。"""
        if not self.logfile.exists():
            return
        cutoff = (datetime.now(SHANGHAI_TZ) - timedelta(days=RETAIN_DAYS)).isoformat()
        keep, archive = [], []
        for line in self.logfile.read_text(encoding="utf-8").splitlines():
            if not (line := line.strip()):
                continue
            try:
                ts = json.loads(line).get("ts", "")
                (keep if ts >= cutoff else archive).append(line)
            except json.JSONDecodeError:
                keep.append(line)
        if archive:
            archive_path = self.logfile.with_suffix(".jsonl.archive")
            with archive_path.open("a", encoding="utf-8") as f:
                f.write("\n".join(archive) + "\n")
            self.logfile.write_text("\n".join(keep) + "\n", encoding="utf-8")
            log.info(f"  📦 日志轮转: 归档 {len(archive)} 条, 保留 {len(keep)} 条")


# ── 断点续传 ──────────────────────────────────────────────
class Checkpoint:
    """管理采集断点。网络中断后再次运行可从上次失败处继续。"""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.data: dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.filepath.exists():
            try:
                self.data = json.loads(self.filepath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {}

    def save(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @property
    def completed(self) -> set[str]:
        return set(self.data.get("completed_sources", []))

    @property
    def pending_items(self) -> list[dict]:
        return self.data.get("pending_items", [])

    @property
    def is_resuming(self) -> bool:
        return bool(self.data.get("completed_sources"))

    def mark_done(self, name: str, count: int):
        self.data.setdefault("completed_sources", [])
        if name not in self.data["completed_sources"]:
            self.data["completed_sources"].append(name)
        self.data.setdefault("source_stats", {})[name] = {
            "items": count, "ts": datetime.now(SHANGHAI_TZ).isoformat()
        }
        self.save()

    def mark_failed(self, name: str, error: str):
        self.data.setdefault("failures", {})[name] = {
            "error": error, "ts": datetime.now(SHANGHAI_TZ).isoformat()
        }
        self.save()

    def set_pending(self, items: list[dict]):
        self.data["pending_items"] = items
        self.save()

    def get_run_id(self) -> str:
        if "run_id" not in self.data:
            self.data["run_id"] = datetime.now(SHANGHAI_TZ).strftime("%Y%m%dT%H%M%S")
            self.save()
        return self.data["run_id"]

    def clear(self):
        if self.filepath.exists():
            self.filepath.unlink()
        self.data = {}


# ── 源配置加载 ────────────────────────────────────────────
def load_sources() -> dict[str, list[dict]]:
    """加载 sources.yaml，仅按 enabled 字段过滤。"""
    if not SOURCES_YAML.exists():
        log.error(f"sources.yaml 不存在: {SOURCES_YAML}")
        sys.exit(1)

    with SOURCES_YAML.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    result: dict[str, list[dict]] = {}
    for group in ("daily_sources", "weekly_sources"):
        sources = cfg.get(group, [])
        filtered = [
            s for s in sources
            if s.get("enabled", True) is not False
        ]
        if filtered:
            result[group] = filtered
    return result


# ── 主逻辑（纯编排，不含任何具体采集逻辑） ────────────────
def run(
    mode: str = "daily",
    dry_run: bool = False,
    resume: bool = True,
) -> dict[str, Any]:
    now = datetime.now(SHANGHAI_TZ)
    ckpt = Checkpoint(CHECKPOINT_FILE)

    # 断点恢复
    if resume and ckpt.is_resuming:
        run_id = ckpt.get_run_id()
        log.info(f"=== 从断点恢复 [run_id={run_id}] 已完成 {len(ckpt.completed)} 个源 ===")
    else:
        ckpt.clear()
        run_id = ckpt.get_run_id()
        log.info(f"=== 采集开始 [{mode}] run_id={run_id} @ {now.isoformat()} ===")

    # 加载 adapters
    adapters.auto_discover()
    registered = adapters.list_adapters()
    log.info(f"  可用 adapter: {list(registered.keys())}")

    # 加载源配置
    sources_cfg = load_sources()
    groups = []
    if mode in ("daily", "full"):
        groups.append("daily_sources")
    if mode in ("weekly", "full"):
        groups.append("weekly_sources")

    dedup = DeduplicationDB(HARVEST_LOG)
    dedup.rotate()  # 自动归档超期日志
    all_pending: list[dict] = list(ckpt.pending_items)  # 恢复断点数据
    stats = {
        "total_fetched": 0, "duplicates": 0,
        "pending": len(all_pending), "errors": 0,
        "skipped_checkpoint": len(ckpt.completed),
    }

    # ── 采集循环 ──
    client = adapters.HTTPConfig(timeout=HTTP_TIMEOUT, user_agent=USER_AGENT)
    for group in groups:
        for src in sources_cfg.get(group, []):
            name = src["name"]
            src_type = src.get("type", "rss")

            # 断点：跳过已完成
            if name in ckpt.completed:
                log.info(f"  ⏭ 跳过(已完成): {name}")
                continue

            # 查找 adapter
            adapter = adapters.get_adapter(src_type)
            if not adapter:
                log.warning(f"  ⚠️ 未知 adapter type: {src_type} (源: {name})")
                stats["errors"] += 1
                continue

            log.info(f"  ▸ 采集: {name} [adapter={src_type}]")

            try:
                items = adapter.fetch(src, client)
                stats["total_fetched"] += len(items)

                # 去重（仅内存去重，不写 harvest.jsonl —— 由 Layer 2 写入最终决定）
                new_items = []
                for item in items:
                    url = item.get("url", "")
                    if dedup.is_seen(url):
                        stats["duplicates"] += 1
                        continue
                    item["source_name"] = name
                    item["source_group"] = group.replace("_sources", "")
                    item["fetched_at"] = now.isoformat()
                    new_items.append(item)

                    if not dry_run:
                        dedup.mark_seen(url)

                all_pending.extend(new_items)
                stats["pending"] = len(all_pending)

                # 保存断点（dry-run 不写，避免幽灵断点）
                if not dry_run:
                    ckpt.mark_done(name, len(items))
                    ckpt.set_pending(all_pending)

                log.info(f"    → {len(items)} 条, {len(new_items)} 新")

            except Exception as e:
                stats["errors"] += 1
                ckpt.mark_failed(name, str(e))
                log.error(f"    ❌ 采集失败 [{name}]: {e}")

    # ── 输出 ──
    output = {
        "generated_at": now.isoformat(),
        "run_id": run_id,
        "mode": mode,
        "stats": stats,
        "items": all_pending,
    }

    if not dry_run:
        PENDING_ITEMS.parent.mkdir(parents=True, exist_ok=True)
        # 合并现有 pending_items.json（保留 REQUEUED 等条目，避免覆盖丢失）
        if PENDING_ITEMS.exists():
            try:
                with PENDING_ITEMS.open(encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing_items = existing_data.get("items", [])
                if existing_items:
                    # 以 URL 去重：新条目优先
                    new_urls = {item.get("url", "") for item in all_pending}
                    preserved = [
                        item for item in existing_items
                        if item.get("url", "") and item.get("url", "") not in new_urls
                    ]
                    if preserved:
                        all_pending.extend(preserved)
                        output["items"] = all_pending
                        output["stats"]["pending"] = len(all_pending)
                        output["stats"]["preserved_from_existing"] = len(preserved)
                        log.info(f"  📥 合并现有 {len(preserved)} 条 pending 条目")
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"  ⚠️ 读取现有 pending_items.json 失败，将覆盖: {e}")
        with PENDING_ITEMS.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        ckpt.clear()
        log.info(f"  📄 已写入 {PENDING_ITEMS}")
    else:
        log.info("  [DRY RUN] 未写入文件")

    # ── 报告 ──
    report = (
        f"\n📊 采集报告 [{mode}] {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"总拉取: {stats['total_fetched']} | 去重: {stats['duplicates']} | "
        f"待处理: {stats['pending']} | 错误: {stats['errors']}\n"
    )
    if dry_run:
        report += "⚠️  DRY RUN — 未写入文件\n"
    print(report)

    if dry_run:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return output


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Harvester Layer 1 — 模块化 Adapter 采集（支持断点续传）"
    )
    parser.add_argument("--mode", choices=["daily", "weekly", "full"], default="daily")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="禁用断点续传")
    parser.add_argument("--list-adapters", action="store_true", help="列出已注册的 adapter")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_adapters:
        adapters.auto_discover()
        registered = adapters.list_adapters()
        print(f"\n📋 已注册 adapter ({len(registered)}):\n")
        for name, a in sorted(registered.items()):
            print(f"  • {name:20s} → {a.__class__.__name__} ({a.__class__.__module__})")
        return

    run(mode=args.mode, dry_run=args.dry_run, resume=not args.no_resume)


if __name__ == "__main__":
    main()
