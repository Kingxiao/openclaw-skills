#!/usr/bin/env python3
"""
Knowledge Harvester — Layer 2: LLM 编排
读取 pending_items.json → 调用外部 LLM CLI (gemini/claude) → 快筛 + 深评 + 笔记生成

用法:
    python harvest_llm.py                  # 完整执行
    python harvest_llm.py --limit 5        # 仅处理前 5 条
    python harvest_llm.py --dry-run        # 打印 prompt 但不实际调用 LLM
    python harvest_llm.py --backend claude # 强制使用 claude
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

import yaml

from config import (
    SHANGHAI_TZ, NOTES_DIR, LOGS_DIR,
    PENDING_ITEMS, HARVEST_LOG, HTTP_TIMEOUT, USER_AGENT,
    TAXONOMY_FILE,
)

log = logging.getLogger("harvest_llm")

# ── 快筛批次大小 ──────────────────────────────────────────
BATCH_SIZE = 15  # 每次快筛的条目数


# ── LLM 后端 ──────────────────────────────────────────────
class LLMBackend:
    """统一 LLM CLI 调用接口。"""

    def __init__(self, name: str, cmd: list[str]):
        self.name = name
        self.cmd = cmd

    def call(self, prompt: str, timeout: int = 120) -> str:
        """调用 LLM CLI，返回文本输出。"""
        log.debug(f"  LLM [{self.name}] prompt 长度={len(prompt)} chars")
        try:
            result = subprocess.run(
                self.cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                log.warning(f"  LLM [{self.name}] 非零退出码 {result.returncode}: {stderr[:200]}")
            output = result.stdout.strip()
            log.debug(f"  LLM [{self.name}] 输出长度={len(output)} chars")
            return output
        except subprocess.TimeoutExpired:
            log.error(f"  LLM [{self.name}] 超时 ({timeout}s)")
            return ""
        except Exception as e:
            log.error(f"  LLM [{self.name}] 调用失败: {e}")
            return ""


def detect_backend(preferred: str | None = None) -> LLMBackend:
    """检测可用的 LLM CLI 后端。优先级: preferred > gemini > claude。"""
    backends = {
        "gemini": ["gemini", "-p"],
        "claude": ["claude", "-p", "--verbose"],
    }

    if preferred and preferred in backends:
        cmd_name = backends[preferred][0]
        if shutil.which(cmd_name):
            log.info(f"使用指定后端: {preferred}")
            return LLMBackend(preferred, backends[preferred])
        log.warning(f"指定后端 {preferred} 不可用，尝试自动检测")

    for name, cmd in backends.items():
        if shutil.which(cmd[0]):
            log.info(f"自动检测到后端: {name}")
            return LLMBackend(name, cmd)

    log.error("未找到可用的 LLM CLI 工具 (gemini / claude)")
    sys.exit(1)


# ── 快筛 (Stage 1) ───────────────────────────────────────
SCREEN_PROMPT_TEMPLATE = textwrap.dedent("""\
你是一个知识过滤器。你的任务是判断以下信息条目是否值得深入阅读。

判断标准: "这条信息能教会我一个新的做法、新的思考方式或新的工具吗?"
- PASS: 有实质性新知识/新方法/新工具/重要趋势
- SKIP: 增量改进 / 重复已知 / 纯新闻无干货 / 营销内容

请严格按照以下 JSON 格式输出，不要有任何额外文字:
```json
[
  {{"id": 0, "decision": "PASS", "reason": "简短理由"}},
  {{"id": 1, "decision": "SKIP", "reason": "简短理由"}}
]
```

以下是待筛选的条目:

