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

from urllib.request import Request, urlopen
from urllib.error import URLError

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
            # gemini 需要参数输入，不支持 stdin
            if self.name == "gemini":
                cmd = self.cmd + [prompt]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                # claude 支持 stdin
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
        "gemini": ["gemini", "-p"],  # 需要参数: gemini -p "prompt"
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

## 用户兴趣权重

重点关注（高优先级 — 满足任一即倾向 PASS）:
- AI Agent 架构、多 Agent 系统、Agent 工具调用
- Rust / Zig 系统编程（性能优化、内存安全、编译器）
- 认知科学（决策模型、思维框架、学习理论）
- 一人公司 / 独立开发者（商业模式、效率工具、自动化）

次要关注（中优先级 — 需有实质内容才 PASS）:
- AI 论文：仅 SOTA 突破或全新范式，增量改进 SKIP
- 开源工具：有明确使用场景和可复现的方法

直接过滤（低优先级 — 默认 SKIP）:
- 纯新闻报道 / 政治评论
- 增量版本更新（如 v1.2.3 → v1.2.4）
- 无方法论支撑的观点文章 / 营销内容

## 硬约束

条目必须包含以下至少一项才能 PASS:
1. 可复现的方法（有步骤、有代码、有架构图）
2. 可直接使用的工具（有仓库地址或安装方式）
3. 有数据支撑的新发现（有实验、有 benchmark、有案例）

不满足以上任何一项的，即使主题相关也应 SKIP。

## 判断标准

- PASS: 满足兴趣权重 + 硬约束，有实质性新知识/新方法/新工具
- SKIP: 不满足硬约束 / 增量改进 / 重复已知 / 纯新闻 / 营销内容

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


