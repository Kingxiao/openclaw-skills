#!/usr/bin/env python3
"""
Skill Auditor - 回归检测器

对比技能版本变化，检测破坏性变更：
- 触发词变更检测
- 功能移除检测
- 脚本 API 变化
- 向后兼容性评估

Usage:
    python regression_checker.py <new-skill-path> --baseline <old-skill-path>
    
Returns:
    RegressionResult with change classification
"""

import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ChangeType(Enum):
    """变更类型"""
    BREAKING = "BREAKING"      # 破坏性变更
    COMPATIBLE = "COMPATIBLE"  # 兼容性变更
    ENHANCEMENT = "ENHANCEMENT"  # 增强性变更
    COSMETIC = "COSMETIC"      # 表面性变更


@dataclass
class Change:
    """变更记录"""
    change_type: ChangeType
    category: str
    description: str
    severity: str = "medium"  # high, medium, low
    details: Optional[str] = None


@dataclass
class RegressionResult:
    """回归检测结果"""
    passed: bool
    breaking_changes: list = field(default_factory=list)
    compatible_changes: list = field(default_factory=list)
    enhancements: list = field(default_factory=list)
    summary: str = ""


def extract_frontmatter(content: str) -> dict:
    """提取 YAML frontmatter"""
    if not content.startswith("---"):
        return {}
    
    second_delimiter = content.find("---", 3)
    if second_delimiter == -1:
        return {}
    
    frontmatter_text = content[3:second_delimiter].strip()
    frontmatter = {}
    
    for line in frontmatter_text.split("\n"):
        match = re.match(r'^([a-z_-]+):\s*(.+)$', line, re.IGNORECASE)
        if match:
            frontmatter[match.group(1).lower()] = match.group(2).strip()
    
    return frontmatter


def extract_sections(content: str) -> dict:
    """提取章节标题"""
    sections = {}
    current_section = None
    current_content = []
    
    for line in content.split("\n"):
        match = re.match(r'^(#+)\s+(.+)$', line)
        if match:
            # 保存之前的章节
            if current_section:
                sections[current_section] = "\n".join(current_content)
            
            level = len(match.group(1))
            title = match.group(2).strip().lower()
            current_section = title
            current_content = []
        else:
            current_content.append(line)
    
    # 保存最后一个章节
    if current_section:
        sections[current_section] = "\n".join(current_content)
    
    return sections


def extract_triggers(description: str) -> set[str]:
    """从 description 提取触发词"""
    # 提取有意义的关键词
    words = re.findall(r'\b\w{3,}\b', description.lower())
    
    # 过滤停用词
    stop_words = {
        'this', 'that', 'with', 'from', 'when', 'what', 'where', 'which',
        'should', 'would', 'could', 'will', 'have', 'been', 'being',
        'about', 'using', 'used', 'uses', 'also', 'into', 'than', 'the',
        'and', 'for', 'are', 'not', 'can', 'any', 'all', 'your', 'our',
    }
    
    return {w for w in words if w not in stop_words}


def extract_scripts(skill_dir: Path) -> dict:
    """提取脚本及其签名"""
    scripts = {}
    scripts_dir = skill_dir / "scripts"
    
    if not scripts_dir.exists():
        return scripts
    
    for script in scripts_dir.rglob("*.py"):
        rel_path = str(script.relative_to(skill_dir))
        try:
            content = script.read_text(encoding="utf-8")
            # 提取函数签名
            functions = re.findall(
                r'^def\s+(\w+)\s*\(([^)]*)\)',
                content,
                re.MULTILINE
            )
            scripts[rel_path] = {
                "functions": {name: params for name, params in functions},
                "size": len(content),
            }
        except:
            scripts[rel_path] = {"functions": {}, "size": 0}
    
    return scripts


def compare_triggers(old_triggers: set, new_triggers: set) -> list[Change]:
    """比较触发词变化"""
    changes = []
    
    removed = old_triggers - new_triggers
    added = new_triggers - old_triggers
    
    if removed:
        changes.append(Change(
            change_type=ChangeType.BREAKING,
            category="triggers",
            description=f"移除触发词: {', '.join(sorted(removed))}",
            severity="high",
            details="这些关键词被移除后，原有使用场景可能无法触发此技能"
        ))
    
    if added:
        changes.append(Change(
            change_type=ChangeType.ENHANCEMENT,
            category="triggers",
            description=f"新增触发词: {', '.join(sorted(added))}",
            severity="low"
        ))
    
    return changes


