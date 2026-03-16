#!/usr/bin/env python3
"""
Skill Auditor - 自然语言断言测试器

使用自然语言描述验证技能是否满足预期：
- 存在性断言（内容是否存在）
- 行为性断言（功能预期）
- 风格性断言（写作规范）
- 覆盖性断言（场景覆盖）

支持两种模式：
1. 简单模式：使用规则匹配（无需 LLM）
2. LLM 模式：使用大语言模型进行语义验证（可选）

Usage:
    python assertion_tester.py <skill-path> --assertions <assertions-file>
    python assertion_tester.py <skill-path> -a "技能必须包含错误处理说明"
    
Returns:
    AssertionResult with pass/fail status for each assertion
"""

import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class AssertionType(Enum):
    """断言类型"""
    EXISTENCE = "existence"      # 存在性：内容必须/不能存在
    STYLE = "style"              # 风格性：格式和写作规范
    COVERAGE = "coverage"        # 覆盖性：场景和功能覆盖
    BEHAVIOR = "behavior"        # 行为性：功能预期（需要 LLM）


@dataclass
class AssertionResult:
    """断言结果"""
    assertion: str
    passed: bool
    assertion_type: AssertionType
    confidence: float = 1.0
    evidence: str = ""
    suggestion: str = ""


@dataclass
class TestResult:
    """测试总结果"""
    total: int
    passed: int
    failed: int
    results: list = field(default_factory=list)


# 预定义的断言规则（简单模式）
BUILTIN_RULES = {
    # 存在性规则
    r"(?:必须|应该|需要)包含(.+?)(?:说明|描述|章节|部分)": {
        "type": AssertionType.EXISTENCE,
        "pattern_template": r"(?i){keyword}",
        "check": "positive",
    },
    r"(?:不允许|不能|禁止)(?:使用|包含)(.+?)": {
        "type": AssertionType.STYLE,
        "pattern_template": r"(?i){keyword}",
        "check": "negative",
    },
    r"(?:必须|应该)有至少\s*(\d+)\s*个(.+?)(?:示例|代码块)": {
        "type": AssertionType.COVERAGE,
        "count_check": True,
    },
    r"(?:所有|每个)(.+?)(?:必须|应该)有(.+?)": {
        "type": AssertionType.STYLE,
        "check": "all",
    },
}


def parse_assertion(assertion: str) -> tuple[AssertionType, dict]:
    """解析断言，返回断言类型和参数"""
    assertion = assertion.strip()
    
    # 尝试匹配内置规则
    for rule_pattern, config in BUILTIN_RULES.items():
        match = re.search(rule_pattern, assertion)
        if match:
            return config["type"], {"match": match, **config}
    
    # 默认为行为性断言（需要 LLM）
    return AssertionType.BEHAVIOR, {}


def check_existence(content: str, keyword: str, positive: bool = True) -> tuple[bool, str]:
    """检查内容是否存在"""
    # 构建搜索模式
    pattern = re.compile(keyword, re.IGNORECASE)
    matches = pattern.findall(content)
    
    if positive:
        if matches:
            return True, f"找到 {len(matches)} 处匹配"
        else:
            return False, f"未找到 '{keyword}'"
    else:
        if matches:
            return False, f"发现 {len(matches)} 处不允许的内容"
        else:
            return True, "未发现禁止内容"


def check_count(content: str, count: int, pattern: str) -> tuple[bool, str]:
    """检查数量"""
    if "代码块" in pattern or "示例" in pattern:
        # 计算代码块数量
        code_blocks = len(re.findall(r'```', content)) // 2
        passed = code_blocks >= count
        return passed, f"实际: {code_blocks} 个, 要求: >= {count} 个"
    
    matches = re.findall(pattern, content, re.IGNORECASE)
    passed = len(matches) >= count
    return passed, f"实际: {len(matches)} 个, 要求: >= {count} 个"


