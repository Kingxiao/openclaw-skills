#!/usr/bin/env python3
"""
Knowledge Harvester — 动态源发现 (Auto-Discovery)
给定 URL 或站点名，自动探测最佳采集方式并添加到 sources.yaml。

探测策略 (优先级从高到低):
  1. HTML <head> 中的 <link rel="alternate" type="application/rss+xml">
  2. 常见 RSS 路径探测 (/feed, /rss, /feed.xml, /atom.xml 等)
  3. RSSHub 查询 (rsshub.app，免费开源)
  4. 最终降级: 标记为 web 类型 (HTML scrape)

用法:
    python discover_source.py "https://arstechnica.com"
    python discover_source.py "https://example.com" --name "My Source" --frequency daily
    python discover_source.py --list-strategies
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests as httpx
import yaml

# 添加 scripts/ 到路径以支持 config 导入
SCRIPTS_DIR = Path(__file__).parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from config import SOURCES_YAML, SHANGHAI_TZ, HTTP_TIMEOUT, USER_AGENT

log = logging.getLogger("discover_source")


# ── 探测结果 ──────────────────────────────────────────────
class ProbeResult:
    """源探测结果。"""
    def __init__(
        self,
        url: str,
        feed_url: str | None = None,
        feed_type: str = "unknown",
        title: str = "",
        strategy: str = "",
        confidence: float = 0.0,
    ):
        self.url = url
        self.feed_url = feed_url
        self.feed_type = feed_type  # rss / atom / api / web
        self.title = title
        self.strategy = strategy
        self.confidence = confidence  # 0.0 ~ 1.0

    def __repr__(self):
        return (
            f"ProbeResult(feed={self.feed_url}, type={self.feed_type}, "
            f"strategy={self.strategy}, confidence={self.confidence:.1%})"
        )

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "feed_url": self.feed_url,
            "feed_type": self.feed_type,
            "title": self.title,
            "strategy": self.strategy,
            "confidence": self.confidence,
        }


# ── 策略 1: HTML <link> 探测 ──────────────────────────────
def probe_html_link(url: str, client: httpx.Client) -> list[ProbeResult]:
    """解析 HTML <head> 中的 RSS/Atom 链接。"""
    results = []
    try:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()

        # 提取页面标题
        title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
        page_title = title_match.group(1).strip() if title_match else ""

        # 查找 RSS/Atom link 标签
        link_patterns = [
            (r'<link[^>]*type=["\']application/rss\+xml["\'][^>]*href=["\']([^"\']+)["\']', "rss"),
            (r'<link[^>]*href=["\']([^"\']+)["\'][^>]*type=["\']application/rss\+xml["\']', "rss"),
            (r'<link[^>]*type=["\']application/atom\+xml["\'][^>]*href=["\']([^"\']+)["\']', "atom"),
            (r'<link[^>]*href=["\']([^"\']+)["\'][^>]*type=["\']application/atom\+xml["\']', "atom"),
        ]

        for pattern, feed_type in link_patterns:
            matches = re.findall(pattern, resp.text, re.IGNORECASE)
            for match in matches:
                feed_url = urljoin(url, match)
                results.append(ProbeResult(
                    url=url,
                    feed_url=feed_url,
                    feed_type=feed_type,
                    title=page_title,
                    strategy="html_link",
                    confidence=0.95,
                ))

    except Exception as e:
        log.debug(f"  HTML link 探测失败 [{url}]: {e}")

    return results


# ── 策略 2: 常见路径探测 ──────────────────────────────────
COMMON_FEED_PATHS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss/",
    "/feed.xml",
    "/atom.xml",
    "/rss.xml",
    "/index.xml",
    "/feeds/posts/default",  # Blogger
    "/blog/feed",
    "/blog/rss",
    "/?feed=rss2",  # WordPress
    "/wp-json/wp/v2/posts",  # WordPress REST API
]


def probe_common_paths(url: str, client: httpx.Client) -> list[ProbeResult]:
    """尝试常见 RSS 路径。"""
    results = []
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in COMMON_FEED_PATHS:
        feed_url = base + path
        try:
            resp = client.get(feed_url, follow_redirects=True)
            if resp.status_code != 200:
                continue

            content_type = resp.headers.get("content-type", "").lower()
            text = resp.text[:500]

            is_feed = False
            feed_type = "rss"

            # 检查 Content-Type
            if "xml" in content_type or "rss" in content_type or "atom" in content_type:
                is_feed = True
            # 检查内容头部
            elif "<rss" in text or "<feed" in text or "<channel>" in text:
                is_feed = True
            elif "atom" in text.lower():
                is_feed = True
                feed_type = "atom"

            # WordPress REST API
            if "wp/v2" in path and "application/json" in content_type:
                is_feed = True
                feed_type = "api"

            if is_feed:
                # 尝试提取 feed 标题
                title = ""
                title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text[:2000])
                if title_match:
                    title = re.sub(r'<!\[CDATA\[|\]\]>', '', title_match.group(1)).strip()

                results.append(ProbeResult(
                    url=url,
                    feed_url=feed_url,
                    feed_type=feed_type,
                    title=title,
                    strategy="common_path",
                    confidence=0.85,
                ))

        except Exception:
            continue

    return results


# ── 策略 3: RSSHub 查询 ──────────────────────────────────
RSSHUB_INSTANCE = "https://rsshub.app"

# 常见域名到 RSSHub 路由的映射
RSSHUB_ROUTES: dict[str, list[str]] = {
    "twitter.com": ["/twitter/user/{path}"],
    "x.com": ["/twitter/user/{path}"],
    "github.com": ["/github/repos/{path}"],
    "youtube.com": ["/youtube/channel/{path}"],
    "bilibili.com": ["/bilibili/user/video/{path}"],
    "zhihu.com": ["/zhihu/hot"],
    "weibo.com": ["/weibo/user/{path}"],
    "36kr.com": ["/36kr/hot-list"],
    "sspai.com": ["/sspai/matrix"],
    "v2ex.com": ["/v2ex/topics/hot"],
    "producthunt.com": ["/producthunt/today"],
    "telegram.org": ["/telegram/channel/{path}"],
    "instagram.com": ["/instagram/user/{path}"],
    "medium.com": ["/medium/user/{path}"],
}


def probe_rsshub(url: str, client: httpx.Client) -> list[ProbeResult]:
    """查询 RSSHub 是否有该站点的路由。"""
    results = []
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.strip("/")

    routes = RSSHUB_ROUTES.get(domain, [])
    if not routes:
        # 尝试去掉子域名
        parts = domain.split(".")
        if len(parts) > 2:
            base_domain = ".".join(parts[-2:])
            routes = RSSHUB_ROUTES.get(base_domain, [])

    for route_template in routes:
        route = route_template.replace("{path}", path) if path else route_template
        rsshub_url = f"{RSSHUB_INSTANCE}{route}"

        try:
            resp = client.get(rsshub_url, follow_redirects=True)
            if resp.status_code == 200:
                content = resp.text[:500]
                if "<rss" in content or "<feed" in content or "<channel>" in content:
                    results.append(ProbeResult(
                        url=url,
                        feed_url=rsshub_url,
                        feed_type="rss",
                        title=f"RSSHub: {domain}",
                        strategy="rsshub",
                        confidence=0.80,
                    ))
        except Exception:
            continue

    return results


# ── 策略 4: Web Scrape 降级 ──────────────────────────────
def probe_web_fallback(url: str, client: httpx.Client) -> ProbeResult:
    """最终降级方案：标记为需要 HTML scrape。"""
    # 获取页面标题
    title = ""
    try:
        resp = client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
    except Exception:
        pass

    return ProbeResult(
        url=url,
        feed_url=None,
        feed_type="web",
        title=title or urlparse(url).netloc,
        strategy="web_scrape_fallback",
        confidence=0.30,
    )


# ── 主探测逻辑 ────────────────────────────────────────────
def discover(
    url: str,
    client: httpx.Client | None = None,
) -> list[ProbeResult]:
    """执行全套探测策略，返回所有发现的结果（按 confidence 降序）。"""
    own_client = client is None
    if own_client:
        client = httpx.Client(
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )

    all_results: list[ProbeResult] = []

    try:
        # 策略 1: HTML link
        log.info(f"  [1/4] HTML <link> 探测...")
        results = probe_html_link(url, client)
        all_results.extend(results)
        if results:
            log.info(f"    → 发现 {len(results)} 个 feed link")

        # 策略 2: 常见路径
        log.info(f"  [2/4] 常见路径探测...")
        results = probe_common_paths(url, client)
        all_results.extend(results)
        if results:
            log.info(f"    → 发现 {len(results)} 个常见路径 feed")

        # 策略 3: RSSHub
        log.info(f"  [3/4] RSSHub 路由查询...")
        results = probe_rsshub(url, client)
        all_results.extend(results)
        if results:
            log.info(f"    → 发现 {len(results)} 个 RSSHub 路由")

        # 策略 4: 降级
        if not all_results:
            log.info(f"  [4/4] 降级为 web scrape...")
            all_results.append(probe_web_fallback(url, client))

        # 去重（按 feed_url）
        seen: set[str] = set()
        unique: list[ProbeResult] = []
        for r in all_results:
            key = r.feed_url or r.url
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # 按 confidence 降序排列
        unique.sort(key=lambda r: r.confidence, reverse=True)
        return unique

    finally:
        if own_client:
            client.close()


# ── sources.yaml 操作 ────────────────────────────────────
def add_to_sources(
    probe: ProbeResult,
    name: str | None = None,
    frequency: str = "daily",
    categories: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """将探测结果写入 sources.yaml。"""
    now = datetime.now(SHANGHAI_TZ)

    source_entry = {
        "name": name or probe.title or urlparse(probe.url).netloc,
        "url": probe.feed_url or probe.url,
        "type": probe.feed_type if probe.feed_type != "atom" else "rss",
        "categories": categories or ["custom"],
        "priority": 2,
        "auto_discovered": True,
        "discovered_at": now.isoformat(),
        "discovery_strategy": probe.strategy,
    }

    if probe.feed_type == "web":
        source_entry["note"] = "需 HTML scrape，建议手动确认采集方式"

    if dry_run:
        log.info(f"  [DRY RUN] 将添加到 {frequency}_sources:")
        print(yaml.dump([source_entry], allow_unicode=True, default_flow_style=False))
        return source_entry

    # 读取现有配置（仅用于重名检查）
    if SOURCES_YAML.exists():
        with SOURCES_YAML.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # 添加到对应的源组
    group_key = f"{frequency}_sources"
    sources = cfg.get(group_key, [])

    # 检查重名
    existing_names = {s.get("name") for s in sources}
    if source_entry["name"] in existing_names:
        log.warning(f"  ⚠️ 源 '{source_entry['name']}' 已存在，跳过添加")
        return source_entry

    # 追加到文件末尾（保留手写注释和格式）
    entry_yaml = yaml.dump(
        [source_entry], allow_unicode=True,
        default_flow_style=False, sort_keys=False,
    )
    # 格式化为缩进的列表项
    lines = entry_yaml.strip().split("\n")
    formatted = "\n".join(f"  {line}" if i > 0 else f"  {line}" for i, line in enumerate(lines))

    with SOURCES_YAML.open("a", encoding="utf-8") as f:
        f.write(f"\n  # ── auto-discovered ({now.strftime('%Y-%m-%d')}) ──\n")
        f.write(formatted + "\n")

    log.info(f"  ✅ 已追加到 {SOURCES_YAML}: {source_entry['name']}")
    return source_entry


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Harvester — 动态源发现与添加"
    )
    parser.add_argument("url", nargs="?", help="要探测的 URL")
    parser.add_argument("--name", help="源名称（默认从页面标题提取）")
    parser.add_argument(
        "--frequency", choices=["daily", "weekly"], default="daily",
        help="采集频率 (default: daily)"
    )
    parser.add_argument(
        "--categories", help="分类标签，逗号分隔 (如: ai,tools,frameworks)"
    )
    parser.add_argument(
        "--add", action="store_true",
        help="探测后自动添加到 sources.yaml（默认仅展示结果）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅展示将要添加的内容"
    )
    parser.add_argument(
        "--list-strategies", action="store_true",
        help="列出所有可用的探测策略"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="详细日志"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_strategies:
        print("📋 可用的探测策略:\n")
        print("  1. html_link      — 解析 HTML <head> 中的 RSS/Atom <link> 标签 (confidence: 95%)")
        print("  2. common_path    — 尝试 /feed, /rss, /feed.xml 等常见路径 (confidence: 85%)")
        print("  3. rsshub         — 查询 RSSHub 开源服务是否有该站路由 (confidence: 80%)")
        print("  4. web_fallback   — 降级为 HTML scrape (confidence: 30%)")
        print()
        print("支持的 RSSHub 域名:")
        for domain in sorted(RSSHUB_ROUTES.keys()):
            routes = RSSHUB_ROUTES[domain]
            print(f"  • {domain}: {', '.join(routes)}")
        return

    if not args.url:
        parser.error("请提供要探测的 URL")

    url = args.url
    if not url.startswith("http"):
        url = f"https://{url}"

    print(f"\n🔍 探测: {url}\n")
    results = discover(url)

    if not results:
        print("  ❌ 未找到任何 feed")
        sys.exit(1)

    print(f"\n📡 发现 {len(results)} 个可用方式:\n")
    for i, r in enumerate(results, 1):
        status = "🟢" if r.confidence >= 0.8 else "🟡" if r.confidence >= 0.5 else "🔴"
        print(f"  {status} [{i}] {r.strategy} (confidence: {r.confidence:.0%})")
        print(f"      URL: {r.feed_url or r.url}")
        print(f"      Type: {r.feed_type}")
        if r.title:
            print(f"      Title: {r.title}")
        print()

    # 使用最佳结果
    best = results[0]

    if args.add or args.dry_run:
        categories = args.categories.split(",") if args.categories else None
        add_to_sources(
            probe=best,
            name=args.name,
            frequency=args.frequency,
            categories=categories,
            dry_run=args.dry_run,
        )
    else:
        print("💡 使用 --add 将最佳结果添加到 sources.yaml")
        print(f"   例: python discover_source.py \"{url}\" --add --frequency daily")


if __name__ == "__main__":
    main()
