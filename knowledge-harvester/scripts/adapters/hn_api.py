"""
Hacker News (Algolia API) 适配器

通过 HN Algolia search API 拉取高分文章。
sources.yaml 中 type: hn_api
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from . import SourceAdapter, http_get, make_item, register

log = logging.getLogger("adapters.hn_api")

MAX_ITEMS = 30


class HNApiAdapter:
    """Hacker News Algolia API 适配器。"""

    adapter_type = "hn_api"

    def fetch(self, config: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
        min_points = config.get("min_points", 100)
        hours = config.get("lookback_hours", 24)
        ts_cutoff = int(time.time()) - hours * 3600

        url = (
            f"https://hn.algolia.com/api/v1/search?"
            f"tags=story&numericFilters=points>={min_points},"
            f"created_at_i>={ts_cutoff}&hitsPerPage={MAX_ITEMS}"
        )

        resp = http_get(client, url)
        if not resp:
            return []

        items = []
        try:
            data = resp.json()
            for hit in data.get("hits", []):
                link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                points = hit.get("points", 0)
                comments = hit.get("num_comments", 0)

                items.append(make_item(
                    title=hit.get("title", "Untitled"),
                    url=link,
                    summary=f"HN {points} points, {comments} comments",
                    published=hit.get("created_at", ""),
                    source_type="api",
                    metadata={"points": points, "comments": comments},
                ))
        except Exception as e:
            log.warning(f"  HN API 解析失败: {e}")

        return items


# 自注册
register(HNApiAdapter())