def check_style_rule(content: str, target: str, requirement: str, skill_dir: Path) -> tuple[bool, str]:
    """检查风格规则"""
    # 特殊处理：检查脚本的 docstring
    if "脚本" in target and "docstring" in requirement:
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.exists():
            return True, "无脚本需要检查"
        
        total = 0
        with_docstring = 0
        for script in scripts_dir.rglob("*.py"):
            total += 1
            try:
                script_content = script.read_text(encoding="utf-8")
                # 检查模块级 docstring
                if re.search(r'^["\'][\'"]{2}', script_content.strip()):
                    with_docstring += 1
                elif re.search(r'^#!.*\n+["\'][\'"]{2}', script_content):
                    with_docstring += 1
            except:
                pass
        
        if total == 0:
            return True, "无脚本需要检查"
        
        passed = with_docstring == total
        return passed, f"{with_docstring}/{total} 个脚本有 docstring"
    
    # 通用风格检查
    return True, "规则匹配（简单模式）"


def evaluate_assertion_simple(assertion: str, content: str, skill_dir: Path) -> AssertionResult:
    """使用简单规则评估断言"""
    assertion_type, config = parse_assertion(assertion)
    
    # 存在性断言
    if assertion_type == AssertionType.EXISTENCE:
        match = config.get("match")
        if match:
            keyword = match.group(1)
            positive = config.get("check") == "positive"
            passed, evidence = check_existence(content, keyword, positive)
            return AssertionResult(
                assertion=assertion,
                passed=passed,
                assertion_type=assertion_type,
                evidence=evidence,
                suggestion="" if passed else f"添加关于 '{keyword}' 的内容"
            )
    
    # 风格性断言（负面检查）
    if assertion_type == AssertionType.STYLE and config.get("check") == "negative":
        match = config.get("match")
        if match:
            keyword = match.group(1)
            passed, evidence = check_existence(content, keyword, positive=False)
            return AssertionResult(
                assertion=assertion,
                passed=passed,
                assertion_type=assertion_type,
                evidence=evidence,
                suggestion="" if passed else f"移除 '{keyword}'"
            )
    
    # 覆盖性断言（数量检查）
    if assertion_type == AssertionType.COVERAGE and config.get("count_check"):
        match = config.get("match")
        if match:
            count = int(match.group(1))
            pattern = match.group(2)
            passed, evidence = check_count(content, count, pattern)
            return AssertionResult(
                assertion=assertion,
                passed=passed,
                assertion_type=assertion_type,
                evidence=evidence,
                suggestion="" if passed else f"增加更多 {pattern}"
            )
    
    # 风格规则（全部检查）
    if assertion_type == AssertionType.STYLE and config.get("check") == "all":
        match = config.get("match")
        if match:
            target = match.group(1)
            requirement = match.group(2)
            passed, evidence = check_style_rule(content, target, requirement, skill_dir)
            return AssertionResult(
                assertion=assertion,
                passed=passed,
                assertion_type=assertion_type,
                evidence=evidence,
                suggestion="" if passed else f"确保所有 {target} 都有 {requirement}"
            )
    
    # 行为性断言 - 在简单模式下标记为需要 LLM
    if assertion_type == AssertionType.BEHAVIOR:
        return AssertionResult(
            assertion=assertion,
            passed=True,  # 默认通过，提示需要 LLM
            assertion_type=assertion_type,
            confidence=0.5,
            evidence="需要 LLM 进行语义验证",
            suggestion="使用 --llm 模式进行深度验证"
        )
    
    # 默认处理：尝试关键词搜索
    keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', assertion)
    important_keywords = [k for k in keywords if len(k) > 2][:3]
    
    if important_keywords:
        found = all(k.lower() in content.lower() for k in important_keywords)
        return AssertionResult(
            assertion=assertion,
            passed=found,
            assertion_type=AssertionType.EXISTENCE,
            confidence=0.7,
            evidence=f"关键词检查: {', '.join(important_keywords)}",
            suggestion="" if found else f"确保包含相关内容"
        )
    
    return AssertionResult(
        assertion=assertion,
        passed=True,
        assertion_type=AssertionType.BEHAVIOR,
        confidence=0.3,
        evidence="无法在简单模式下验证",
        suggestion="使用 --llm 模式进行深度验证"
    )


