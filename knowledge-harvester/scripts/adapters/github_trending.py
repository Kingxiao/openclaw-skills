"""
GitHub Trending 适配器

主路径：mshibanami RSS（每日自动构建）
降级后备：直接 scrape github.com/trending

sources.yaml 中 type: github_trending
配置项:
  languages: [python, rust, go, zig, typescript]  # 要抓取的语言
"""

from __future__ import annotations

import re
import logging
from typing import Any

import feedparser
import httpx

from . import SourceAdapter, http_get, make_item, register

log = logging.getLogger("adapters.github_trending")

MAX_ITEMS = 30
# mshibanami RSS 正确格式: {base}/daily/{lang}.xml
RSS_BASE = "https://mshibanami.github.io/GitHubTrendingRSS"


class GitHubTrendingAdapter:
    """GitHub Trending 适配器（RSS 主路径 + scrape 降级）。"""

    adapter_type = "github_trending"

    def fetch(self, config: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
        languages = config.get("languages", ["python", "rust", "go", "zig", "typescript"])

        # 主路径: RSS
        log.info(f"    尝试 RSS (mshibanami)...")
        items = self._fetch_rss(client, languages)
        if items:
            return items

        # 降级: 直接 scrape
        log.warning(f"    RSS 失败，降级到 scrape github.com/trending")
        return self._fetch_scrape(client, languages)

    def _fetch_rss(self, client: httpx.Client, languages: list[str]) -> list[dict[str, Any]]:
        """通过 mshibanami 第三方 RSS 拉取。"""
        items = []
        seen: set[str] = set()

        for lang in languages:
            feed_url = f"{RSS_BASE}/daily/{lang}.xml"
            resp = http_get(client, feed_url, max_retries=2, retry_delay=3)
            if not resp:
                log.debug(f"      RSS [{lang}] 不可用")
                continue

            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:10]:
                link = entry.get("link", "")
                if not link or link in seen:
                    continue
                seen.add(link)

                summary = ""
                if hasattr(entry, "summary"):
                    summary = re.sub(r"<[^>]+>", "", entry.summary).strip()

                items.append(make_item(
                    title=entry.get("title", "Unknown repo"),
                    url=link,
                    summary=summary or f"GitHub trending {lang}",
                    published=entry.get("published", ""),
                    source_type="rss",
                    metadata={"language": lang},
                ))

        return items[:MAX_ITEMS]

    def _fetch_scrape(self, client: httpx.Client, languages: list[str]) -> list[dict[str, Any]]:
        """直接 scrape github.com/trending（降级方案）。"""
        items = []
        seen: set[str] = set()

        for lang in languages:
            url = f"https://github.com/trending/{lang}?since=daily"
            resp = http_get(client, url, max_retries=2)
            if not resp:
                continue

            repo_links = re.findall(
                r'<h2[^>]*>\s*<a[^>]*href="(/[^"]+)"', resp.text
            )
            descriptions = re.findall(
                r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                resp.text, re.DOTALL,
            )

            for i, repo_path in enumerate(repo_links):
                repo_url = f"https://github.com{repo_path.strip()}"
                if repo_url in seen:
                    continue
                seen.add(repo_url)

                desc = ""
                if i < len(descriptions):
                    desc = re.sub(r'<[^>]+>', '', descriptions[i]).strip()

                items.append(make_item(
                    title=repo_path.strip().lstrip("/"),
                    url=repo_url,
                    summary=desc or f"GitHub trending {lang}",
                    source_type="web",
                    metadata={"language": lang},
                ))

        return items[:MAX_ITEMS]


# 自注册
register(GitHubTrendingAdapter())
