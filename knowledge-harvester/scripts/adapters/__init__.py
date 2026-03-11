"""
Knowledge Harvester — Adapter 注册表与协议定义

每个 adapter 是一个独立模块，实现 SourceAdapter 协议。
core (fetch_sources.py) 通过 sources.yaml 的 `type` 字段路由到对应 adapter。

新增采集方式 = 新建 adapter 文件 + yaml 条目，零修改核心代码。
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

log = logging.getLogger("adapters")


# ── Adapter 协议 ──────────────────────────────────────────
@runtime_checkable
class SourceAdapter(Protocol):
    """源适配器协议。所有 adapter 必须实现此接口。"""

    # adapter 处理的 type 名称（匹配 sources.yaml 中的 type 字段）
    adapter_type: str

    def fetch(self, config: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
        """
        从源拉取条目。

        Args:
            config: sources.yaml 中该源的完整配置字典
            client: 共享的 httpx.Client（已配置 timeout 和 UA）

        Returns:
            标准化条目列表，每条必须包含:
            - title: str
            - url: str
            - summary: str
            - published: str (可空)
            - source_type: str (rss/api/web)
            可选:
            - metadata: dict (源特有的额外信息)
        """
        ...


# ── 标准条目构建 ──────────────────────────────────────────
def make_item(
    title: str,
    url: str,
    summary: str = "",
    published: str = "",
    source_type: str = "rss",
    metadata: dict | None = None,
) -> dict[str, Any]:
    """构建标准化的采集条目。所有 adapter 应使用此函数。"""
    item: dict[str, Any] = {
        "title": title,
        "url": url,
        "summary": summary,
        "published": published,
        "source_type": source_type,
    }
    if metadata:
        item["metadata"] = metadata
    return item


# ── HTTP 工具 ─────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def http_get(
    client: httpx.Client,
    url: str,
    max_retries: int = MAX_RETRIES,
    retry_delay: float = RETRY_DELAY,
    dry_run: bool = False,
) -> httpx.Response | None:
    """带重试的 HTTP GET，供所有 adapter 使用。dry_run 时只试一次。"""
    if dry_run:
        max_retries = 1
    import time

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException:
            log.warning(f"  超时 [{attempt}/{max_retries}]: {url}")
        except httpx.ConnectError:
            log.warning(f"  连接失败 [{attempt}/{max_retries}]: {url}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503):
                log.warning(f"  限流 [{attempt}/{max_retries}]: {url} → {e.response.status_code}")
            else:
                log.warning(f"  HTTP {e.response.status_code}: {url}")
                return None  # 非暂时性错误，不重试
        except httpx.HTTPError as e:
            log.warning(f"  网络错误 [{attempt}/{max_retries}]: {url} → {e}")

        if attempt < max_retries:
            wait = retry_delay * attempt
            log.info(f"  等待 {wait}s 后重试...")
            time.sleep(wait)

    log.error(f"  ❌ {max_retries} 次重试后仍失败: {url}")
    return None


# ── Adapter 注册表 ────────────────────────────────────────
_registry: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter):
    """注册一个 adapter 到全局注册表。"""
    _registry[adapter.adapter_type] = adapter
    log.debug(f"  注册 adapter: {adapter.adapter_type}")


def get_adapter(adapter_type: str) -> SourceAdapter | None:
    """按 type 名获取 adapter。"""
    return _registry.get(adapter_type)


def list_adapters() -> dict[str, SourceAdapter]:
    """返回所有已注册的 adapter。"""
    return dict(_registry)


def auto_discover():
    """自动发现并加载本目录下所有 adapter 模块。

    每个模块定义一个实现 SourceAdapter 协议的类，
    并在模块级调用 register() 注册自己。
    """
    package_dir = Path(__file__).parent
    for info in pkgutil.iter_modules([str(package_dir)]):
        if info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f".{info.name}", package=__name__)
        except Exception as e:
            log.warning(f"  加载 adapter 失败 [{info.name}]: {e}")

    log.info(f"  已加载 {len(_registry)} 个 adapter: {list(_registry.keys())}")