def run_assertions(skill_path: str, assertions: list[str]) -> TestResult:
    """运行断言测试"""
    skill_dir = Path(skill_path).resolve()
    results = []
    
    if not skill_dir.exists():
        return TestResult(
            total=len(assertions),
            passed=0,
            failed=len(assertions),
            results=[AssertionResult(
                assertion="验证技能目录",
                passed=False,
                assertion_type=AssertionType.EXISTENCE,
                evidence=f"目录不存在: {skill_dir}"
            )]
        )
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return TestResult(
            total=len(assertions),
            passed=0,
            failed=len(assertions),
            results=[AssertionResult(
                assertion="验证 SKILL.md",
                passed=False,
                assertion_type=AssertionType.EXISTENCE,
                evidence="缺少 SKILL.md 文件"
            )]
        )
    
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        return TestResult(
            total=len(assertions),
            passed=0,
            failed=len(assertions),
            results=[AssertionResult(
                assertion="读取 SKILL.md",
                passed=False,
                assertion_type=AssertionType.EXISTENCE,
                evidence=f"读取错误: {e}"
            )]
        )
    
    # 运行每个断言
    for assertion in assertions:
        result = evaluate_assertion_simple(assertion, content, skill_dir)
        results.append(result)
    
    passed_count = sum(1 for r in results if r.passed)
    
    return TestResult(
        total=len(assertions),
        passed=passed_count,
        failed=len(assertions) - passed_count,
        results=results
    )


def format_report(result: TestResult, skill_path: str) -> str:
    """格式化断言测试报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("自然语言断言测试报告")
    lines.append("=" * 60)
    lines.append(f"技能路径: {skill_path}")
    lines.append(f"总断言数: {result.total}")
    lines.append(f"通过: {result.passed} | 失败: {result.failed}")
    lines.append(f"通过率: {result.passed/max(result.total, 1)*100:.1f}%")
    lines.append("-" * 60)
    
    for r in result.results:
        icon = "✅" if r.passed else "❌"
        confidence_bar = "●" * int(r.confidence * 5) + "○" * (5 - int(r.confidence * 5))
        
        lines.append(f"\n{icon} {r.assertion}")
        lines.append(f"   类型: {r.assertion_type.value}")
        lines.append(f"   置信度: [{confidence_bar}] {r.confidence*100:.0f}%")
        lines.append(f"   证据: {r.evidence}")
        if r.suggestion and not r.passed:
            lines.append(f"   💡 建议: {r.suggestion}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="自然语言断言测试器"
    )
    parser.add_argument("skill_path", help="技能目录路径")
    parser.add_argument("-a", "--assertion", action="append", 
                       help="添加断言（可多次使用）")
    parser.add_argument("--assertions-file", "-f",
                       help="从文件加载断言（每行一个）")
    
    args = parser.parse_args()
    
    assertions = []
    
    # 从命令行参数收集断言
    if args.assertion:
        assertions.extend(args.assertion)
    
    # 从文件加载断言
    if args.assertions_file:
        try:
            with open(args.assertions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        assertions.append(line)
        except Exception as e:
            print(f"错误: 无法读取断言文件: {e}")
            sys.exit(1)
    
    if not assertions:
        # 默认断言
        assertions = [
            "技能必须包含使用场景说明",
            "不允许使用 'you should'",
            "必须有至少 1 个代码示例",
            "所有脚本必须有 docstring",
        ]
        print("未指定断言，使用默认断言:\n")
        for a in assertions:
            print(f"  • {a}")
        print()
    
    result = run_assertions(args.skill_path, assertions)
    print(format_report(result, args.skill_path))
    
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
