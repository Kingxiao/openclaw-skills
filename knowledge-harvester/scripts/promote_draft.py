#!/usr/bin/env python3
"""
Knowledge Harvester — Layer 3: Draft → 正式 Skill 提升
将审批通过的 Skill 草稿从 knowledge/skill-drafts/ 移动到
extensions/ai-skills/ 并执行 git add。

用法:
  python promote_draft.py <draft-name>
  python promote_draft.py dpo-training  # → extensions/ai-skills/dpo-training/SKILL.md
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from config import DRAFTS_DIR, OPENCLAW_DIR, SKILL_DIR

SKILLS_DIR = SKILL_DIR.parent  # extensions/ai-skills/

log = logging.getLogger("promote_draft")


def promote(draft_name: str, dry_run: bool = False) -> bool:
    """将 Draft 提升为正式 Skill。"""
    draft_dir = DRAFTS_DIR / draft_name
    draft_file = draft_dir / "DRAFT.md"

    if not draft_dir.exists():
        log.error(f"❌ Draft 目录不存在: {draft_dir}")
        return False

    if not draft_file.exists():
        log.error(f"❌ DRAFT.md 不存在: {draft_file}")
        return False

    target_dir = SKILLS_DIR / draft_name
    target_file = target_dir / "SKILL.md"

    if target_dir.exists():
        log.warning(f"⚠️ 目标 Skill 已存在: {target_dir}")
        log.warning("  将合并（追加）到已有 Skill。")
        # 如果已存在，只追加内容而不是覆盖
        if not dry_run:
            existing = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
            new_content = draft_file.read_text(encoding="utf-8")
            with target_file.open("w", encoding="utf-8") as f:
                f.write(existing + "\n\n" + new_content if existing else new_content)
    else:
        log.info(f"  📁 创建目标目录: {target_dir}")
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            # 复制整个 draft 目录内容
            for item in draft_dir.iterdir():
                dest = target_dir / (
                    "SKILL.md" if item.name == "DRAFT.md" else item.name
                )
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir():
                    shutil.copytree(item, dest)

    # git add
    if not dry_run:
        try:
            subprocess.run(
                ["git", "add", str(target_dir)],
                cwd=str(SKILLS_DIR),
                check=True,
                capture_output=True,
            )
            log.info(f"  ✅ git add 完成: {target_dir.relative_to(SKILLS_DIR)}")
        except subprocess.CalledProcessError as e:
            log.warning(f"  ⚠️ git add 失败（可能不在 git 仓库中）: {e.stderr.decode()}")
        except FileNotFoundError:
            log.warning("  ⚠️ git 命令不可用")

    # 标记 draft 为已提升
    if not dry_run:
        promoted_marker = draft_dir / ".promoted"
        promoted_marker.write_text(
            f"Promoted to {target_dir} at {__import__('datetime').datetime.now().isoformat()}\n",
            encoding="utf-8",
        )

    action = "[DRY RUN] " if dry_run else ""
    log.info(f"  {action}🎉 Draft '{draft_name}' → Skill 提升完成")
    return True


def list_drafts():
    """列出所有可提升的 Drafts。"""
    if not DRAFTS_DIR.exists():
        print("📭 暂无 Draft。")
        return

    drafts = [d for d in DRAFTS_DIR.iterdir() if d.is_dir() and (d / "DRAFT.md").exists()]
    if not drafts:
        print("📭 暂无 Draft。")
        return

    print(f"📋 可提升的 Drafts ({len(drafts)}):\n")
    for d in sorted(drafts):
        promoted = (d / ".promoted").exists()
        status = " [已提升]" if promoted else ""
        print(f"  • {d.name}{status}")


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Harvester Layer 3 — Draft → Skill 提升"
    )
    parser.add_argument("draft_name", nargs="?", help="要提升的 Draft 名称")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有 Drafts")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟，不执行")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        list_drafts()
        return

    if not args.draft_name:
        parser.error("请指定 Draft 名称，或使用 --list 查看可用 Drafts")

    success = promote(args.draft_name, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
