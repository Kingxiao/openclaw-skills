"""
通用 Web Scrape 适配器

用于没有 RSS/API 但需要 HTML scraping 的源。
目前支持 Papers with Code trending。
可通过 config 中的 scrape_rules 扩展到其他站点。

sources.yaml 中 type: web_scrape
"""

from __future__ import annotations

import re
import logging
from typing import Any

from . import HTTPConfig, http_get, make_item, register

log = logging.getLogger("adapters.web_scrape")

MAX_ITEMS = 30

# ── 内置 scrape 规则 ──────────────────────────────────────
# 每个规则定义如何从特定站点提取内容
# 键: domain 或 name 关键词
BUILTIN_RULES: dict[str, dict] = {
    "paperswithcode.com": {
        "link_pattern": r'<a\s+href="(/papers/[^"]+)"[^>]*>\s*(.+?)\s*</a>',
        "link_group": 1,  # href 的 group index
        "title_group": 2,  # title 的 group index
        "base_url": "https://paperswithcode.com",
        "min_title_len": 10,
        "default_summary": "Papers with Code trending paper",
    },
}


class WebScrapeAdapter:
    """通用 HTML Scrape 适配器。"""

    adapter_type = "web_scrape"

    def fetch(self, config: dict[str, Any], client: HTTPConfig) -> list[dict[str, Any]]:
        url = config.get("url", "")
        if not url:
            return []

        resp = http_get(client, url)
        if not resp:
            return []

        # 查找匹配的内置规则
        rule = self._find_rule(url, config)
        if rule:
            return self._scrape_with_rule(resp.text, url, rule)

        # 无规则时的通用提取：提取所有 <a> 链接
        return self._generic_scrape(resp.text, url)

    def _find_rule(self, url: str, config: dict) -> dict | None:
        """根据 URL 或 config 查找 scrape 规则。"""
        # 优先使用 config 中的自定义规则
        if "scrape_rules" in config:
            return config["scrape_rules"]

        # 尝试匹配内置规则
        for domain, rule in BUILTIN_RULES.items():
            if domain in url:
                return rule

        return None

    def _scrape_with_rule(self, html: str, base_url: str, rule: dict) -> list[dict[str, Any]]:
        """用规则提取内容。"""
        items = []
        pattern = rule["link_pattern"]
        matches = re.findall(pattern, html)
        seen: set[str] = set()

        for match in matches:
            if isinstance(match, tuple):
                href = match[rule.get("link_group", 1) - 1]
                title_raw = match[rule.get("title_group", 2) - 1]
            else:
                href = match
                title_raw = ""

            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            min_len = rule.get("min_title_len", 5)
            if not title or len(title) < min_len:
                continue

            item_url = rule.get("base_url", base_url.rstrip("/")) + href
            if item_url in seen:
                continue
            seen.add(item_url)

            items.append(make_item(
                title=title,
                url=item_url,
                summary=rule.get("default_summary", ""),
                source_type="web",
            ))

            if len(items) >= MAX_ITEMS:
                break

        return items

    def _generic_scrape(self, html: str, base_url: str) -> list[dict[str, Any]]:
        """无规则时的通用链接提取。"""
        log.warning(f"  web_scrape: 无匹配规则，使用通用提取")
        # 提取标题
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        page_title = title_match.group(1).strip() if title_match else "Unknown"

        return [make_item(
            title=page_title,
            url=base_url,
            summary=f"Web page (需手动配置 scrape_rules)",
            source_type="web",
        )]


# 自注册
register(WebScrapeAdapter())
