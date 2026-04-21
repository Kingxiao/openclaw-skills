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
import sys
import textwrap
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from config import SHANGHAI_TZ, NOTES_DIR, DRAFTS_DIR, LOGS_DIR, TAXONOMY_FILE
from harvest_llm import LLMBackend, detect_backend

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
    backend_name: str | None = None,
    dry_run: bool = False,
) -> dict:
    """调用 LLM 对笔记做语义聚类。"""
    prompt = build_cluster_prompt(notes)

    if dry_run:
        log.info(f"  [DRY RUN] 聚类 prompt ({len(prompt)} chars)")
        print(prompt[:1000] + "...")
        return {"clusters": [], "ungrouped": list(range(len(notes)))}

    llm = detect_backend(backend_name)
    log.info(f"  ▸ 调用 LLM [{llm.name}] 进行语义聚类 ({len(notes)} 篇笔记)...")
    raw = llm.call(prompt, timeout=90)

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
    result = run_llm_clustering(notes, backend_name=backend, dry_run=dry_run)

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


# ── Taxonomy 自适应增长 ──────────────────────────────────
TAXONOMY_CANDIDATES = LOGS_DIR / "taxonomy_candidates.jsonl"
PROMOTE_THRESHOLD = 3   # >= N 个不同来源笔记
WINDOW_DAYS = 7         # 时间窗口


def auto_grow_taxonomy():
    """扫描候选池，将高频被拒 tag 自动提升为正式 taxonomy topic。"""
    if not TAXONOMY_CANDIDATES.exists():
        return

    now = datetime.now(SHANGHAI_TZ)
    cutoff = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")

    # 1. 读取所有候选记录
    candidates: list[dict] = []
    with TAXONOMY_CANDIDATES.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not candidates:
        return

    # 2. 筛选 7 天窗口内的记录，按 (domain, tag) 分组统计唯一来源
    recent: list[dict] = []
    expired: list[dict] = []
    for c in candidates:
        if c.get("date", "") >= cutoff:
            recent.append(c)
        else:
            expired.append(c)

    # 按 (domain, tag) 统计唯一 source
    groups: dict[tuple[str, str], set[str]] = {}
    for c in recent:
        key = (c.get("domain", ""), c.get("tag", ""))
        source = c.get("source", "")
        if key[0] and key[1]:
            groups.setdefault(key, set()).add(source)

    # 3. 找出达到阈值的候选
    promoted: list[tuple[str, str]] = []
    for (domain, tag), sources in groups.items():
        if len(sources) >= PROMOTE_THRESHOLD:
            promoted.append((domain, tag))

    # 4. 更新 taxonomy.yaml
    if promoted and TAXONOMY_FILE.exists():
        try:
            with TAXONOMY_FILE.open(encoding="utf-8") as f:
                tax = yaml.safe_load(f)
        except Exception as e:
            log.warning(f"  taxonomy.yaml 加载失败: {e}")
            tax = None

        if tax and "domains" in tax:
            actually_added = []
            for domain, tag in promoted:
                if domain not in tax["domains"]:
                    continue
                topics = tax["domains"][domain].get("topics", [])
                if tag not in topics:
                    topics.append(tag)
                    tax["domains"][domain]["topics"] = topics
                    actually_added.append((domain, tag))
                    log.info(f"  taxonomy 自适应: 新增 '{tag}' → {domain}")

            if actually_added:
                with TAXONOMY_FILE.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(tax, f, default_flow_style=False, allow_unicode=True)
                promoted = actually_added

    # 5. 清理 JSONL：保留未过期且未被提升的记录
    promoted_set = set(promoted)
    remaining: list[dict] = []
    for c in recent:
        key = (c.get("domain", ""), c.get("tag", ""))
        if key not in promoted_set:
            remaining.append(c)

    with TAXONOMY_CANDIDATES.open("w", encoding="utf-8") as f:
        for c in remaining:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 6. 报告
    print(f"Taxonomy 自适应: 新增 {len(promoted)} 个 topics, 候选池 {len(remaining)} 条")


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

    # Taxonomy 自适应增长
    auto_grow_taxonomy()


if __name__ == "__main__":
    main()