def _fetch_arxiv_abstract(url: str) -> str:
    """从 arXiv abs 页面或 API 获取论文摘要。"""
    # 从 URL 提取 arXiv ID (支持 abs/pdf/html 格式)
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf|html)/(\d+\.\d+(?:v\d+)?)', url)
    if not arxiv_match:
        return ""

    arxiv_id = arxiv_match.group(1)
    api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        req = Request(api_url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            xml = resp.read().decode("utf-8", errors="replace")

        # 提取 <summary> 标签
        summary_match = re.search(r'<summary>(.*?)</summary>', xml, re.DOTALL)
        if summary_match:
            abstract = summary_match.group(1).strip()
            # 提取标题
            title_match = re.search(r'<title>(.*?)</title>', xml, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            # 提取作者
            authors = re.findall(r'<name>(.*?)</name>', xml)
            authors_str = ", ".join(authors[:5])
            if len(authors) > 5:
                authors_str += f" et al. ({len(authors)} authors)"

            return f"Title: {title}\nAuthors: {authors_str}\n\nAbstract:\n{abstract}"
    except (URLError, OSError, ValueError) as e:
        log.debug(f"    arXiv API 获取失败: {arxiv_id} → {e}")
    return ""


def _clean_html_to_text(html: str) -> str:
    """将 HTML 清理为纯文本。"""
    # 尝试提取语义化内容区域（按优先级）
    for tag in ("article", "main", r'div[^>]*class="[^"]*content[^"]*"',
                r'div[^>]*class="[^"]*post[^"]*"', r'div[^>]*class="[^"]*entry[^"]*"'):
        if tag.startswith("div"):
            pattern = rf"<{tag}>(.*?)</div>"
        else:
            pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            html = match.group(1)
            break

    # 去除噪声元素
    for noise_tag in ("script", "style", "nav", "header", "footer",
                       "aside", "noscript", "iframe", "svg"):
        html = re.sub(
            rf"<{noise_tag}[^>]*>.*?</{noise_tag}>", "",
            html, flags=re.DOTALL | re.IGNORECASE
        )
    # 去除 HTML 注释
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # 将 <br>/<p>/<li> 转换为换行
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>|</li>|</div>|</h[1-6]>", "\n", html, flags=re.IGNORECASE)
    # 去除剩余 HTML 标签
    text = re.sub(r"<[^>]+>", " ", html)
    # 清理多余空白（保留换行结构）
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_article_body(url: str) -> str:
    """获取文章原文正文，返回纯文本。对 arXiv 直接获取 abstract。"""
    if not url:
        return ""

    # arXiv 特殊处理
    if "arxiv.org" in url:
        abstract = _fetch_arxiv_abstract(url)
        if abstract:
            log.info(f"    ✓ arXiv abstract 获取成功")
            return abstract

    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            html = resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
    except (URLError, OSError, ValueError) as e:
        log.debug(f"    原文获取失败: {url} → {e}")
        return ""

    text = _clean_html_to_text(html)

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


# ── Taxonomy 验证 ─────────────────────────────────────────
# 近似映射表：常见错误 domain → 正确 domain
_DOMAIN_ALIASES: dict[str, str] = {
    "programming": "engineering",
    "software": "engineering",
    "cs": "engineering",
    "computer-science": "engineering",
    "ml": "ai",
    "machine-learning": "ai",
    "deep-learning": "ai",
    "nlp": "ai",
    "math": "science",
    "psychology": "science",
    "neuroscience": "science",
    "startup": "business",
    "startups": "business",
    "finance": "economics",
    "fintech": "economics",
    "ethics": "philosophy",
}


def validate_note_taxonomy(content: str, filepath_hint: str = "") -> str:
    """验证并修正笔记 frontmatter 中的 domain/tags，使其符合 taxonomy.yaml。

    1. 加载 taxonomy.yaml 获取合法 domain 和 topics
    2. 检查 frontmatter 中的 domain 是否合法，不合法则映射到最近的
    3. 检查 tags 是否在该 domain 的 topics 中，不合法则替换为最近的
    4. 返回修正后的完整 content 字符串
    """
    # 加载 taxonomy
    if not TAXONOMY_FILE.exists():
        return content
    try:
        with TAXONOMY_FILE.open(encoding="utf-8") as f:
            tax = yaml.safe_load(f)
    except Exception:
        return content

    domains_data = tax.get("domains", {})
    if not domains_data:
        return content

    valid_domains = set(domains_data.keys())
    domain_topics: dict[str, list[str]] = {
        d: info.get("topics", []) for d, info in domains_data.items()
    }

    # 解析 frontmatter
    fm_match = re.match(r'^---\s*\n([\s\S]*?)\n---', content)
    if not fm_match:
        return content

    fm_text = fm_match.group(1)
    try:
        fm = yaml.safe_load(fm_text)
    except Exception:
        return content

    if not isinstance(fm, dict):
        return content

    changed = False
    note_domain = fm.get("domain", "")

    # 验证 domain
    if note_domain not in valid_domains:
        mapped = _DOMAIN_ALIASES.get(note_domain.lower(), "")
        if mapped and mapped in valid_domains:
            log.info(f"    taxonomy 修正: domain '{note_domain}' → '{mapped}'")
            fm["domain"] = mapped
            note_domain = mapped
            changed = True
        else:
            # 默认回退到 ai
            log.warning(f"    taxonomy 修正: 未知 domain '{note_domain}' → 'ai'")
            fm["domain"] = "ai"
            note_domain = "ai"
            changed = True

    # 验证 tags
    valid_topics = set(domain_topics.get(note_domain, []))
    all_topics = set()
    for topics_list in domain_topics.values():
        all_topics.update(topics_list)

    tags = fm.get("tags", [])
    if isinstance(tags, list) and valid_topics:
        corrected_tags = []
        for tag in tags:
            if tag in valid_topics:
                corrected_tags.append(tag)
            elif tag in all_topics:
                # tag 存在但属于其他 domain，保留（LLM 可能有交叉意图）
                # 但替换为当前 domain 中最接近的
                best = _find_closest_tag(tag, valid_topics)
                if best:
                    log.info(f"    taxonomy 修正: tag '{tag}' → '{best}' (domain={note_domain})")
                    corrected_tags.append(best)
                    changed = True
                else:
                    corrected_tags.append(tag)
            else:
                # 完全未知 tag，找当前 domain 中最接近的
                best = _find_closest_tag(tag, valid_topics)
                if best:
                    log.info(f"    taxonomy 修正: tag '{tag}' → '{best}'")
                    corrected_tags.append(best)
                    changed = True
                else:
                    log.warning(f"    taxonomy 修正: 无法映射 tag '{tag}'，移除")
                    _record_taxonomy_candidate(tag, note_domain, filepath_hint)
                    changed = True

        if corrected_tags:
            fm["tags"] = corrected_tags
        elif valid_topics:
            # 所有 tags 都被移除，使用 domain 的第一个 topic
            fm["tags"] = [domain_topics[note_domain][0]]
            changed = True

    if not changed:
        return content

    # 重建 frontmatter
    new_fm_lines = ["---"]
    for key, val in fm.items():
        if key == "tags":
            tag_str = ", ".join(val) if isinstance(val, list) else str(val)
            new_fm_lines.append(f"tags: [{tag_str}]")
        elif isinstance(val, str) and ('"' in val or "'" in val or ":" in val):
            new_fm_lines.append(f'{key}: "{val}"')
        elif isinstance(val, str):
            new_fm_lines.append(f'{key}: "{val}"')
        else:
            new_fm_lines.append(f"{key}: {val}")
    new_fm_lines.append("---")
    new_fm = "\n".join(new_fm_lines)

    # 替换原 frontmatter
    body_after_fm = content[fm_match.end():]
    return new_fm + body_after_fm


def _record_taxonomy_candidate(tag: str, domain: str, source_note: str):
    """将被拒绝的 tag 追加到 taxonomy_candidates.jsonl 候选池。"""
    TAXONOMY_CANDIDATES = LOGS_DIR / "taxonomy_candidates.jsonl"
    TAXONOMY_CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "tag": tag,
        "domain": domain,
        "date": datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d"),
        "source": source_note,
    }
    with TAXONOMY_CANDIDATES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _find_closest_tag(tag: str, valid_tags: set[str]) -> str | None:
    """简单的字符串相似度匹配，找最接近的合法 tag。"""
    tag_lower = tag.lower().replace("_", "-").replace(" ", "-")

    # 精确匹配（大小写/分隔符不同）
    for vt in valid_tags:
        if vt.lower() == tag_lower:
            return vt

    # 子串匹配
    for vt in valid_tags:
        if tag_lower in vt or vt in tag_lower:
            return vt

    # 首字匹配
    for vt in valid_tags:
        if vt.startswith(tag_lower[:3]) or tag_lower.startswith(vt[:3]):
            return vt

    return None


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


# ── 批量笔记生成 prompt ──────────────────────────────────
NOTE_BATCH_SIZE = 5  # 每次批量生成的笔记数

BATCH_NOTE_PROMPT_TEMPLATE = textwrap.dedent("""\
你是一个知识提取专家。请基于以下多篇文章的原文内容，为每篇分别生成一篇结构化的知识笔记。
**你必须仅从原文中提炼知识，严禁编造不在原文中的信息。**

## 分类约束（必须严格遵守）

domain 必须从以下列表中选择一个，tags 必须从对应 domain 的 topics 中选择 1-3 个：

{taxonomy}

## 待处理文章

{articles_block}

## 输出格式

请为每篇文章输出一篇笔记，用 `===ARTICLE_ID===` 分隔（ID 对应文章编号）。
每篇笔记严格按以下 Markdown 格式：

```
===0===
---
source: "来源名"
url: "原始URL"
date: YYYY-MM-DD
domain: 从上方列表选一个
tags: [从对应 domain 选 1-3 个]
---

## 核心发现

用 2-3 句话概括最重要的发现

## 关键洞察

1. 洞察1
2. 洞察2
3. 洞察3

## 可操作要点

- 具体可以怎么做/怎么用

===1===
---
...（下一篇）
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

    # 验证并修正 taxonomy 合规性
    content = validate_note_taxonomy(content, filepath_hint=filename)

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content + "\n", encoding="utf-8")
    log.info(f"    ✅ 已写入: {filepath}")
    return filepath


def generate_notes_batch(
    items: list[dict], backend: LLMBackend, dry_run: bool = False
) -> dict[int, Path | None]:
    """批量调用 LLM 生成多篇笔记，减少 API 调用次数。返回 {item_index: filepath}。"""
    now = datetime.now(SHANGHAI_TZ)
    taxonomy = load_taxonomy()
    results: dict[int, Path | None] = {}

    for batch_start in range(0, len(items), NOTE_BATCH_SIZE):
        batch = items[batch_start : batch_start + NOTE_BATCH_SIZE]
        batch_items_with_body: list[tuple[int, dict, str, str, Path]] = []

        # 预获取所有原文 + 准备 slug/filepath
        for i, item in enumerate(batch):
            idx = batch_start + i
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            source = item.get("source_name", "Unknown")
            summary = item.get("summary", "")

            slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:60].strip('-') or "untitled"
            filename = f"{now.strftime('%Y-%m-%d')}_{slug}.md"
            filepath = NOTES_DIR / filename

            if filepath.exists():
                log.info(f"    笔记已存在，跳过: {filename}")
                results[idx] = filepath
                continue

            log.info(f"    ▸ 获取原文: {url[:80]}")
            body = fetch_article_body(url)
            if not body:
                body = f"(原文不可用，仅有摘要) {summary}"

            batch_items_with_body.append((idx, item, body, filename, filepath))

        if not batch_items_with_body:
            continue

        # 如果只有 1 篇，用单篇 prompt（更可靠）
        if len(batch_items_with_body) == 1:
            idx, item, body, filename, filepath = batch_items_with_body[0]
            result_path = generate_note(item, backend, dry_run)
            results[idx] = result_path
            continue

        # 构建批量 prompt
        articles_lines = []
        for local_i, (idx, item, body, filename, filepath) in enumerate(batch_items_with_body):
            articles_lines.append(
                f"### 文章 [{local_i}]\n"
                f"来源: {item.get('source_name', 'Unknown')}\n"
                f"标题: {item.get('title', 'Untitled')}\n"
                f"URL: {item.get('url', '')}\n"
                f"摘要: {item.get('summary', '')}\n\n"
                f"原文正文:\n{body}\n"
            )

        prompt = BATCH_NOTE_PROMPT_TEMPLATE.format(
            taxonomy=taxonomy,
            articles_block="\n---\n\n".join(articles_lines),
        )

        if dry_run:
            log.info(f"    [DRY RUN] 批量笔记: {len(batch_items_with_body)} 篇")
            for idx, *_ in batch_items_with_body:
                results[idx] = None
            continue

        log.info(f"    ▸ 批量生成 {len(batch_items_with_body)} 篇笔记...")
        raw = backend.call(prompt, timeout=180)

        if not raw:
            log.warning("    批量笔记生成失败，回退到逐篇生成")
            for idx, item, body, filename, filepath in batch_items_with_body:
                result_path = generate_note(item, backend, dry_run)
                results[idx] = result_path
            continue

        # 解析批量输出：按 ===ID=== 分隔
        note_blocks: dict[int, str] = {}
        parts = re.split(r'===(\d+)===', raw)
        # parts: ['前导文字', '0', '笔记内容0', '1', '笔记内容1', ...]
        for j in range(1, len(parts) - 1, 2):
            try:
                local_id = int(parts[j])
                content = parts[j + 1].strip()
                note_blocks[local_id] = content
            except (ValueError, IndexError):
                continue

        # 写入每篇笔记
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        for local_i, (idx, item, body, filename, filepath) in enumerate(batch_items_with_body):
            content = note_blocks.get(local_i, "")

            # 提取 markdown 块
            md_match = re.search(r'```markdown\s*\n([\s\S]*?)\n```', content)
            if md_match:
                content = md_match.group(1).strip()

            if not content or not content.startswith("---"):
                fm_match = re.search(r'(---[\s\S]*?---[\s\S]*)', content)
                if fm_match:
                    content = fm_match.group(1)
                else:
                    log.warning(f"    批量笔记 [{local_i}] 格式异常，回退到单篇生成: {filename}")
                    result_path = generate_note(item, backend, dry_run)
                    results[idx] = result_path
                    continue

            # 验证并修正 taxonomy 合规性
            content = validate_note_taxonomy(content, filepath_hint=filename)

            filepath.write_text(content + "\n", encoding="utf-8")
            log.info(f"    ✅ 已写入: {filepath}")
            results[idx] = filepath

    return results


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

    # 4. 深评 + 笔记生成（批量化）
    log.info("── 阶段 2: 深评 + 笔记生成 ──")
    generated_notes: list[Path] = []
    log_entries: list[dict] = []

    # 批量生成 PASS 条目的笔记
    batch_results: dict[int, Path | None] = {}
    if passed_items and not dry_run:
        batch_results = generate_notes_batch(passed_items, backend, dry_run)
    elif passed_items and dry_run:
        batch_results = generate_notes_batch(passed_items, backend, dry_run)

    # 构建 passed_items 的 URL→结果映射
    pass_note_map: dict[str, Path | None] = {}
    for i, item in enumerate(passed_items):
        url = item.get("url", "")
        pass_note_map[url] = batch_results.get(i)

    for item in items:
        entry = {
            "ts": now.isoformat(),
            "source": item.get("source_name", ""),
            "url": item.get("url", ""),
            "title": item.get("title", ""),
        }

        if item.get("screen_decision") == "PASS":
            note_path = pass_note_map.get(item.get("url", ""))
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
