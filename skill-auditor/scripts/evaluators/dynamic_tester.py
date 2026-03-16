#!/usr/bin/env python3
"""
LLM 动态测试器 (dynamic_tester.py)

运行时由 LLM 动态生成测试用例，验证技能的实际执行效果。

核心能力:
1. 根据 SKILL.md 分析技能功能
2. 使用 LLM 动态生成测试用例
3. 模拟执行测试并验证结果
4. 生成测试报告和通过率

用法:
    python dynamic_tester.py /path/to/skill
    python dynamic_tester.py /path/to/skill --num-tests 5
    python dynamic_tester.py /path/to/skill --json
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import urllib.request
import urllib.error

# LLM API 配置（通过环境变量注入，不硬编码）
API_BASE_URL = os.environ.get("LLM_API_BASE_URL", "https://api.302.ai/v1/chat/completions")
API_KEY = os.environ.get("API_302_KEY", "")
MODEL_NAME = os.environ.get("API_302_MODEL", "qwen-plus")

SCRIPT_DIR = Path(__file__).parent


@dataclass
class TestCase:
    """测试用例"""
    name: str
    description: str
    user_input: str
    expected_behavior: str
    test_type: str = "functional"  # functional, edge_case, error_handling


@dataclass
class TestResult:
    """测试结果"""
    test_case: TestCase
    passed: bool
    actual_behavior: str
    reasoning: str
    score: float = 0.0  # 0-100


@dataclass
class DynamicTestReport:
    """动态测试报告"""
    skill_name: str
    skill_path: str
    test_time: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float
    overall_score: float
    test_results: List[TestResult]
    summary: str
    recommendations: List[str] = field(default_factory=list)


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> Optional[str]:
    """调用 LLM API"""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(API_BASE_URL, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        return None


def read_skill_content(skill_path: Path) -> str:
    """读取技能内容"""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return ""
    
    content = skill_md.read_text(encoding="utf-8")
    # 限制长度，保留关键部分
    if len(content) > 8000:
        # 保留前 4000 和后 2000 字符
        content = content[:4000] + "\n...[中间内容省略]...\n" + content[-2000:]
    
    return content


def generate_test_cases(skill_path: Path, num_tests: int = 5) -> List[TestCase]:
    """使用 LLM 生成测试用例"""
    skill_content = read_skill_content(skill_path)
    if not skill_content:
        print(f"❌ 无法读取技能内容")
        return []
    
    system_prompt = """你是一个技能测试专家。根据给定的技能文档，生成测试用例来验证技能的功能。

生成的测试用例应该覆盖：
1. **核心功能测试**: 验证技能的主要功能
2. **边界情况测试**: 测试极端或边界输入
3. **错误处理测试**: 验证技能如何处理无效输入

返回 JSON 数组格式：
[
  {
    "name": "测试用例名称",
    "description": "测试目的说明",
    "user_input": "模拟用户输入或触发场景",
    "expected_behavior": "预期的技能行为或输出",
    "test_type": "functional|edge_case|error_handling"
  }
]

只返回 JSON 数组，不要其他内容。确保测试用例具体、可验证。"""

    user_prompt = f"""请为以下技能生成 {num_tests} 个测试用例：

技能文档：
{skill_content}

要求：
1. 至少包含 1 个边界情况测试
2. 至少包含 1 个错误处理测试
3. 其余为核心功能测试
4. 测试用例应该具体且可验证"""

    result = call_llm(system_prompt, user_prompt, 2000)
    if not result:
        return []
    
    try:
        # 清理 markdown 格式
        result = re.sub(r'^```json\s*', '', result)
        result = re.sub(r'\s*```$', '', result)
        tests_data = json.loads(result.strip())
        
        test_cases = []
        for t in tests_data:
            test_cases.append(TestCase(
                name=t.get("name", "未命名测试"),
                description=t.get("description", ""),
                user_input=t.get("user_input", ""),
                expected_behavior=t.get("expected_behavior", ""),
                test_type=t.get("test_type", "functional")
            ))
        return test_cases
        
    except json.JSONDecodeError as e:
        print(f"⚠️ 解析测试用例失败: {e}")
        return []


def execute_test(skill_path: Path, test_case: TestCase) -> TestResult:
    """模拟执行测试并验证结果"""
    skill_content = read_skill_content(skill_path)
    
    # 使用 LLM 模拟执行并评估
    system_prompt = """你是一个技能测试评估专家。根据技能文档和测试用例，模拟执行测试并评估结果。

