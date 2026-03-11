"""
Ghost Content API 适配器

用于基于 Ghost CMS 的博客（RSS 已废弃或不可用时）。
通过 Ghost 公开 Content API 拉取最新文章。

sources.yaml 中 type: ghost_api
必须配置:
  url:           站点根地址 (如 https://review.firstround.com)
  ghost_api_key: Ghost Content API key (从页面 JS 中提取)
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from . import SourceAdapter, make_item, register

log = logging.getLogger("adapters.ghost_api")

MAX_ITEMS = 20


class GhostApiAdapter:
    """Ghost Content API 适配器。"""

    adapter_type = "ghost_api"

    def fetch(self, config: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
        import os

        base_url = config.get("url", "").rstrip("/")

        # 优先从环境变量读取 API key（与 fred_api 的 api_key_env 模式统一）
        api_key_env = config.get("ghost_api_key_env", "")
        api_key = os.environ.get(api_key_env, "") if api_key_env else ""
        if not api_key:
            api_key = config.get("ghost_api_key", "")

        if not base_url or not api_key:
            log.warning("  ghost_api: 缺少 url 或 ghost_api_key/ghost_api_key_env")
            return []

        api_url = (
            f"{base_url}/ghost/api/content/posts/"
            f"?key={api_key}"
            f"&limit={MAX_ITEMS}"
            f"&fields=title,url,slug,published_at,custom_excerpt,feature_image"
        )

        try:
            resp = client.get(api_url, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.error(f"  ghost_api: 请求失败 → {e}")
            return []

        try:
            data = resp.json()
        except Exception:
            log.error("  ghost_api: 响应不是有效 JSON")
            return []

        posts = data.get("posts", [])
        items = []

        for post in posts:
            title = post.get("title", "")
            url = post.get("url", "")
            if not title or not url:
                continue

            excerpt = post.get("custom_excerpt", "") or ""
            published = post.get("published_at", "")

            items.append(make_item(
                title=title,
                url=url,
                summary=excerpt[:500],
                published=published,
                source_type="ghost_api",
            ))

        return items


# 自注册
register(GhostApiAdapter())
