#!/usr/bin/env python3
"""
Skill Auditor - 技能格式/结构验证器

验证 AI Agent Skills 是否符合规范结构，包括：
- SKILL.md 存在性检查
- YAML frontmatter 格式验证
- name/description 字段验证
- 目录结构合规性检查
- 引用文件存在性检查

Usage:
    python format_validator.py <skill-path>
    
Returns:
    ValidationResult with passed status and list of issues
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Severity(Enum):
    """问题严重性等级"""
    CRITICAL = "CRITICAL"  # 必须修复，否则技能不可用
    ERROR = "ERROR"        # 必须修复，影响功能
    WARNING = "WARNING"    # 建议修复，影响质量
    INFO = "INFO"          # 信息提示


@dataclass
class Issue:
    """验证问题"""
    severity: Severity
    code: str
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    score: float  # 0-100
    issues: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def parse_frontmatter(content: str) -> tuple[Optional[dict], Optional[str]]:
    """
    解析 YAML frontmatter
    
    Returns:
        (frontmatter_dict, error_message)
    """
    if not content.startswith("---"):
        return None, "SKILL.md 必须以 YAML frontmatter 开头 (---)"
    
    # 查找 frontmatter 结束位置
    second_delimiter = content.find("---", 3)
    if second_delimiter == -1:
        return None, "YAML frontmatter 未正确关闭"
    
    frontmatter_text = content[3:second_delimiter].strip()
    
    # 简单的 YAML 解析（避免依赖 PyYAML）
    frontmatter = {}
    current_key = None
    current_value_lines = []
    
    for line in frontmatter_text.split("\n"):
        # 检查是否是新的键值对
        match = re.match(r'^([a-z_-]+):\s*(.*)$', line, re.IGNORECASE)
        if match:
            # 保存之前的键值对
            if current_key:
                frontmatter[current_key] = "\n".join(current_value_lines).strip()
            
            current_key = match.group(1).lower()
            value = match.group(2).strip()
            current_value_lines = [value] if value else []
        elif current_key and line.strip():
            # 多行值的续行
            current_value_lines.append(line.strip())
    
    # 保存最后一个键值对
    if current_key:
        frontmatter[current_key] = "\n".join(current_value_lines).strip()
    
    return frontmatter, None


def validate_name(name: str, skill_dir: Path) -> list[Issue]:
    """验证 name 字段"""
    issues = []
    
    if not name:
        issues.append(Issue(
            severity=Severity.CRITICAL,
            code="FM001",
            message="缺少必需字段: name",
            suggestion="在 frontmatter 中添加 name 字段"
        ))
        return issues
    
    # 检查格式：小写连字符
    if not re.match(r'^[a-z0-9-]+$', name):
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM002",
            message=f"name 格式错误: '{name}' (应为小写字母、数字、连字符)",
            suggestion="使用 kebab-case 格式，如 'my-skill-name'"
        ))
    
    # 检查连字符规则
    if name.startswith('-') or name.endswith('-'):
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM003",
            message=f"name '{name}' 不能以连字符开头或结尾"
        ))
    
    if '--' in name:
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM004",
            message=f"name '{name}' 不能包含连续连字符"
        ))
    
    # 检查长度
    if len(name) > 64:
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM005",
            message=f"name 过长 ({len(name)} 字符)，最大 64 字符"
        ))
    
    # 检查与目录名一致性
    if name != skill_dir.name:
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM006",
            message=f"name '{name}' 与目录名 '{skill_dir.name}' 不一致",
            suggestion="确保 name 字段与技能目录名完全一致"
        ))
    
    return issues


def validate_description(description: str) -> list[Issue]:
    """验证 description 字段"""
    issues = []
    
    if not description:
        issues.append(Issue(
            severity=Severity.CRITICAL,
            code="FM010",
            message="缺少必需字段: description",
            suggestion="在 frontmatter 中添加 description 字段"
        ))
        return issues
    
    # 检查长度
    if len(description) < 20:
        issues.append(Issue(
            severity=Severity.WARNING,
            code="FM011",
            message=f"description 过短 ({len(description)} 字符)，建议至少 50 字符",
            suggestion="添加更多描述信息，包括使用场景和触发关键词"
        ))
    
    if len(description) > 1024:
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM012",
            message=f"description 过长 ({len(description)} 字符)，最大 1024 字符"
        ))
    
    # 检查是否包含使用场景
    use_keywords = ["when", "use", "适用", "场景", "when to", "使用"]
    has_use_case = any(kw.lower() in description.lower() for kw in use_keywords)
    if not has_use_case:
        issues.append(Issue(
            severity=Severity.INFO,
            code="FM013",
            message="description 中建议包含使用场景描述",
            suggestion="添加 'Use when...' 或 '当...时使用' 的说明"
        ))
    
    # 检查禁止字符
    if '<' in description or '>' in description:
        issues.append(Issue(
            severity=Severity.ERROR,
            code="FM014",
            message="description 不能包含尖括号 (< 或 >)"
        ))
    
    return issues


def validate_structure(skill_dir: Path, content: str) -> list[Issue]:
    """验证目录结构和引用"""
    issues = []
    
    # 检查 SKILL.md 行数
    lines = content.split("\n")
    if len(lines) > 500:
        issues.append(Issue(
            severity=Severity.WARNING,
            code="ST001",
            message=f"SKILL.md 行数过多 ({len(lines)} 行)，建议 < 500 行",
            location="SKILL.md",
            suggestion="将详细内容移至 references/ 目录"
        ))
    elif len(lines) > 400:
        issues.append(Issue(
            severity=Severity.INFO,
            code="ST002",
            message=f"SKILL.md 行数 ({len(lines)}) 接近上限",
            location="SKILL.md"
        ))
    
    # 检查目录结构
    expected_dirs = ["scripts", "references", "assets"]
    for dir_name in expected_dirs:
        dir_path = skill_dir / dir_name
        if dir_path.exists() and not dir_path.is_dir():
            issues.append(Issue(
                severity=Severity.ERROR,
                code="ST003",
                message=f"'{dir_name}' 应该是目录而非文件",
                location=str(dir_path)
            ))
    
    # 检查引用的文件是否存在
    # 匹配 Markdown 链接: [text](./path) 或 [text](path)
    link_patterns = [
        r'\[.+?\]\(\./(.+?)\)',      # [text](./path)
        r'\[.+?\]\((?!http)(?!#)(.+?\.(?:md|py|sh|json))\)',  # [text](path.ext)
    ]
    
    for pattern in link_patterns:
        for match in re.finditer(pattern, content):
            ref_path = skill_dir / match.group(1)
            if not ref_path.exists():
                issues.append(Issue(
                    severity=Severity.ERROR,
                    code="ST004",
                    message=f"引用文件不存在: {match.group(1)}",
                    location="SKILL.md",
                    suggestion="创建该文件或修正链接路径"
                ))
    
    return issues


def validate_scripts(skill_dir: Path) -> list[Issue]:
    """验证脚本规范"""
    issues = []
    scripts_dir = skill_dir / "scripts"
    
    if not scripts_dir.exists():
        return issues
    
    for script in scripts_dir.rglob("*.py"):
        try:
            script_content = script.read_text(encoding="utf-8")
        except Exception as e:
            issues.append(Issue(
                severity=Severity.ERROR,
                code="SC001",
                message=f"无法读取脚本: {e}",
                location=str(script.relative_to(skill_dir))
            ))
            continue
        
        rel_path = str(script.relative_to(skill_dir))
        
        # 检查入口点
        if "if __name__" not in script_content:
            issues.append(Issue(
                severity=Severity.WARNING,
                code="SC002",
                message="脚本缺少入口点 (if __name__ == '__main__')",
                location=rel_path,
                suggestion="添加 if __name__ == '__main__': main() 入口"
            ))
        
        # 检查 docstring
        if not script_content.strip().startswith('"""') and not script_content.strip().startswith("'''"):
            # 检查是否在 shebang 后有 docstring
            lines = script_content.split('\n')
            has_docstring = False
            for i, line in enumerate(lines):
                if line.strip().startswith('#!'):
                    continue
                if line.strip().startswith('"""') or line.strip().startswith("'''"):
                    has_docstring = True
                    break
                elif line.strip() and not line.strip().startswith('#'):
                    break
            
            if not has_docstring:
                issues.append(Issue(
                    severity=Severity.INFO,
                    code="SC003",
                    message="脚本缺少模块级 docstring",
                    location=rel_path,
                    suggestion="在文件开头添加描述脚本用途的 docstring"
                ))
    
    return issues


