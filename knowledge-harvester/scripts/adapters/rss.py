"""
RSS/Atom 通用适配器

处理所有通用 RSS 和 Atom feed。覆盖 sources.yaml 中 type: rss 的源。
这是最常用的 adapter——大多数信息源都走这条路径。
"""

from __future__ import annotations

import re
import logging
from typing import Any

import feedparser
import httpx

from . import SourceAdapter, http_get, make_item, register

log = logging.getLogger("adapters.rss")

MAX_ITEMS = 30


class RSSAdapter:
    """通用 RSS/Atom 适配器。"""

    adapter_type = "rss"

    def fetch(self, config: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
        url = config.get("url", "")
        if not url:
            log.warning(f"  RSS adapter: 未指定 URL")
            return []

        resp = http_get(client, url)
        if not resp:
            return []

        feed = feedparser.parse(resp.text)
        items = []

        for entry in feed.entries[:MAX_ITEMS]:
            link = entry.get("link", "")
            if not link:
                continue

            # 提取摘要
            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary
            elif hasattr(entry, "description"):
                summary = entry.description

            # 清理 HTML 标签
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            if len(summary) > 500:
                summary = summary[:500] + "..."

            items.append(make_item(
                title=entry.get("title", "Untitled"),
                url=link,
                summary=summary,
                published=entry.get("published", ""),
                source_type="rss",
            ))

        return items


# 自注册
register(RSSAdapter())
