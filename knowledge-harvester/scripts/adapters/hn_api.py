"""
Hacker News (Algolia API) 适配器

通过 HN Algolia search API 拉取高分文章。
sources.yaml 中 type: hn_api
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import HTTPConfig, http_get, make_item, register

log = logging.getLogger("adapters.hn_api")

MAX_ITEMS = 30


class HNApiAdapter:
    """Hacker News Algolia API 适配器。"""

    adapter_type = "hn_api"

    def fetch(self, config: dict[str, Any], client: HTTPConfig) -> list[dict[str, Any]]:
        min_points = config.get("min_points", 100)
        hours = config.get("lookback_hours", 24)
        ts_cutoff = int(time.time()) - hours * 3600

        # P-2026-06-27-03 06-27 复盘决策：provisional 修复
        # HN Algolia 服务端拒绝 numericFilters=points>=X 校验（HTTP 400，已持续 12+ 日）
        # 改为客户端过滤：拉取 hitsPerPage=MAX_ITEMS 后按 points 阈值过滤
        url = (
            f"https://hn.algolia.com/api/v1/search?"
            f"tags=story&numericFilters=created_at_i>={ts_cutoff}"
            f"&hitsPerPage={MAX_ITEMS}"
        )

        resp = http_get(client, url)
        if not resp:
            return []

        items = []
        try:
            data = resp.json()
            for hit in data.get("hits", []):
                # 客户端按 points 过滤（替代服务端 numericFilters）
                points = hit.get("points", 0)
                if points < min_points:
                    continue
                link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
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
