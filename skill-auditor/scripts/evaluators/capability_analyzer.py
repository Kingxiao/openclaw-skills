#!/usr/bin/env python3
"""
Skill Auditor - 能力分析器

分析 AI Agent Skills 的功能覆盖范围：
- 触发关键词提取
- 功能列表映射
- 依赖分析
- 使用场景识别
- 工具权限分析

Usage:
    python capability_analyzer.py <skill-path>
    
Returns:
    CapabilityResult with capability mapping and coverage analysis
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CapabilityResult:
    """能力分析结果"""
    skill_name: str
    triggers: list = field(default_factory=list)  # 触发关键词
    capabilities: dict = field(default_factory=dict)  # 能力映射
    dependencies: dict = field(default_factory=dict)  # 依赖分析
    tools: list = field(default_factory=list)  # 工具权限
    complexity_score: float = 0.0  # 复杂度评分
    coverage_estimate: str = ""  # 覆盖度估计


def extract_triggers(description: str, content: str) -> list[str]:
    """从 description 和内容中提取触发关键词"""
    triggers = set()
    
    # 从 description 提取
    # 常见触发词模式
    trigger_patterns = [
        r"(?:use\s+when|when\s+to\s+use|适用于|当|when)[\s:]+(.+?)(?:\.|。|$)",
        r"(?:triggers?|触发)[\s:]+(.+?)(?:\.|。|$)",
    ]
    
    for pattern in trigger_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            # 提取关键词
            words = re.findall(r'\b\w+\b', match)
            triggers.update(w.lower() for w in words if len(w) > 2)
    
    # 从 SKILL.md 的 "When to Use" 章节提取
    when_section = re.search(
        r'(?:when\s+to\s+use|使用场景|usage)[^\n]*\n(.*?)(?=\n##|\n---|\Z)',
        content,
        re.IGNORECASE | re.DOTALL
    )
    if when_section:
        section_text = when_section.group(1)
        # 提取列表项
        items = re.findall(r'[-*]\s*(.+?)(?:\n|$)', section_text)
        for item in items:
            words = re.findall(r'\b\w+\b', item)
            triggers.update(w.lower() for w in words if len(w) > 3)
    
    # 添加技能名称中的关键词
    name_words = description.split()[0:5] if description else []
    triggers.update(w.lower() for w in name_words if len(w) > 3)
    
    # 过滤常见停用词
    stop_words = {
        'this', 'that', 'with', 'from', 'when', 'what', 'where', 'which',
        'should', 'would', 'could', 'will', 'have', 'been', 'being',
        'about', 'using', 'used', 'uses', 'also', 'into', 'than',
        '这个', '那个', '使用', '需要', '可以', '应该', '如果',
    }
    triggers = [t for t in triggers if t not in stop_words]
    
    return sorted(triggers)[:20]  # 返回前20个


def extract_capabilities(content: str) -> dict:
    """提取技能的能力列表"""
    capabilities = {
        "primary": [],
        "secondary": [],
    }
    
    # 从标题中提取主要能力
    headings = re.findall(r'^#+\s+(.+?)$', content, re.MULTILINE)
    
    # 过滤常见的非能力标题
    skip_headings = {
        'overview', 'introduction', 'quick start', 'installation',
        'requirements', 'references', 'related', 'faq', 'troubleshooting',
        '概述', '简介', '快速开始', '安装', '要求', '参考', '相关', '常见问题',
    }
    
    for heading in headings:
        heading_lower = heading.lower().strip()
        if not any(skip in heading_lower for skip in skip_headings):
            if heading_lower.startswith(('step', 'task', '步骤', '任务')):
                capabilities["primary"].append(heading.strip())
            elif ':' in heading or '：' in heading:
                capabilities["secondary"].append(heading.strip())
    
    # 从列表项中提取次要能力
    list_items = re.findall(r'^[-*]\s*\*\*(.+?)\*\*', content, re.MULTILINE)
    capabilities["secondary"].extend(list_items[:10])
    
    return capabilities


def analyze_dependencies(skill_dir: Path, content: str) -> dict:
    """分析技能依赖"""
    dependencies = {
        "scripts": [],
        "references": [],
        "assets": [],
        "external": [],
    }
    
    # 分析 scripts 目录
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.rglob("*.py"):
            rel_path = str(script.relative_to(skill_dir))
            dependencies["scripts"].append(rel_path)
            
            # 分析脚本中的导入
            try:
                script_content = script.read_text(encoding="utf-8")
                imports = re.findall(r'^(?:from|import)\s+(\S+)', script_content, re.MULTILINE)
                for imp in imports:
                    if not imp.startswith('.'):
                        dependencies["external"].append(imp.split('.')[0])
            except:
                pass
    
    # 分析 references 目录
    references_dir = skill_dir / "references"
    if references_dir.exists():
        for ref in references_dir.rglob("*.md"):
            dependencies["references"].append(str(ref.relative_to(skill_dir)))
    
    # 分析 assets 目录
    assets_dir = skill_dir / "assets"
    if assets_dir.exists():
        for asset in assets_dir.rglob("*"):
            if asset.is_file():
                dependencies["assets"].append(str(asset.relative_to(skill_dir)))
    
    # 去重
    dependencies["external"] = list(set(dependencies["external"]))
    
    return dependencies


def extract_tools(content: str) -> list[str]:
    """提取允许的工具列表"""
    tools = []
    
    # 从 frontmatter 中提取 allowed-tools
    allowed_tools_match = re.search(
        r'allowed-tools:\s*\[([^\]]+)\]',
        content,
        re.IGNORECASE
    )
    if allowed_tools_match:
        tools_str = allowed_tools_match.group(1)
        tools = [t.strip().strip('"\'') for t in tools_str.split(',')]
    
    # 从内容中推断可能使用的工具
    tool_patterns = {
        "run_command": [r'```bash', r'```shell', r'subprocess', r'os\.system'],
        "write_to_file": [r'write|save|create.*file', r'open\s*\(\s*["\'].*["\'],\s*["\']w'],
        "view_file": [r'read|load.*file', r'open\s*\(\s*["\']'],
        "browser": [r'browser|click|navigate|url'],
        "search": [r'search|find|grep'],
    }
    
    inferred_tools = []
    for tool, patterns in tool_patterns.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                inferred_tools.append(f"{tool} (推断)")
                break
    
    return tools + inferred_tools


def calculate_complexity(dependencies: dict, capabilities: dict) -> float:
    """计算复杂度评分 (1-10)"""
    score = 1.0
    
    # 脚本数量
    script_count = len(dependencies.get("scripts", []))
    score += min(3, script_count * 0.5)
    
    # 外部依赖数量
    external_count = len(dependencies.get("external", []))
    score += min(2, external_count * 0.3)
    
    # 能力数量
    capability_count = (len(capabilities.get("primary", [])) + 
                       len(capabilities.get("secondary", [])) * 0.5)
    score += min(2, capability_count * 0.2)
    
    # 参考文档数量
    ref_count = len(dependencies.get("references", []))
    score += min(1, ref_count * 0.3)
    
    # 资源文件数量
    asset_count = len(dependencies.get("assets", []))
    score += min(1, asset_count * 0.2)
    
    return min(10, round(score, 1))


def estimate_coverage(triggers: list, capabilities: dict) -> str:
    """估计场景覆盖度"""
    trigger_count = len(triggers)
    capability_count = (len(capabilities.get("primary", [])) + 
                       len(capabilities.get("secondary", [])))
    
    if trigger_count >= 15 and capability_count >= 8:
        return "95%+ (全面覆盖)"
    elif trigger_count >= 10 and capability_count >= 5:
        return "85-95% (高覆盖)"
    elif trigger_count >= 5 and capability_count >= 3:
        return "70-85% (中等覆盖)"
    elif trigger_count >= 2:
        return "50-70% (基础覆盖)"
    else:
        return "<50% (有限覆盖)"


def analyze_capability(skill_path: str) -> CapabilityResult:
    """
    执行完整的能力分析
    
    Args:
        skill_path: 技能目录路径
        
    Returns:
        CapabilityResult 包含能力分析结果
    """
    skill_dir = Path(skill_path).resolve()
    
    if not skill_dir.exists():
        return CapabilityResult(
            skill_name="N/A",
            coverage_estimate="无法分析 - 目录不存在"
        )
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return CapabilityResult(
            skill_name="N/A",
            coverage_estimate="无法分析 - 缺少 SKILL.md"
        )
    
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        return CapabilityResult(
            skill_name="N/A",
            coverage_estimate=f"无法分析 - 读取错误: {e}"
        )
    
    # 提取技能名称
    name_match = re.search(r'^name:\s*(.+?)$', content, re.MULTILINE)
    skill_name = name_match.group(1).strip() if name_match else skill_dir.name
    
    # 提取 description
    desc_match = re.search(r'^description:\s*(.+?)(?=\n[a-z]+:|\n---)', content, re.MULTILINE | re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else ""
    
    # 执行各项分析
    triggers = extract_triggers(description, content)
    capabilities = extract_capabilities(content)
    dependencies = analyze_dependencies(skill_dir, content)
    tools = extract_tools(content)
    complexity = calculate_complexity(dependencies, capabilities)
    coverage = estimate_coverage(triggers, capabilities)
    
    return CapabilityResult(
        skill_name=skill_name,
        triggers=triggers,
        capabilities=capabilities,
        dependencies=dependencies,
        tools=tools,
        complexity_score=complexity,
        coverage_estimate=coverage
    )


def format_report(result: CapabilityResult) -> str:
    """格式化能力分析报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("能力分析报告")
    lines.append("=" * 60)
    lines.append(f"技能名称: {result.skill_name}")
    lines.append(f"复杂度评分: {result.complexity_score}/10")
    lines.append(f"场景覆盖: {result.coverage_estimate}")
    lines.append("-" * 60)
    
    # 触发关键词
    lines.append("\n📌 触发关键词:")
    if result.triggers:
        lines.append(f"   {', '.join(result.triggers)}")
    else:
        lines.append("   (未识别)")
    
    # 能力映射
    lines.append("\n🎯 能力映射:")
    if result.capabilities.get("primary"):
        lines.append("   主要能力:")
        for cap in result.capabilities["primary"][:5]:
            lines.append(f"     • {cap}")
    if result.capabilities.get("secondary"):
        lines.append("   次要能力:")
        for cap in result.capabilities["secondary"][:5]:
            lines.append(f"     • {cap}")
    
    # 依赖分析
    lines.append("\n📦 依赖分析:")
    for dep_type, deps in result.dependencies.items():
        if deps:
            lines.append(f"   {dep_type}: {len(deps)} 个")
            for dep in deps[:3]:
                lines.append(f"     • {dep}")
            if len(deps) > 3:
                lines.append(f"     ... 还有 {len(deps)-3} 个")
    
    # 工具权限
    lines.append("\n🔧 工具权限:")
    if result.tools:
        for tool in result.tools:
            lines.append(f"   • {tool}")
    else:
        lines.append("   (未指定)")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python capability_analyzer.py <skill-path>")
        print("\nExample:")
        print("  python capability_analyzer.py ./my-skill")
        sys.exit(1)
    
    skill_path = sys.argv[1]
    result = analyze_capability(skill_path)
    print(format_report(result))


if __name__ == "__main__":
    main()