{items_block}
""")


def build_screen_prompt(items: list[dict]) -> str:
    """构建快筛 prompt。"""
    lines = []
    for i, item in enumerate(items):
        source = item.get("source_name", "Unknown")
        title = item.get("title", "Untitled")
        summary = item.get("summary", "")[:300]
        lines.append(f"[{i}] 来源: {source}\n    标题: {title}\n    摘要: {summary}\n")
    return SCREEN_PROMPT_TEMPLATE.format(items_block="\n".join(lines))


def parse_screen_result(raw: str) -> list[dict]:
    """解析快筛 JSON 结果。"""
    # 尝试从输出中提取 JSON 数组
    json_match = re.search(r'\[[\s\S]*?\]', raw)
    if not json_match:
        log.warning("快筛输出中未找到 JSON 数组")
        return []
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as e:
        log.warning(f"快筛 JSON 解析失败: {e}")
        return []


def run_screening(
    items: list[dict], backend: LLMBackend, dry_run: bool = False
) -> list[dict]:
    """批量快筛，返回 PASS 条目列表。"""
    all_passed: list[dict] = []
    all_skipped: list[dict] = []

    for batch_start in range(0, len(items), BATCH_SIZE):
        batch = items[batch_start : batch_start + BATCH_SIZE]
        prompt = build_screen_prompt(batch)

        if dry_run:
            log.info(f"  [DRY RUN] 快筛批次 {batch_start // BATCH_SIZE + 1} ({len(batch)} 条)")
            log.debug(f"  Prompt:\n{prompt[:500]}...")
            # dry_run 模式下全部视为 PASS
            all_passed.extend(batch)
            continue

        log.info(f"  ▸ 快筛批次 {batch_start // BATCH_SIZE + 1} ({len(batch)} 条)")
        raw = backend.call(prompt, timeout=90)

        if not raw:
            log.warning("  快筛无输出，本批次全部跳过")
            all_skipped.extend(batch)
            continue

        decisions = parse_screen_result(raw)

        # 映射 decision 到 items
        decision_map: dict[int, dict] = {d["id"]: d for d in decisions if "id" in d}
        for i, item in enumerate(batch):
            d = decision_map.get(i, {})
            decision = d.get("decision", "SKIP").upper()
            reason = d.get("reason", "未返回判断")
            item["screen_decision"] = decision
            item["screen_reason"] = reason
            if decision == "PASS":
                all_passed.append(item)
            else:
                all_skipped.append(item)

    log.info(f"  快筛完成: {len(all_passed)} PASS / {len(all_skipped)} SKIP")
    return all_passed


# ── 原文获取 ──────────────────────────────────────────────
ARTICLE_MAX_CHARS = 8000  # 拼入 prompt 的原文上限


def fetch_article_body(url: str) -> str:
    """获取文章原文正文，返回纯文本（去 HTML 标签）。"""
    if not url:
        return ""
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        log.debug(f"    原文获取失败: {url} → {e}")
        return ""

    html = resp.text

    # 尝试提取 <article> 或 <main> 区域
    for tag in ("article", "main"):
        match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.DOTALL | re.IGNORECASE)
        if match:
            html = match.group(1)
            break

    # 去 script/style
    html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 去 HTML 标签
    text = re.sub(r"<[^>]+>", " ", html)
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > ARTICLE_MAX_CHARS:
        text = text[:ARTICLE_MAX_CHARS] + "... [截断]"

    return text


# ── Taxonomy 加载 ─────────────────────────────────────────
def load_taxonomy() -> str:
    """加载 taxonomy.yaml，转换为 prompt 可用的文本格式。"""
    if not TAXONOMY_FILE.exists():
        log.warning(f"taxonomy.yaml 不存在: {TAXONOMY_FILE}，使用默认分类")
        return "ai, science, business, economics, engineering, philosophy"
    try:
        with TAXONOMY_FILE.open(encoding="utf-8") as f:
            tax = yaml.safe_load(f)
        lines = []
        for domain, info in tax.get("domains", {}).items():
            topics = info.get("topics", [])
            lines.append(f"  {domain}: {', '.join(topics)}")
        return "\n".join(lines)
    except Exception as e:
        log.warning(f"taxonomy.yaml 加载失败: {e}")
        return "ai, science, business, economics, engineering, philosophy"


# ── 深评 + 笔记生成 (Stage 2) ────────────────────────────
NOTE_PROMPT_TEMPLATE = textwrap.dedent("""\
你是一个知识提取专家。请基于以下原文内容生成一篇结构化的知识笔记。
**你必须仅从原文中提炼知识，严禁编造不在原文中的信息。**

来源: {source}
标题: {title}
URL: {url}
摘要: {summary}

原文正文:
{body}

## 分类约束（必须严格遵守）

domain 必须从以下列表中选择一个，tags 必须从对应 domain 的 topics 中选择 1-3 个：

{taxonomy}

请严格按照以下 Markdown 格式输出整篇笔记，不要有任何额外解释:

