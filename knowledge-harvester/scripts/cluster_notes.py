#!/usr/bin/env python3
"""
Knowledge Harvester — Layer 3: LLM 语义聚类
扫描 knowledge/notes/ → 将标题+标签交给 LLM 做语义分组 → 检测成熟集群。

核心设计：
  用 LLM 理解"这些笔记在讲什么"，而非靠字符串匹配或统计方法。
  LLM 天生能处理同义词、缩写、跨语言等 TF-IDF 无法解决的问题。

依赖: pyyaml（LLM 后端复用 harvest_llm 的 detect_backend）
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
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

from config import SHANGHAI_TZ, NOTES_DIR, DRAFTS_DIR

CLUSTER_THRESHOLD = 3  # >= N 篇笔记 → 标记为成熟集群

log = logging.getLogger("cluster_notes")


# ── 笔记解析 ──────────────────────────────────────────────
def parse_note(filepath: Path) -> dict | None:
    """解析笔记的 YAML frontmatter 和核心发现。"""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return None
    try:
        meta = yaml.safe_load(match.group(1))
        meta["_filename"] = filepath.name
        # 提取"核心发现"段落作为摘要
        body = match.group(2)
        core_match = re.search(
            r"##\s*核心发现\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL
        )
        meta["_core"] = core_match.group(1).strip() if core_match else ""
        return meta
    except yaml.YAMLError:
        return None


def scan_notes() -> list[dict]:
    """扫描 notes/ 目录下所有 .md 文件。"""
    if not NOTES_DIR.exists():
        log.warning(f"notes 目录不存在: {NOTES_DIR}")
        return []

    notes = []
    for md_file in sorted(NOTES_DIR.glob("*.md")):
        meta = parse_note(md_file)
        if meta:
            notes.append(meta)
        else:
            log.debug(f"跳过无 frontmatter 的文件: {md_file.name}")
    return notes


# ── LLM 后端（复用 harvest_llm 的逻辑） ──────────────────
def _call_llm(prompt: str, backend: str | None = None, timeout: int = 90) -> str:
    """调用 LLM CLI。"""
    backends = {
        "gemini": ["gemini", "-p"],
        "claude": ["claude", "-p", "--verbose"],
    }
    if backend and backend in backends:
        cmd = backends[backend]
    else:
        for name, cmd in backends.items():
            if shutil.which(cmd[0]):
                backend = name
                break
        else:
            log.error("未找到可用的 LLM CLI (gemini / claude)")
            return ""

    log.debug(f"  LLM [{backend}] prompt {len(prompt)} chars")
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception as e:
        log.error(f"  LLM [{backend}] 调用失败: {e}")
        return ""


# ── LLM 聚类 ─────────────────────────────────────────────
CLUSTER_PROMPT = textwrap.dedent("""\
你是一个知识管理专家。以下是一组知识笔记的摘要，请将它们按主题语义分组。

规则：
1. 只分组「讨论同一核心主题」的笔记（如"LLM Agent 架构"和"Agent 工具调用"应归为一组）
2. 同义词/缩写/不同语言视为相同（如 RL = reinforcement learning = 强化学习）
3. 单独一篇无法归组的，放入 "ungrouped"
4. 每个组给一个简短的主题标签名称（英文，kebab-case，如 llm-agents）

笔记列表：

{notes_block}