def validate_skill(skill_path: str) -> ValidationResult:
    """
    执行完整的格式/结构验证
    
    Args:
        skill_path: 技能目录路径
        
    Returns:
        ValidationResult 包含验证结果
    """
    skill_dir = Path(skill_path).resolve()
    issues = []
    
    # 1. 检查目录存在
    if not skill_dir.exists():
        return ValidationResult(
            passed=False,
            score=0,
            issues=[Issue(
                severity=Severity.CRITICAL,
                code="DIR001",
                message=f"目录不存在: {skill_dir}"
            )]
        )
    
    if not skill_dir.is_dir():
        return ValidationResult(
            passed=False,
            score=0,
            issues=[Issue(
                severity=Severity.CRITICAL,
                code="DIR002",
                message=f"不是目录: {skill_dir}"
            )]
        )
    
    # 2. 检查 SKILL.md 存在
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return ValidationResult(
            passed=False,
            score=0,
            issues=[Issue(
                severity=Severity.CRITICAL,
                code="FILE001",
                message="缺少必需文件: SKILL.md"
            )]
        )
    
    # 3. 读取并解析 SKILL.md
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        return ValidationResult(
            passed=False,
            score=0,
            issues=[Issue(
                severity=Severity.CRITICAL,
                code="FILE002",
                message=f"无法读取 SKILL.md: {e}"
            )]
        )
    
    # 4. 解析 frontmatter
    frontmatter, fm_error = parse_frontmatter(content)
    if fm_error:
        issues.append(Issue(
            severity=Severity.CRITICAL,
            code="FM000",
            message=fm_error
        ))
    else:
        # 5. 验证 name
        name = frontmatter.get("name", "")
        issues.extend(validate_name(name, skill_dir))
        
        # 6. 验证 description
        description = frontmatter.get("description", "")
        issues.extend(validate_description(description))
    
    # 7. 验证结构
    issues.extend(validate_structure(skill_dir, content))
    
    # 8. 验证脚本
    issues.extend(validate_scripts(skill_dir))
    
    # 计算得分
    critical_count = sum(1 for i in issues if i.severity == Severity.CRITICAL)
    error_count = sum(1 for i in issues if i.severity == Severity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)
    
    # 评分规则: CRITICAL=-25, ERROR=-10, WARNING=-3
    score = max(0, 100 - critical_count * 25 - error_count * 10 - warning_count * 3)
    passed = critical_count == 0 and error_count == 0
    
    return ValidationResult(
        passed=passed,
        score=score,
        issues=issues,
        metadata={
            "skill_name": frontmatter.get("name", "") if frontmatter else "",
            "skill_path": str(skill_dir),
            "line_count": len(content.split("\n")),
        }
    )