```markdown
---
source: "{source}"
url: "{url}"
date: {date}
domain: {{从上方列表中选一个 domain}}
tags: [{{从对应 domain 的 topics 中选 1-3 个}}]
---

## 核心发现

{{用 2-3 句话概括最重要的发现}}

## 关键洞察

1. {{洞察1}}
2. {{洞察2}}
3. {{洞察3}}

## 可操作要点

- {{具体可以怎么做/怎么用}}
```
""")


def generate_note(
    item: dict, backend: LLMBackend, dry_run: bool = False
) -> Path | None:
    """调用 LLM 生成单篇知识笔记，写入文件。"""
    now = datetime.now(SHANGHAI_TZ)
    title = item.get("title", "Untitled")
    url = item.get("url", "")
    source = item.get("source_name", "Unknown")
    summary = item.get("summary", "")

    # 生成 slug
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:60].strip('-')
    if not slug:
        slug = "untitled"
    filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"
    filepath = NOTES_DIR / filename

    # 检查是否已存在
    if filepath.exists():
        log.info(f"    笔记已存在，跳过: {filename}")
        return filepath

    # 获取原文正文
    log.info(f"    ▸ 获取原文: {url[:80]}")
    body = fetch_article_body(url)
    if body:
        log.info(f"    ✓ 原文 {len(body)} 字符")
    else:
        log.warning(f"    ⚠ 原文获取失败，将仅用摘要生成")
        body = f"(原文不可用，仅有摘要) {summary}"

    prompt = NOTE_PROMPT_TEMPLATE.format(
        source=source,
        title=title,
        url=url,
        summary=summary,
        body=body,
        date=now.strftime("%Y-%m-%d"),
        taxonomy=load_taxonomy(),
    )

    if dry_run:
        log.info(f"    [DRY RUN] 笔记: {filename}")
        return None

    log.info(f"    ▸ 生成笔记: {filename}")
    raw = backend.call(prompt, timeout=120)

    if not raw:
        log.warning(f"    笔记生成失败: {title}")
        return None

    # 提取 markdown 内容
    md_match = re.search(r'```markdown\s*\n([\s\S]*?)\n```', raw)
    content = md_match.group(1).strip() if md_match else raw.strip()

    # 基本验证：必须包含 frontmatter
    if not content.startswith("---"):
        log.warning(f"    笔记格式异常（缺少 frontmatter），尝试修复: {filename}")
        # 尝试提取 --- 之间的内容
        fm_match = re.search(r'(---[\s\S]*?---[\s\S]*)', content)
        if fm_match:
            content = fm_match.group(1)
        else:
            log.error(f"    笔记格式无法修复，跳过: {filename}")
            return None

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content + "\n", encoding="utf-8")
    log.info(f"    ✅ 已写入: {filepath}")
    return filepath


# ── 日志记录 ──────────────────────────────────────────────
def append_harvest_log(entries: list[dict]):
    """追加记录到 harvest.jsonl。"""
    HARVEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with HARVEST_LOG.open("a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 主逻辑 ────────────────────────────────────────────────
def run(
    backend_name: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行 Layer 2 完整流程。"""
    now = datetime.now(SHANGHAI_TZ)
    log.info(f"=== Layer 2 开始 @ {now.isoformat()} ===")

    # 1. 读取 pending items
    if not PENDING_ITEMS.exists():
        log.error(f"pending_items.json 不存在: {PENDING_ITEMS}")
        log.error("请先运行 fetch_sources.py (Layer 1)")
        sys.exit(1)

    with PENDING_ITEMS.open(encoding="utf-8") as f:
        pending = json.load(f)

    items = pending.get("items", [])
    if not items:
        log.info("无待处理条目，退出。")
        return {"status": "empty"}

    if limit:
        items = items[:limit]
        log.info(f"限制处理前 {limit} 条")

    log.info(f"共 {len(items)} 条待处理")

    # 2. 检测 LLM 后端
    backend = detect_backend(backend_name)

    # 3. 快筛
    log.info("── 阶段 1: 快筛 ──")
    passed_items = run_screening(items, backend, dry_run)

    # 4. 深评 + 笔记生成
    log.info("── 阶段 2: 深评 + 笔记生成 ──")
    generated_notes: list[Path] = []
    log_entries: list[dict] = []

    for item in items:
        entry = {
            "ts": now.isoformat(),
            "source": item.get("source_name", ""),
            "url": item.get("url", ""),
            "title": item.get("title", ""),
        }

        if item.get("screen_decision") == "PASS":
            note_path = generate_note(item, backend, dry_run)
            if note_path:
                generated_notes.append(note_path)
                entry["decision"] = "PASS"
                entry["note"] = note_path.name
            else:
                entry["decision"] = "PASS"
                entry["note"] = "generation_failed" if not dry_run else "dry_run"
        else:
            entry["decision"] = "SKIP"
            entry["reason"] = item.get("screen_reason", "快筛未通过")

        log_entries.append(entry)

    # 5. 写日志
    if not dry_run:
        append_harvest_log(log_entries)
        # 清空 pending_items.json (保留元数据，清空 items)
        pending["items"] = []
        pending["processed_at"] = now.isoformat()
        with PENDING_ITEMS.open("w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)
        log.info(f"  📝 已更新 harvest.jsonl ({len(log_entries)} 条)")

    # 6. 统计报告
    pass_count = sum(1 for e in log_entries if e["decision"] == "PASS")
    skip_count = sum(1 for e in log_entries if e["decision"] == "SKIP")
    total = len(log_entries)
    pass_rate = pass_count / total * 100 if total else 0

    report = (
        f"\n📊 采集报告 [{backend.name}] {now.strftime('%Y-%m-%d')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"待处理: {total} 条\n"
        f"快筛: {pass_count} PASS / {skip_count} SKIP ({pass_rate:.0f}% 通过率)\n"
        f"笔记生成: {len(generated_notes)} 篇\n"
    )

    if generated_notes:
        report += "新笔记:\n"
        for p in generated_notes:
            report += f"  • {p.name}\n"

    if dry_run:
        report += "⚠️  DRY RUN — 未实际调用 LLM\n"

    print(report)
    log.info("=== Layer 2 完成 ===")

    return {
        "status": "done",
        "total": total,
        "passed": pass_count,
        "skipped": skip_count,
        "notes_generated": len(generated_notes),
        "pass_rate": f"{pass_rate:.0f}%",
    }


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Harvester Layer 2 — LLM 快筛 + 笔记生成"
    )
    parser.add_argument(
        "--backend", choices=["gemini", "claude"], default=None,
        help="LLM 后端 (默认自动检测: gemini > claude)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="限制处理条目数量 (调试用)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印 prompt，不实际调用 LLM"
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

    run(backend_name=args.backend, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