你需要：
1. 根据技能文档理解技能的能力和限制
2. 模拟用户输入时技能的行为
3. 判断实际行为是否符合预期
4. 给出评分和理由

返回 JSON 格式：
{
  "passed": true/false,
  "actual_behavior": "技能的实际/模拟行为描述",
  "reasoning": "评估理由",
  "score": 0-100
}

评分标准：
- 100: 完全符合预期
- 80-99: 基本符合，有小问题
- 60-79: 部分符合
- 0-59: 不符合预期

只返回 JSON。"""

    user_prompt = f"""测试用例：
- 名称: {test_case.name}
- 类型: {test_case.test_type}
- 用户输入: {test_case.user_input}
- 预期行为: {test_case.expected_behavior}

技能文档摘要：
{skill_content[:3000]}

请模拟执行此测试并评估结果。"""

    result = call_llm(system_prompt, user_prompt, 800)
    
    if not result:
        return TestResult(
            test_case=test_case,
            passed=False,
            actual_behavior="LLM 评估失败",
            reasoning="无法获取 LLM 响应",
            score=0
        )
    
    try:
        result = re.sub(r'^```json\s*', '', result)
        result = re.sub(r'\s*```$', '', result)
        eval_data = json.loads(result.strip())
        
        return TestResult(
            test_case=test_case,
            passed=eval_data.get("passed", False),
            actual_behavior=eval_data.get("actual_behavior", ""),
            reasoning=eval_data.get("reasoning", ""),
            score=eval_data.get("score", 0)
        )
    except json.JSONDecodeError:
        return TestResult(
            test_case=test_case,
            passed=False,
            actual_behavior="解析评估结果失败",
            reasoning=result[:200],
            score=0
        )


def run_dynamic_tests(skill_path: Path, num_tests: int = 5) -> DynamicTestReport:
    """运行完整动态测试流程"""
    skill_name = skill_path.name
    
    print(f"🧪 正在为 {skill_name} 生成测试用例...")
    test_cases = generate_test_cases(skill_path, num_tests)
    
    if not test_cases:
        return DynamicTestReport(
            skill_name=skill_name,
            skill_path=str(skill_path),
            test_time=datetime.now().isoformat(),
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            pass_rate=0,
            overall_score=0,
            test_results=[],
            summary="无法生成测试用例",
            recommendations=["检查技能文档是否完整"]
        )
    
    print(f"✅ 生成了 {len(test_cases)} 个测试用例")
    
    # 执行测试
    test_results = []
    for i, tc in enumerate(test_cases, 1):
        print(f"   [{i}/{len(test_cases)}] 执行: {tc.name}...")
        result = execute_test(skill_path, tc)
        test_results.append(result)
        status = "✅" if result.passed else "❌"
        print(f"   {status} {tc.name}: {result.score:.0f}分")
    
    # 计算统计
    passed_tests = sum(1 for r in test_results if r.passed)
    failed_tests = len(test_results) - passed_tests
    pass_rate = passed_tests / len(test_results) * 100 if test_results else 0
    overall_score = sum(r.score for r in test_results) / len(test_results) if test_results else 0
    
    # 生成建议
    recommendations = []
    failed_cases = [r for r in test_results if not r.passed]
    
    if failed_cases:
        recommendations.append(f"共 {len(failed_cases)} 个测试未通过，需要检查相关功能")
        
        # 按类型分组
        edge_failures = [r for r in failed_cases if r.test_case.test_type == "edge_case"]
        error_failures = [r for r in failed_cases if r.test_case.test_type == "error_handling"]
        
        if edge_failures:
            recommendations.append("边界情况处理需要加强")
        if error_failures:
            recommendations.append("错误处理机制需要完善")
    
    # 生成摘要
    if pass_rate >= 80:
        summary = f"✅ 测试通过 - 通过率 {pass_rate:.0f}%，综合得分 {overall_score:.1f}/100"
    elif pass_rate >= 60:
        summary = f"⚠️ 测试部分通过 - 通过率 {pass_rate:.0f}%，需要改进"
    else:
        summary = f"❌ 测试未通过 - 通过率 {pass_rate:.0f}%，需要重大改进"
    
    return DynamicTestReport(
        skill_name=skill_name,
        skill_path=str(skill_path),
        test_time=datetime.now().isoformat(),
        total_tests=len(test_results),
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        pass_rate=pass_rate,
        overall_score=overall_score,
        test_results=test_results,
        summary=summary,
        recommendations=recommendations
    )


def format_console_report(report: DynamicTestReport) -> str:
    """格式化控制台报告"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"🧪 动态测试报告: {report.skill_name}")
    lines.append("=" * 60)
    lines.append(f"测试时间: {report.test_time}")
    lines.append(f"技能路径: {report.skill_path}")
    lines.append("-" * 60)
    lines.append(f"总测试数: {report.total_tests}")
    lines.append(f"通过: {report.passed_tests} | 失败: {report.failed_tests}")
    lines.append(f"通过率: {report.pass_rate:.1f}%")
    lines.append(f"综合得分: {report.overall_score:.1f}/100")
    lines.append(f"\n{report.summary}")
    lines.append("-" * 60)
    
    # 测试详情
    lines.append("\n📋 测试详情:")
    for i, result in enumerate(report.test_results, 1):
        status = "✅" if result.passed else "❌"
        lines.append(f"\n  {i}. {status} {result.test_case.name}")
        lines.append(f"     类型: {result.test_case.test_type}")
        lines.append(f"     得分: {result.score:.0f}/100")
        if not result.passed:
            lines.append(f"     原因: {result.reasoning[:100]}...")
    
    # 建议
    if report.recommendations:
        lines.append("\n💡 改进建议:")
        for rec in report.recommendations:
            lines.append(f"  • {rec}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def to_dict(report: DynamicTestReport) -> Dict[str, Any]:
    """转换为字典"""
    return {
        "skill_name": report.skill_name,
        "skill_path": report.skill_path,
        "test_time": report.test_time,
        "total_tests": report.total_tests,
        "passed_tests": report.passed_tests,
        "failed_tests": report.failed_tests,
        "pass_rate": report.pass_rate,
        "overall_score": report.overall_score,
        "summary": report.summary,
        "recommendations": report.recommendations,
        "test_results": [
            {
                "name": r.test_case.name,
                "type": r.test_case.test_type,
                "user_input": r.test_case.user_input,
                "expected_behavior": r.test_case.expected_behavior,
                "passed": r.passed,
                "actual_behavior": r.actual_behavior,
                "reasoning": r.reasoning,
                "score": r.score
            }
            for r in report.test_results
        ]
    }


def main():
    parser = argparse.ArgumentParser(
        description="LLM 动态测试器 - 运行时生成并执行测试用例"
    )
    parser.add_argument("skill_path", help="技能目录路径")
    parser.add_argument("--num-tests", "-n", type=int, default=5, help="生成测试用例数量 (默认: 5)")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--output", "-o", help="输出报告文件路径")
    
    args = parser.parse_args()
    
    skill_path = Path(args.skill_path).expanduser().resolve()
    
    if not skill_path.exists():
        print(f"❌ 目录不存在: {skill_path}")
        sys.exit(1)
    
    if not (skill_path / "SKILL.md").exists():
        print(f"❌ 未找到 SKILL.md: {skill_path}")
        sys.exit(1)
    
    # 运行测试
    report = run_dynamic_tests(skill_path, args.num_tests)
    
    # 输出
    if args.json:
        output = json.dumps(to_dict(report), ensure_ascii=False, indent=2)
    else:
        output = format_console_report(report)
    
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"报告已保存到: {args.output}")
    else:
        print(output)
    
    # 返回码
    sys.exit(0 if report.pass_rate >= 60 else 1)


if __name__ == "__main__":
    main()