def format_report(result: ValidationResult) -> str:
    """格式化验证报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("格式/结构验证报告")
    lines.append("=" * 60)
    lines.append(f"技能路径: {result.metadata.get('skill_path', 'N/A')}")
    lines.append(f"技能名称: {result.metadata.get('skill_name', 'N/A')}")
    lines.append(f"SKILL.md 行数: {result.metadata.get('line_count', 'N/A')}")
    lines.append("-" * 60)
    lines.append(f"验证结果: {'✅ 通过' if result.passed else '❌ 不通过'}")
    lines.append(f"格式得分: {result.score:.1f}/100")
    lines.append("-" * 60)
    
    if result.issues:
        lines.append("发现问题:")
        for issue in result.issues:
            icon = {
                Severity.CRITICAL: "🔴",
                Severity.ERROR: "🟠",
                Severity.WARNING: "🟡",
                Severity.INFO: "🔵",
            }.get(issue.severity, "⚪")
            
            loc = f" [{issue.location}]" if issue.location else ""
            lines.append(f"  {icon} [{issue.code}] {issue.severity.value}: {issue.message}{loc}")
            if issue.suggestion:
                lines.append(f"     💡 建议: {issue.suggestion}")
    else:
        lines.append("✨ 未发现问题")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python format_validator.py <skill-path>")
        print("\nExample:")
        print("  python format_validator.py ./my-skill")
        sys.exit(1)
    
    skill_path = sys.argv[1]
    result = validate_skill(skill_path)
    print(format_report(result))
    
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
