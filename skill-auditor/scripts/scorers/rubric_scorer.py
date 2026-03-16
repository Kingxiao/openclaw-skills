#!/usr/bin/env python3
"""
Skill Auditor - Rubric 评分器

基于多维度 Rubric 对技能进行量化评分：
- 格式规范 (15%)
- 安全性 (25%)
- 文档质量 (20%)
- 能力覆盖 (15%)
- 可维护性 (15%)
- 实用性 (10%)

Usage:
    python rubric_scorer.py <skill-path>
    python rubric_scorer.py <skill-path> --config custom_rubric.json
    
Returns:
    RubricScore with composite score and grade
"""

import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# 导入其他评估器
sys.path.insert(0, str(Path(__file__).parent.parent))
from validators.format_validator import validate_skill as format_validate
from validators.security_scanner import scan_skill as security_scan
from evaluators.quality_evaluator import evaluate_quality
from evaluators.capability_analyzer import analyze_capability


@dataclass
class DimensionScore:
    """维度得分"""
    name: str
    score: float  # 0-100
    weight: float  # 权重
    weighted_score: float  # 加权得分
    details: str = ""


@dataclass
class RubricScore:
    """Rubric 评分结果"""
    skill_name: str
    total_score: float  # 综合得分
    grade: str  # 等级
    dimensions: list = field(default_factory=list)
    summary: str = ""
    recommendations: list = field(default_factory=list)


# 默认 Rubric 配置
DEFAULT_RUBRIC = {
    "dimensions": {
        "format": {
            "name": "格式规范",
            "weight": 0.15,
            "description": "结构完整性、命名规范、frontmatter 正确性"
        },
        "security": {
            "name": "安全性",
            "weight": 0.25,
            "description": "无安全漏洞、无敏感信息泄露、无危险代码"
        },
        "quality": {
            "name": "文档质量",
            "weight": 0.20,
            "description": "清晰性、完整性、可读性、一致性"
        },
        "capability": {
            "name": "能力覆盖",
            "weight": 0.15,
            "description": "功能范围、场景覆盖、触发词完整性"
        },
        "maintainability": {
            "name": "可维护性",
            "weight": 0.15,
            "description": "模块化、注释、单一来源、结构清晰"
        },
        "practicality": {
            "name": "实用性",
            "weight": 0.10,
            "description": "示例质量、实际可用性、脚本完整性"
        }
    },
    "grades": {
        "A+": {"min": 90, "stars": 5, "label": "卓越 - 可作为参考模板"},
        "A": {"min": 80, "stars": 4, "label": "优秀 - 生产就绪"},
        "B": {"min": 70, "stars": 3, "label": "良好 - 可用但有改进空间"},
        "C": {"min": 60, "stars": 2, "label": "合格 - 需要改进"},
        "D": {"min": 0, "stars": 1, "label": "不合格 - 需要重大修改"}
    }
}


def calculate_maintainability(skill_dir: Path, content: str) -> tuple[float, str]:
    """计算可维护性得分"""
    score = 70  # 基础分
    details = []
    
    # 检查 SKILL.md 行数
    line_count = len(content.split("\n"))
    if line_count > 500:
        score -= 15
        details.append("SKILL.md 过长")
    elif line_count > 400:
        score -= 5
        details.append("SKILL.md 接近上限")
    else:
        score += 5
    
    # 检查是否有 references 目录（良好的模块化）
    if (skill_dir / "references").exists():
        ref_count = len(list((skill_dir / "references").glob("*.md")))
        if ref_count > 0:
            score += min(10, ref_count * 3)
            details.append(f"有 {ref_count} 个参考文档")
    
    # 检查脚本结构
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        # 检查是否有子目录（良好组织）
        subdirs = [d for d in scripts_dir.iterdir() if d.is_dir()]
        if subdirs:
            score += 5
            details.append("脚本有良好的目录组织")
        
        # 检查是否有 __init__.py（模块化）
        if (scripts_dir / "__init__.py").exists():
            score += 5
    
    # 检查是否有重复内容的迹象
    # 简单检查：相同的长段落是否出现多次
    paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 100]
    unique_paragraphs = set(paragraphs)
    if len(paragraphs) > len(unique_paragraphs):
        score -= 10
        details.append("可能存在重复内容")
    
    score = max(0, min(100, score))
    return score, "; ".join(details) if details else "结构良好"