def compare_sections(old_sections: dict, new_sections: dict) -> list[Change]:
    """比较章节变化"""
    changes = []
    
    old_titles = set(old_sections.keys())
    new_titles = set(new_sections.keys())
    
    removed = old_titles - new_titles
    added = new_titles - old_titles
    
    # 检查重要章节移除
    important_keywords = ['overview', 'instruction', 'step', 'how', 'usage', 'example']
    
    for title in removed:
        is_important = any(kw in title for kw in important_keywords)
        if is_important:
            changes.append(Change(
                change_type=ChangeType.BREAKING,
                category="sections",
                description=f"移除重要章节: {title}",
                severity="high"
            ))
        else:
            changes.append(Change(
                change_type=ChangeType.COMPATIBLE,
                category="sections",
                description=f"移除章节: {title}",
                severity="medium"
            ))
    
    for title in added:
        changes.append(Change(
            change_type=ChangeType.ENHANCEMENT,
            category="sections",
            description=f"新增章节: {title}",
            severity="low"
        ))
    
    return changes


def compare_scripts(old_scripts: dict, new_scripts: dict) -> list[Change]:
    """比较脚本变化"""
    changes = []
    
    old_paths = set(old_scripts.keys())
    new_paths = set(new_scripts.keys())
    
    removed = old_paths - new_paths
    added = new_paths - old_paths
    common = old_paths & new_paths
    
    # 检查移除的脚本
    for script in removed:
        changes.append(Change(
            change_type=ChangeType.BREAKING,
            category="scripts",
            description=f"移除脚本: {script}",
            severity="high",
            details="依赖此脚本的用法将无法工作"
        ))
    
    # 检查新增的脚本
    for script in added:
        changes.append(Change(
            change_type=ChangeType.ENHANCEMENT,
            category="scripts",
            description=f"新增脚本: {script}",
            severity="low"
        ))
    
    # 检查函数签名变化
    for script in common:
        old_funcs = old_scripts[script].get("functions", {})
        new_funcs = new_scripts[script].get("functions", {})
        
        removed_funcs = set(old_funcs.keys()) - set(new_funcs.keys())
        added_funcs = set(new_funcs.keys()) - set(old_funcs.keys())
        
        for func in removed_funcs:
            changes.append(Change(
                change_type=ChangeType.BREAKING,
                category="api",
                description=f"移除函数 {func}() in {script}",
                severity="high"
            ))
        
        for func in added_funcs:
            changes.append(Change(
                change_type=ChangeType.ENHANCEMENT,
                category="api",
                description=f"新增函数 {func}() in {script}",
                severity="low"
            ))
        
        # 检查参数变化
        common_funcs = set(old_funcs.keys()) & set(new_funcs.keys())
        for func in common_funcs:
            old_params = old_funcs[func]
            new_params = new_funcs[func]
            
            if old_params != new_params:
                # 简单检查：新参数是否是旧参数的超集
                old_param_names = set(re.findall(r'\b\w+\b', old_params.split('=')[0]))
                new_param_names = set(re.findall(r'\b\w+\b', new_params.split('=')[0]))
                
                if not old_param_names.issubset(new_param_names):
                    changes.append(Change(
                        change_type=ChangeType.BREAKING,
                        category="api",
                        description=f"函数 {func}() 签名变更",
                        severity="high",
                        details=f"旧: {old_params} → 新: {new_params}"
                    ))
                else:
                    changes.append(Change(
                        change_type=ChangeType.COMPATIBLE,
                        category="api",
                        description=f"函数 {func}() 参数扩展",
                        severity="low",
                        details=f"新增参数，保持向后兼容"
                    ))
    
    return changes