请严格按以下 JSON 格式输出，不要有任何额外文字：
```json
{{
  "clusters": [
    {{
      "label": "主题标签",
      "description": "这组笔记在讨论什么（一句话）",
      "note_ids": [0, 1, 3]
    }}
  ],
  "ungrouped": [2, 5]
}}
```
""")


def build_cluster_prompt(notes: list[dict]) -> str:
    """构建聚类 prompt。"""
    lines = []
    for i, note in enumerate(notes):
        title = note.get("title", note["_filename"])
        domain = note.get("domain", "?")
        tags = note.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        tags_str = ", ".join(tags) if tags else "N/A"
        core = note.get("_core", "")[:150]
        lines.append(
            f"[{i}] {title}\n"
            f"    domain={domain} tags=[{tags_str}]\n"
            f"    {core}\n"
        )
    return CLUSTER_PROMPT.format(notes_block="\n".join(lines))


def parse_cluster_result(raw: str) -> dict:
    """解析 LLM 输出的聚类 JSON。"""
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        log.warning("聚类输出中未找到 JSON")
        return {"clusters": [], "ungrouped": []}
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as e:
        log.warning(f"聚类 JSON 解析失败: {e}")
        return {"clusters": [], "ungrouped": []}


def run_llm_clustering(
    notes: list[dict],
    backend: str | None = None,
    dry_run: bool = False,
) -> dict:
    """调用 LLM 对笔记做语义聚类。"""
    prompt = build_cluster_prompt(notes)

    if dry_run:
        log.info(f"  [DRY RUN] 聚类 prompt ({len(prompt)} chars)")
        print(prompt[:1000] + "...")
        return {"clusters": [], "ungrouped": list(range(len(notes)))}

    log.info(f"  ▸ 调用 LLM 进行语义聚类 ({len(notes)} 篇笔记)...")
    raw = _call_llm(prompt, backend)

    if not raw:
        log.error("  LLM 无输出")
        return {"clusters": [], "ungrouped": list(range(len(notes)))}

    return parse_cluster_result(raw)


# ── 主逻辑 ────────────────────────────────────────────────
def run(
    threshold: int = CLUSTER_THRESHOLD,
    backend: str | None = None,
    dry_run: bool = False,
):
    """扫描 + LLM 聚类 + 输出报告。"""
    now = datetime.now(SHANGHAI_TZ)
    log.info(f"=== 笔记聚类扫描 @ {now.isoformat()} ===")

    notes = scan_notes()
    log.info(f"  扫描到 {len(notes)} 篇笔记")

    if not notes:
        print("📭 notes/ 目录为空，无可聚类笔记。")
        return

    # Tag 统计
    all_tags = Counter()
    for note in notes:
        tags = note.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                all_tags[tag] += 1

    # LLM 语义聚类
    log.info("  ▸ LLM 语义聚类...")
    result = run_llm_clustering(notes, backend, dry_run)

    # 转为报告格式
    mature_clusters = {}
    for cluster in result.get("clusters", []):
        label = cluster.get("label", "unknown")
        ids = cluster.get("note_ids", [])
        if len(ids) < threshold:
            continue

        cluster_notes = [notes[i] for i in ids if i < len(notes)]
        draft_dir = DRAFTS_DIR / label.replace(" ", "-")
        has_draft = draft_dir.exists() and (draft_dir / "DRAFT.md").exists()

        mature_clusters[label] = {
            "count": len(cluster_notes),
            "description": cluster.get("description", ""),
            "notes": [n["_filename"] for n in cluster_notes],
            "domains": list(set(n.get("domain", "unknown") for n in cluster_notes)),
            "has_existing_draft": has_draft,
        }

    report = {
        "generated_at": now.isoformat(),
        "total_notes": len(notes),
        "unique_tags": len(all_tags),
        "tag_distribution": dict(all_tags.most_common(20)),
        "threshold": threshold,
        "llm_clusters": len(result.get("clusters", [])),
        "mature_clusters": mature_clusters,
        "ungrouped_count": len(result.get("ungrouped", [])),
        "actionable": [
            label for label, info in mature_clusters.items()
            if not info["has_existing_draft"]
        ],
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["actionable"]:
        log.info(f"  🟢 {len(report['actionable'])} 个主题可生成 Skill 草稿: {report['actionable']}")
    else:
        log.info("  ⏳ 暂无可操作的成熟集群")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Harvester Layer 3 — LLM 语义聚类"
    )
    parser.add_argument(
        "--threshold", "-t", type=int, default=CLUSTER_THRESHOLD,
        help=f"成熟集群阈值 (default: {CLUSTER_THRESHOLD})"
    )
    parser.add_argument(
        "--backend", choices=["gemini", "claude"], default=None,
        help="LLM 后端 (默认自动检测)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印 prompt，不调用 LLM"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    run(threshold=args.threshold, backend=args.backend, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