def calculate_practicality(skill_dir: Path, content: str) -> tuple[float, str]:
    """计算实用性得分"""
    score = 60  # 基础分
    details = []
    
    # 检查代码示例
    import re
    code_blocks = re.findall(r'```(\w*)\n', content)
    if len(code_blocks) >= 3:
        score += 15
        details.append(f"{len(code_blocks)} 个代码示例")
    elif len(code_blocks) >= 1:
        score += 5
        details.append(f"{len(code_blocks)} 个代码示例（建议增加）")
    else:
        score -= 10
        details.append("缺少代码示例")
    
    # 检查是否有可执行脚本
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        py_scripts = list(scripts_dir.rglob("*.py"))
        sh_scripts = list(scripts_dir.rglob("*.sh"))
        script_count = len(py_scripts) + len(sh_scripts)
        
        if script_count > 0:
            score += min(15, script_count * 4)
            details.append(f"{script_count} 个可执行脚本")
            
            # 检查主入口脚本
            for script in py_scripts:
                try:
                    script_content = script.read_text(encoding="utf-8")
                    if "argparse" in script_content or "sys.argv" in script_content:
                        score += 5
                        details.append("包含 CLI 接口")
                        break
                except:
                    pass
    
    # 检查是否有资源模板
    assets_dir = skill_dir / "assets"
    if assets_dir.exists() and list(assets_dir.rglob("*")):
        score += 5
        details.append("包含资源文件")
    
    score = max(0, min(100, score))
    return score, "; ".join(details) if details else "基础可用"


def score_skill(skill_path: str, rubric_config: dict = None) -> RubricScore:
    """
    对技能进行 Rubric 评分
    
    Args:
        skill_path: 技能目录路径
        rubric_config: 自定义 Rubric 配置
        
    Returns:
        RubricScore 包含综合评分
    """
    skill_dir = Path(skill_path).resolve()
    config = rubric_config or DEFAULT_RUBRIC
    dimensions = []
    recommendations = []
    
    # 验证路径
    if not skill_dir.exists():
        return RubricScore(
            skill_name="N/A",
            total_score=0,
            grade="❌",
            summary="目录不存在"
        )
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return RubricScore(
            skill_name="N/A",
            total_score=0,
            grade="❌",
            summary="缺少 SKILL.md"
        )
    
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        return RubricScore(
            skill_name="N/A",
            total_score=0,
            grade="❌",
            summary=f"读取错误: {e}"
        )
    
    skill_name = skill_dir.name
    
    # 1. 格式规范评分
    format_result = format_validate(skill_path)
    format_weight = config["dimensions"]["format"]["weight"]
    dimensions.append(DimensionScore(
        name=config["dimensions"]["format"]["name"],
        score=format_result.score,
        weight=format_weight,
        weighted_score=format_result.score * format_weight,
        details=f"{len(format_result.issues)} 个问题"
    ))
    if format_result.score < 70:
        recommendations.append("修复格式问题以提升规范性")
    
    # 2. 安全性评分
    security_result = security_scan(skill_path)
    security_weight = config["dimensions"]["security"]["weight"]
    dimensions.append(DimensionScore(
        name=config["dimensions"]["security"]["name"],
        score=security_result.score,
        weight=security_weight,
        weighted_score=security_result.score * security_weight,
        details=f"{len(security_result.findings)} 个发现"
    ))
    if security_result.score < 100:
        recommendations.append("处理安全扫描发现的问题")
    
    # 3. 文档质量评分
    quality_result = evaluate_quality(skill_path)
    quality_weight = config["dimensions"]["quality"]["weight"]
    dimensions.append(DimensionScore(
        name=config["dimensions"]["quality"]["name"],
        score=quality_result.overall_score,
        weight=quality_weight,
        weighted_score=quality_result.overall_score * quality_weight,
        details=quality_result.summary
    ))
    if quality_result.overall_score < 70:
        recommendations.append("提升文档质量：改善清晰性和完整性")
    
    # 4. 能力覆盖评分
    capability_result = analyze_capability(skill_path)
    # 基于复杂度和覆盖度估算分数
    capability_score = min(100, 50 + capability_result.complexity_score * 5)
    if "95%" in capability_result.coverage_estimate:
        capability_score = min(100, capability_score + 20)
    elif "85" in capability_result.coverage_estimate:
        capability_score = min(100, capability_score + 10)
    
    capability_weight = config["dimensions"]["capability"]["weight"]
    dimensions.append(DimensionScore(
        name=config["dimensions"]["capability"]["name"],
        score=capability_score,
        weight=capability_weight,
        weighted_score=capability_score * capability_weight,
        details=f"覆盖: {capability_result.coverage_estimate}"
    ))
    if capability_score < 70:
        recommendations.append("扩展触发词和功能覆盖范围")
    
    # 5. 可维护性评分
    maintainability_score, maintainability_details = calculate_maintainability(skill_dir, content)
    maintainability_weight = config["dimensions"]["maintainability"]["weight"]
    dimensions.append(DimensionScore(
        name=config["dimensions"]["maintainability"]["name"],
        score=maintainability_score,
        weight=maintainability_weight,
        weighted_score=maintainability_score * maintainability_weight,
        details=maintainability_details
    ))
    if maintainability_score < 70:
        recommendations.append("改善代码组织和模块化结构")
    
    # 6. 实用性评分
    practicality_score, practicality_details = calculate_practicality(skill_dir, content)
    practicality_weight = config["dimensions"]["practicality"]["weight"]
    dimensions.append(DimensionScore(
        name=config["dimensions"]["practicality"]["name"],
        score=practicality_score,
        weight=practicality_weight,
        weighted_score=practicality_score * practicality_weight,
        details=practicality_details
    ))
    if practicality_score < 70:
        recommendations.append("增加可执行示例和实用脚本")
    
    # 计算总分
    total_score = sum(d.weighted_score for d in dimensions)
    
    # 确定等级
    grade = "D"
    grade_info = config["grades"]["D"]
    for grade_name, grade_config in config["grades"].items():
        if total_score >= grade_config["min"]:
            grade = grade_name
            grade_info = grade_config
            break
    
    stars = "⭐" * grade_info["stars"]
    grade_str = f"{stars} {grade} - {grade_info['label']}"
    
    # 生成摘要
    if total_score >= 90:
        summary = "技能质量卓越，可作为最佳实践参考"
    elif total_score >= 80:
        summary = "技能质量优秀，已达生产就绪标准"
    elif total_score >= 70:
        summary = "技能质量良好，有少量改进空间"
    elif total_score >= 60:
        summary = "技能质量合格，建议进行改进"
    else:
        summary = "技能质量不足，需要重大修改"
    
    return RubricScore(
        skill_name=skill_name,
        total_score=total_score,
        grade=grade_str,
        dimensions=dimensions,
        summary=summary,
        recommendations=recommendations[:5]  # 最多5条建议
    )


