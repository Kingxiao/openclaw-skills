#!/usr/bin/env python3
"""
Skill Auditor - 主审计入口

综合运行所有审计检查并生成完整报告：
- 格式/结构验证
- 安全扫描
- 质量评估
- 能力分析
- Rubric 评分
- 可选：回归检测、断言测试

Usage:
    # 完整审计
    python audit_skill.py <skill-path>
    
    # 指定检查类型
    python audit_skill.py <skill-path> --check format,security,quality
    
    # 生成报告文件
    python audit_skill.py <skill-path> --output report.md --format markdown
    
    # 回归检测
    python audit_skill.py <skill-path> --baseline <old-skill-path>
    
    # 使用断言
    python audit_skill.py <skill-path> --assertions assertions.txt
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

# 确保导入路径正确
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from validators.format_validator import validate_skill as format_validate, format_report as format_format_report
from validators.security_scanner import scan_skill as security_scan, format_report as format_security_report
from evaluators.quality_evaluator import evaluate_quality, format_report as format_quality_report
from evaluators.capability_analyzer import analyze_capability, format_report as format_capability_report
from scorers.rubric_scorer import score_skill, format_report as format_rubric_report


@dataclass
class AuditResult:
    """完整审计结果"""
    skill_name: str
    skill_path: str
    audit_time: str
    overall_score: float
    grade: str
    passed: bool
    format_result: Optional[dict] = None
    security_result: Optional[dict] = None
    quality_result: Optional[dict] = None
    capability_result: Optional[dict] = None
    rubric_result: Optional[dict] = None
    regression_result: Optional[dict] = None
    assertion_result: Optional[dict] = None
    summary: str = ""
    recommendations: list = field(default_factory=list)


def run_audit(
    skill_path: str,
    checks: list = None,
    baseline_path: str = None,
    assertions_file: str = None
) -> AuditResult:
    """
    运行完整审计
    
    Args:
        skill_path: 技能目录路径
        checks: 要运行的检查类型列表
        baseline_path: 基线版本路径（用于回归检测）
        assertions_file: 断言文件路径
        
    Returns:
        AuditResult 包含完整审计结果
    """
    skill_dir = Path(skill_path).resolve()
    
    if not skill_dir.exists():
        return AuditResult(
            skill_name="N/A",
            skill_path=str(skill_dir),
            audit_time=datetime.now().isoformat(),
            overall_score=0,
            grade="❌",
            passed=False,
            summary=f"目录不存在: {skill_dir}"
        )
    
    if not (skill_dir / "SKILL.md").exists():
        return AuditResult(
            skill_name="N/A",
            skill_path=str(skill_dir),
            audit_time=datetime.now().isoformat(),
            overall_score=0,
            grade="❌",
            passed=False,
            summary="缺少 SKILL.md 文件"
        )
    
    skill_name = skill_dir.name
    all_checks = checks or ["format", "security", "quality", "capability", "rubric"]
    
    result = AuditResult(
        skill_name=skill_name,
        skill_path=str(skill_dir),
        audit_time=datetime.now().isoformat(),
        overall_score=0,
        grade="",
        passed=True
    )
    
    # 1. 格式验证
    if "format" in all_checks:
        format_result = format_validate(str(skill_dir))
        result.format_result = {
            "passed": format_result.passed,
            "score": format_result.score,
            "issues_count": len(format_result.issues),
            "issues": [
                {
                    "severity": i.severity.value,
                    "code": i.code,
                    "message": i.message
                }
                for i in format_result.issues
            ]
        }
        if not format_result.passed:
            result.passed = False
    
    # 2. 安全扫描
    if "security" in all_checks:
        security_result = security_scan(str(skill_dir))
        result.security_result = {
            "passed": security_result.passed,
            "score": security_result.score,
            "risk_summary": security_result.risk_summary,
            "findings_count": len(security_result.findings),
            "findings": [
                {
                    "risk_level": f.risk_level.value,
                    "category": f.category,
                    "message": f.message,
                    "location": f.location
                }
                for f in security_result.findings[:10]  # 限制数量
            ]
        }
        if not security_result.passed:
            result.passed = False
    
    # 3. 质量评估
    if "quality" in all_checks:
        quality_result = evaluate_quality(str(skill_dir))
        result.quality_result = {
            "score": quality_result.overall_score,
            "grade": quality_result.grade,
            "summary": quality_result.summary,
            "metrics": {
                name: {
                    "score": m.score,
                    "weight": m.weight,
                    "details": m.details
                }
                for name, m in quality_result.metrics.items()
            }
        }
    
    # 4. 能力分析
    if "capability" in all_checks:
        capability_result = analyze_capability(str(skill_dir))
        result.capability_result = {
            "skill_name": capability_result.skill_name,
            "triggers": capability_result.triggers,
            "capabilities": capability_result.capabilities,
            "complexity_score": capability_result.complexity_score,
            "coverage_estimate": capability_result.coverage_estimate
        }
    
    # 5. Rubric 评分
    if "rubric" in all_checks:
        rubric_result = score_skill(str(skill_dir))
        result.rubric_result = {
            "total_score": rubric_result.total_score,
            "grade": rubric_result.grade,
            "summary": rubric_result.summary,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "weighted_score": d.weighted_score
                }
                for d in rubric_result.dimensions
            ],
            "recommendations": rubric_result.recommendations
        }
        result.overall_score = rubric_result.total_score
        result.grade = rubric_result.grade
        result.recommendations = rubric_result.recommendations
    
    # 6. 回归检测（可选）
    if baseline_path and "regression" in all_checks:
        from evaluators.regression_checker import check_regression
        regression_result = check_regression(str(skill_dir), baseline_path)
        result.regression_result = {
            "passed": regression_result.passed,
            "breaking_changes": len(regression_result.breaking_changes),
            "compatible_changes": len(regression_result.compatible_changes),
            "enhancements": len(regression_result.enhancements),
            "summary": regression_result.summary
        }
        if not regression_result.passed:
            result.passed = False
    
    # 7. 断言测试（可选）
    if assertions_file and "assertions" in all_checks:
        from evaluators.assertion_tester import run_assertions
        assertions = []
        try:
            with open(assertions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        assertions.append(line)
        except:
            pass
        
        if assertions:
            assertion_result = run_assertions(str(skill_dir), assertions)
            result.assertion_result = {
                "total": assertion_result.total,
                "passed": assertion_result.passed,
                "failed": assertion_result.failed,
                "pass_rate": assertion_result.passed / max(assertion_result.total, 1) * 100
            }
    
    # 生成摘要
    if result.overall_score >= 70 and result.passed:
        result.summary = f"✅ 审计通过 - 得分: {result.overall_score:.1f}/100"
    else:
        issues = []
        if result.format_result and not result.format_result.get("passed"):
            issues.append("格式问题")
        if result.security_result and not result.security_result.get("passed"):
            issues.append("安全风险")
        if result.regression_result and not result.regression_result.get("passed"):
            issues.append("回归问题")
        result.summary = f"⚠️ 审计发现问题: {', '.join(issues) if issues else '质量评分偏低'}"
    
    return result


def format_markdown_report(result: AuditResult) -> str:
    """生成 Markdown 格式报告"""
    lines = []
    lines.append(f"# 技能审计报告: {result.skill_name}")
    lines.append("")
    lines.append(f"**审计时间**: {result.audit_time}")
    lines.append(f"**技能路径**: `{result.skill_path}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # 综合评分
    lines.append("## 📊 综合评分")
    lines.append("")
    lines.append(f"| 指标 | 结果 |")
    lines.append("|------|------|")
    lines.append(f"| 综合得分 | **{result.overall_score:.1f}/100** |")
    lines.append(f"| 质量等级 | {result.grade} |")
    lines.append(f"| 审计结果 | {'✅ 通过' if result.passed else '❌ 不通过'} |")
    lines.append(f"| 摘要 | {result.summary} |")
    lines.append("")
    
    # Rubric 分项得分
    if result.rubric_result:
        lines.append("### 分项得分")
        lines.append("")
        lines.append("| 维度 | 得分 | 权重 | 加权分 |")
        lines.append("|------|------|------|--------|")
        for dim in result.rubric_result.get("dimensions", []):
            icon = "✅" if dim["score"] >= 70 else "⚠️" if dim["score"] >= 50 else "❌"
            lines.append(
                f"| {icon} {dim['name']} | {dim['score']:.1f} | "
                f"{dim['weight']*100:.0f}% | {dim['weighted_score']:.1f} |"
            )
        lines.append("")
    
    # 格式验证
    if result.format_result:
        lines.append("## 📋 格式验证")
        lines.append("")
        status = "✅ 通过" if result.format_result["passed"] else "❌ 不通过"
        lines.append(f"**状态**: {status}")
        lines.append(f"**得分**: {result.format_result['score']:.1f}/100")
        lines.append(f"**问题数**: {result.format_result['issues_count']}")
        
        if result.format_result.get("issues"):
            lines.append("")
            lines.append("| 严重性 | 代码 | 问题 |")
            lines.append("|--------|------|------|")
            for issue in result.format_result["issues"][:10]:
                lines.append(f"| {issue['severity']} | {issue['code']} | {issue['message']} |")
        lines.append("")
    
    # 安全扫描
    if result.security_result:
        lines.append("## 🔒 安全扫描")
        lines.append("")
        status = "✅ 通过" if result.security_result["passed"] else "❌ 发现风险"
        lines.append(f"**状态**: {status}")
        lines.append(f"**得分**: {result.security_result['score']:.1f}/100")
        lines.append(f"**发现数**: {result.security_result['findings_count']}")
        
        risk_summary = result.security_result.get("risk_summary", {})
        if any(v > 0 for v in risk_summary.values()):
            lines.append("")
            lines.append("**风险分布**:")
            for level, count in risk_summary.items():
                if count > 0:
                    lines.append(f"- {level}: {count}")
        lines.append("")
    
    # 质量评估
    if result.quality_result:
        lines.append("## 📝 质量评估")
        lines.append("")
        lines.append(f"**综合得分**: {result.quality_result['score']:.1f}/100")
        lines.append(f"**质量等级**: {result.quality_result['grade']}")
        lines.append(f"**摘要**: {result.quality_result['summary']}")
        lines.append("")
    
    # 能力分析
    if result.capability_result:
        lines.append("## 🎯 能力分析")
        lines.append("")
        lines.append(f"**复杂度评分**: {result.capability_result['complexity_score']}/10")
        lines.append(f"**场景覆盖**: {result.capability_result['coverage_estimate']}")
        
        if result.capability_result.get("triggers"):
            lines.append(f"**触发关键词**: {', '.join(result.capability_result['triggers'][:10])}")
        lines.append("")
    
    # 改进建议
    if result.recommendations:
        lines.append("## 💡 改进建议")
        lines.append("")
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
    
    lines.append("---")
    lines.append(f"*报告生成时间: {result.audit_time}*")
    
    return "\n".join(lines)


def format_console_report(result: AuditResult) -> str:
    """生成控制台格式报告"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"技能审计报告: {result.skill_name}")
    lines.append("=" * 70)
    lines.append(f"审计时间: {result.audit_time}")
    lines.append(f"技能路径: {result.skill_path}")
    lines.append("-" * 70)
    lines.append(f"综合得分: {result.overall_score:.1f}/100")
    lines.append(f"质量等级: {result.grade}")
    lines.append(f"审计结果: {'✅ 通过' if result.passed else '❌ 不通过'}")
    lines.append(f"摘要: {result.summary}")
    lines.append("-" * 70)
    
    # 分项得分
    if result.rubric_result:
        lines.append("\n📊 分项得分:")
        for dim in result.rubric_result.get("dimensions", []):
            icon = "✅" if dim["score"] >= 70 else "⚠️" if dim["score"] >= 50 else "❌"
            lines.append(
                f"  {icon} {dim['name']:<12} {dim['score']:>6.1f} "
                f"({dim['weight']*100:.0f}%) → {dim['weighted_score']:.1f}"
            )
    
    # 各检查摘要
    lines.append("\n📋 检查摘要:")
    if result.format_result:
        status = "✅" if result.format_result["passed"] else "❌"
        lines.append(f"  {status} 格式验证: {result.format_result['score']:.0f}分, {result.format_result['issues_count']}个问题")
    
    if result.security_result:
        status = "✅" if result.security_result["passed"] else "❌"
        lines.append(f"  {status} 安全扫描: {result.security_result['score']:.0f}分, {result.security_result['findings_count']}个发现")
    
    if result.quality_result:
        lines.append(f"  📝 质量评估: {result.quality_result['score']:.0f}分, {result.quality_result['grade']}")
    
    if result.capability_result:
        lines.append(f"  🎯 能力分析: 复杂度{result.capability_result['complexity_score']}/10, {result.capability_result['coverage_estimate']}")
    
    # 改进建议
    if result.recommendations:
        lines.append("\n💡 改进建议:")
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")
    
    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Skill Auditor - 技能审计工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整审计
  python audit_skill.py ./my-skill
  
  # 仅安全检查
  python audit_skill.py ./my-skill --check security
  
  # 生成 Markdown 报告
  python audit_skill.py ./my-skill --output report.md --format markdown
  
  # 回归检测
  python audit_skill.py ./my-skill-v2 --baseline ./my-skill-v1
        """
    )
    parser.add_argument("skill_path", help="技能目录路径")
    parser.add_argument("--check", "-c", 
                       help="指定检查类型，逗号分隔 (format,security,quality,capability,rubric)")
    parser.add_argument("--baseline", "-b", help="基线版本路径（用于回归检测）")
    parser.add_argument("--assertions", "-a", help="断言文件路径")
    parser.add_argument("--output", "-o", help="输出报告文件路径")
    parser.add_argument("--format", "-f", choices=["console", "markdown", "json"],
                       default="console", help="输出格式 (默认: console)")
    
    args = parser.parse_args()
    
    # 解析检查类型
    checks = None
    if args.check:
        checks = [c.strip() for c in args.check.split(",")]
        if args.baseline:
            checks.append("regression")
        if args.assertions:
            checks.append("assertions")
    elif args.baseline:
        checks = ["format", "security", "quality", "capability", "rubric", "regression"]
    elif args.assertions:
        checks = ["format", "security", "quality", "capability", "rubric", "assertions"]
    
    # 运行审计
    result = run_audit(
        args.skill_path,
        checks=checks,
        baseline_path=args.baseline,
        assertions_file=args.assertions
    )
    
    # 生成报告
    if args.format == "json":
        report = json.dumps({
            "skill_name": result.skill_name,
            "skill_path": result.skill_path,
            "audit_time": result.audit_time,
            "overall_score": result.overall_score,
            "grade": result.grade,
            "passed": result.passed,
            "summary": result.summary,
            "format": result.format_result,
            "security": result.security_result,
            "quality": result.quality_result,
            "capability": result.capability_result,
            "rubric": result.rubric_result,
            "recommendations": result.recommendations
        }, ensure_ascii=False, indent=2)
    elif args.format == "markdown":
        report = format_markdown_report(result)
    else:
        report = format_console_report(result)
    
    # 输出
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"报告已保存到: {output_path}")
    else:
        print(report)
    
    # 返回码
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
