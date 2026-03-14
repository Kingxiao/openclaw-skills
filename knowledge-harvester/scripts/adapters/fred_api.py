"""
FRED (Federal Reserve Economic Data) API 适配器

拉取关键经济指标的最新观测值。
sources.yaml 中 type: fred_api

配置项:
  api_key_env: "FRED_API_KEY"    # 环境变量名
  series_ids: [GDP, UNRATE, ...]  # 要追踪的指标
"""

from __future__ import annotations

import logging
import os
from typing import Any

from . import HTTPConfig, http_get, make_item, register

log = logging.getLogger("adapters.fred_api")


class FREDApiAdapter:
    """FRED 经济数据 API 适配器。"""

    adapter_type = "fred_api"

    def fetch(self, config: dict[str, Any], client: HTTPConfig) -> list[dict[str, Any]]:
        key_env = config.get("api_key_env", "FRED_API_KEY")
        api_key = os.environ.get(key_env, "")
        if not api_key:
            log.info(f"  ⏭ FRED: 未设置 {key_env}，跳过")
            return []

        series_ids = config.get("series_ids", ["GDP", "UNRATE", "CPIAUCSL", "DFF", "T10Y2Y"])
        items = []

        for sid in series_ids:
            obs_url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={sid}&api_key={api_key}&file_type=json"
                f"&sort_order=desc&limit=1"
            )
            resp = http_get(client, obs_url, max_retries=2)
            if not resp:
                continue

            try:
                data = resp.json()
                obs = data.get("observations", [])
                if not obs:
                    continue

                latest = obs[0]
                value = latest.get("value", "N/A")
                date = latest.get("date", "")

                # 获取 series 元数据
                title = sid
                notes = ""
                meta_url = (
                    f"https://api.stlouisfed.org/fred/series"
                    f"?series_id={sid}&api_key={api_key}&file_type=json"
                )
                meta_resp = http_get(client, meta_url, max_retries=1)
                if meta_resp:
                    meta = meta_resp.json()
                    serieses = meta.get("seriess", [])
                    if serieses:
                        title = serieses[0].get("title", sid)
                        notes = serieses[0].get("notes", "")[:200]

                items.append(make_item(
                    title=f"FRED {sid}: {title}",
                    url=f"https://fred.stlouisfed.org/series/{sid}",
                    summary=f"Latest: {value} ({date}). {notes}",
                    published=date,
                    source_type="api",
                    metadata={"series_id": sid, "value": value, "date": date},
                ))
            except Exception as e:
                log.warning(f"  FRED [{sid}] 解析失败: {e}")

        return items


# 自注册
register(FREDApiAdapter())