def format_report(result: RubricScore) -> str:
    """格式化 Rubric 评分报告"""
    lines = []
    lines.append("=" * 70)
    lines.append("Rubric 综合评分报告")
    lines.append("=" * 70)
    lines.append(f"技能名称: {result.skill_name}")
    lines.append(f"综合得分: {result.total_score:.1f}/100")
    lines.append(f"质量等级: {result.grade}")
    lines.append(f"评估摘要: {result.summary}")
    lines.append("-" * 70)
    
    lines.append("\n📊 分项得分:")
    lines.append(f"{'维度':<12} {'得分':>8} {'权重':>8} {'加权分':>10} {'详情'}")
    lines.append("-" * 70)
    
    for dim in result.dimensions:
        icon = "✅" if dim.score >= 70 else "⚠️" if dim.score >= 50 else "❌"
        lines.append(
            f"{icon} {dim.name:<10} {dim.score:>6.1f} {dim.weight*100:>6.0f}% "
            f"{dim.weighted_score:>8.1f}   {dim.details}"
        )
    
    lines.append("-" * 70)
    lines.append(f"{'总计':<12} {'':<8} {'100%':>8} {result.total_score:>8.1f}")
    
    if result.recommendations:
        lines.append("\n💡 改进建议:")
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"   {i}. {rec}")
    
    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Rubric 评分器 - 对技能进行多维度量化评分"
    )
    parser.add_argument("skill_path", help="技能目录路径")
    parser.add_argument("--config", "-c", help="自定义 Rubric 配置文件 (JSON)")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    
    args = parser.parse_args()
    
    # 加载自定义配置
    rubric_config = None
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                rubric_config = json.load(f)
        except Exception as e:
            print(f"警告: 无法加载配置文件: {e}，使用默认配置")
    
    result = score_skill(args.skill_path, rubric_config)
    
    if args.json:
        # JSON 输出
        output = {
            "skill_name": result.skill_name,
            "total_score": result.total_score,
            "grade": result.grade,
            "summary": result.summary,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "weighted_score": d.weighted_score,
                    "details": d.details
                }
                for d in result.dimensions
            ],
            "recommendations": result.recommendations
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    
    # 返回码基于分数
    if result.total_score >= 70:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