def check_regression(new_path: str, baseline_path: str) -> RegressionResult:
    """
    执行回归检测
    
    Args:
        new_path: 新版本技能路径
        baseline_path: 基线版本技能路径
        
    Returns:
        RegressionResult 包含变更分类
    """
    new_dir = Path(new_path).resolve()
    baseline_dir = Path(baseline_path).resolve()
    
    all_changes = []
    
    # 验证路径
    for path, name in [(new_dir, "新版本"), (baseline_dir, "基线版本")]:
        if not path.exists():
            return RegressionResult(
                passed=False,
                summary=f"错误: {name}路径不存在: {path}"
            )
        if not (path / "SKILL.md").exists():
            return RegressionResult(
                passed=False,
                summary=f"错误: {name}缺少 SKILL.md"
            )
    
    # 读取 SKILL.md
    try:
        new_content = (new_dir / "SKILL.md").read_text(encoding="utf-8")
        baseline_content = (baseline_dir / "SKILL.md").read_text(encoding="utf-8")
    except Exception as e:
        return RegressionResult(
            passed=False,
            summary=f"读取文件错误: {e}"
        )
    
    # 提取 frontmatter
    new_fm = extract_frontmatter(new_content)
    baseline_fm = extract_frontmatter(baseline_content)
    
    # 1. 比较触发词
    new_triggers = extract_triggers(new_fm.get("description", ""))
    baseline_triggers = extract_triggers(baseline_fm.get("description", ""))
    all_changes.extend(compare_triggers(baseline_triggers, new_triggers))
    
    # 2. 比较章节
    new_sections = extract_sections(new_content)
    baseline_sections = extract_sections(baseline_content)
    all_changes.extend(compare_sections(baseline_sections, new_sections))
    
    # 3. 比较脚本
    new_scripts = extract_scripts(new_dir)
    baseline_scripts = extract_scripts(baseline_dir)
    all_changes.extend(compare_scripts(baseline_scripts, new_scripts))
    
    # 分类变更
    breaking = [c for c in all_changes if c.change_type == ChangeType.BREAKING]
    compatible = [c for c in all_changes if c.change_type == ChangeType.COMPATIBLE]
    enhancements = [c for c in all_changes if c.change_type == ChangeType.ENHANCEMENT]
    
    # 判断是否通过
    passed = len(breaking) == 0
    
    # 生成摘要
    if not all_changes:
        summary = "✅ 无显著变更"
    elif breaking:
        summary = f"❌ 发现 {len(breaking)} 个破坏性变更需要处理"
    else:
        summary = f"✅ 所有变更均向后兼容"
    
    return RegressionResult(
        passed=passed,
        breaking_changes=breaking,
        compatible_changes=compatible,
        enhancements=enhancements,
        summary=summary
    )


def format_report(result: RegressionResult, new_path: str, baseline_path: str) -> str:
    """格式化回归检测报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("回归检测报告")
    lines.append("=" * 60)
    lines.append(f"新版本: {new_path}")
    lines.append(f"基线版本: {baseline_path}")
    lines.append("-" * 60)
    lines.append(f"检测结果: {'✅ 通过' if result.passed else '❌ 不通过'}")
    lines.append(f"摘要: {result.summary}")
    lines.append("-" * 60)
    
    change_icons = {
        ChangeType.BREAKING: "🔴",
        ChangeType.COMPATIBLE: "🟡",
        ChangeType.ENHANCEMENT: "🟢",
        ChangeType.COSMETIC: "⚪",
    }
    
    if result.breaking_changes:
        lines.append("\n🔴 破坏性变更 (需要修复):")
        for change in result.breaking_changes:
            lines.append(f"   [{change.category}] {change.description}")
            if change.details:
                lines.append(f"      📝 {change.details}")
    
    if result.compatible_changes:
        lines.append("\n🟡 兼容性变更 (可接受):")
        for change in result.compatible_changes:
            lines.append(f"   [{change.category}] {change.description}")
    
    if result.enhancements:
        lines.append("\n🟢 增强性变更:")
        for change in result.enhancements:
            lines.append(f"   [{change.category}] {change.description}")
    
    if not any([result.breaking_changes, result.compatible_changes, result.enhancements]):
        lines.append("\n✨ 未检测到显著变更")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="回归检测器 - 对比技能版本变化"
    )
    parser.add_argument("new_skill", help="新版本技能路径")
    parser.add_argument("--baseline", "-b", required=True, help="基线版本技能路径")
    
    args = parser.parse_args()
    
    result = check_regression(args.new_skill, args.baseline)
    print(format_report(result, args.new_skill, args.baseline))
    
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
