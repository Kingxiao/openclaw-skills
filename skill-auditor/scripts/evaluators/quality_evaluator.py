#!/usr/bin/env python3
"""
Skill Auditor - 质量评估器

评估 AI Agent Skills 的质量指标：
- 可读性分析
- 清晰性评估（动作动词使用率、祈使句比例）
- 完整性检查（必要章节覆盖）
- 一致性验证（术语和格式）
- 文档化程度
- 示例质量

Usage:
    python quality_evaluator.py <skill-path>
    
Returns:
    QualityResult with scores and improvement suggestions
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter


@dataclass
class QualityMetric:
    """质量指标"""
    name: str
    score: float  # 0-100
    weight: float  # 权重
    details: str
    suggestions: list = field(default_factory=list)


@dataclass
class QualityResult:
    """质量评估结果"""
    overall_score: float  # 加权总分
    metrics: dict = field(default_factory=dict)  # 各维度得分
    grade: str = ""  # 等级
    summary: str = ""


# 必要章节定义
REQUIRED_SECTIONS = {
    "overview": {
        "patterns": [
            r"^#+\s*(?:overview|概述|简介|introduction|核心能力|能力|功能)",
            r"^This\s+skill",
            r"^#+\s*飞书",  # 允许技能名作为 Overview
        ],
        "weight": 1.0,
        "description": "概述/Overview"
    },
    "usage": {
        "patterns": [
            r"^#+\s*(?:when\s+to\s+use|使用场景|usage|how\s+to\s+use|快速开始|quick\s+start)",
            r"^#+\s*(?:使用示例|触发场景|适用场景)",
        ],
        "weight": 0.8,
        "description": "使用场景/When to Use"
    },
    "instructions": {
        "patterns": [
            r"^#+\s*(?:step\s*\d|instructions?|步骤|操作|how\s+it\s+works|workflow)",
            r"^#+\s*(?:工作流程|执行步骤|操作流程|流程)",
        ],
        "weight": 1.0,
        "description": "操作步骤/Instructions"
    },
    "examples": {
        "patterns": [
            r"^#+\s*(?:examples?|示例|用例|use\s+cases?)",
            r"^#+\s*(?:使用示例|案例|场景示例)",
        ],
        "weight": 0.6,
        "description": "示例/Examples"
    },
}

# 动作动词列表
ACTION_VERBS = [
    "create", "generate", "build", "make", "write", "read", "load", "save",
    "update", "modify", "edit", "delete", "remove", "add", "insert",
    "run", "execute", "call", "invoke", "start", "stop", "restart",
    "check", "validate", "verify", "test", "analyze", "scan", "audit",
    "configure", "setup", "install", "deploy", "publish",
    "extract", "parse", "process", "transform", "convert",
    "send", "receive", "upload", "download", "fetch",
    "open", "close", "connect", "disconnect",
    # 中文动词
    "创建", "生成", "构建", "编写", "读取", "加载", "保存",
    "更新", "修改", "编辑", "删除", "移除", "添加", "插入",
    "运行", "执行", "调用", "启动", "停止", "重启",
    "检查", "验证", "测试", "分析", "扫描", "审计",
    "配置", "安装", "部署", "发布",
    "提取", "解析", "处理", "转换",
    "发送", "接收", "上传", "下载", "获取",
    "打开", "关闭", "连接", "断开",
]

# 应避免的模式
AVOID_PATTERNS = [
    (r"(?i)\byou\s+should\b", "第二人称 'you should'"),
    (r"(?i)\byou\s+can\b", "第二人称 'you can'"),
    (r"(?i)\byou\s+need\s+to\b", "第二人称 'you need to'"),
    (r"(?i)\bplease\s+", "'please' (可省略)"),
    (r"(?i)\bkindly\s+", "'kindly' (过于正式)"),
    (r"\[TODO\]", "未完成的 TODO 标记"),
    (r"\[TBD\]", "待定的 TBD 标记"),
    (r"(?i)\betc\.?\b", "模糊的 'etc.'"),
]


def analyze_readability(content: str) -> QualityMetric:
    """分析可读性"""
    lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
    
    if not lines:
        return QualityMetric(
            name="可读性",
            score=50,
            weight=0.15,
            details="无足够内容进行分析"
        )
    
    # 计算平均句子长度
    sentences = []
    for line in lines:
        # 简单的句子分割
        sents = re.split(r'[.!?。！？]', line)
        sentences.extend([s.strip() for s in sents if s.strip()])
    
    if not sentences:
        return QualityMetric(
            name="可读性",
            score=60,
            weight=0.15,
            details="无法识别句子结构"
        )
    
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
    
    # 理想句子长度 10-20 词
    suggestions = []
    if avg_sentence_length > 25:
        score = max(40, 100 - (avg_sentence_length - 20) * 3)
        suggestions.append("句子过长，建议拆分为更短的句子")
    elif avg_sentence_length < 5:
        score = max(50, 100 - (10 - avg_sentence_length) * 5)
        suggestions.append("句子过短，可能缺少必要细节")
    else:
        score = min(100, 70 + (20 - abs(avg_sentence_length - 15)) * 2)
    
    # 检查代码块数量（代码块有助于理解）
    code_blocks = len(re.findall(r'```', content)) // 2
    if code_blocks > 0:
        score = min(100, score + code_blocks * 2)
    
    return QualityMetric(
        name="可读性",
        score=score,
        weight=0.15,
        details=f"平均句子长度: {avg_sentence_length:.1f} 词, 代码块: {code_blocks} 个",
        suggestions=suggestions
    )


def analyze_clarity(content: str) -> QualityMetric:
    """分析清晰性"""
    suggestions = []
    deductions = 0
    
    # 计算动作动词使用率
    words = re.findall(r'\b\w+\b', content.lower())
    action_verb_count = sum(1 for w in words if w in [v.lower() for v in ACTION_VERBS])
    action_ratio = action_verb_count / max(len(words), 1) * 100
    
    # 检查应避免的模式
    avoid_counts = []
    for pattern, description in AVOID_PATTERNS:
        count = len(re.findall(pattern, content))
        if count > 0:
            avoid_counts.append((description, count))
            deductions += count * 3
    
    if avoid_counts:
        for desc, count in avoid_counts:
            suggestions.append(f"发现 {count} 处 {desc}，建议修改")
    
    # 检查使用祈使句的比例
    imperative_patterns = [
        r"^(?:To\s+\w+|Create|Generate|Run|Execute|Check|Verify|Use|Add|Remove|Update)",
        r"^(?:创建|生成|运行|执行|检查|验证|使用|添加|删除|更新)",
    ]
    
    lines = content.split("\n")
    instruction_lines = [l for l in lines if l.strip() and not l.startswith("#") 
                         and not l.startswith("```") and not l.startswith("-")]
    
    imperative_count = 0
    for line in instruction_lines:
        for pattern in imperative_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                imperative_count += 1
                break
    
    # 计算得分
    base_score = 70
    base_score += min(15, action_ratio * 3)  # 动作动词加分
    base_score -= min(30, deductions)  # 避免模式扣分
    
    score = max(0, min(100, base_score))
    
    details = (f"动作动词比例: {action_ratio:.1f}%, "
               f"祈使句行数: {imperative_count}, "
               f"避免模式次数: {sum(c for _, c in avoid_counts)}")
    
    return QualityMetric(
        name="清晰性",
        score=score,
        weight=0.20,
        details=details,
        suggestions=suggestions
    )


def analyze_completeness(content: str) -> QualityMetric:
    """分析完整性"""
    suggestions = []
    found_sections = []
    missing_sections = []
    
    content_lower = content.lower()
    lines = content.split("\n")
    
    for section_name, section_config in REQUIRED_SECTIONS.items():
        found = False
        for pattern in section_config["patterns"]:
            for line in lines:
                if re.match(pattern, line, re.IGNORECASE):
                    found = True
                    break
            if found:
                break
        
        if found:
            found_sections.append(section_name)
        else:
            missing_sections.append(section_config["description"])
    
    # 计算覆盖率
    total_weight = sum(s["weight"] for s in REQUIRED_SECTIONS.values())
    found_weight = sum(REQUIRED_SECTIONS[s]["weight"] for s in found_sections)
    coverage = found_weight / total_weight * 100
    
    if missing_sections:
        suggestions.append(f"建议添加以下章节: {', '.join(missing_sections)}")
    
    # 检查示例数量
    example_count = len(re.findall(r'```', content)) // 2
    if example_count < 2:
        suggestions.append(f"当前只有 {example_count} 个代码示例，建议至少 2 个")
        coverage = max(0, coverage - 10)
    elif example_count >= 3:
        coverage = min(100, coverage + 5)
    
    score = max(0, min(100, coverage))
    
    return QualityMetric(
        name="完整性",
        score=score,
        weight=0.25,
        details=f"章节覆盖: {len(found_sections)}/{len(REQUIRED_SECTIONS)}, 代码示例: {example_count}",
        suggestions=suggestions
    )


def analyze_consistency(content: str) -> QualityMetric:
    """分析一致性"""
    suggestions = []
    issues = 0
    
    lines = content.split("\n")
    
    # 检查标题层级一致性
    heading_levels = []
    for line in lines:
        match = re.match(r'^(#+)\s+', line)
        if match:
            heading_levels.append(len(match.group(1)))
    
    if heading_levels:
        # 检查是否从 H1 开始
        if heading_levels[0] != 1:
            issues += 1
            suggestions.append("建议从 H1 标题开始")
        
        # 检查层级跳跃
        for i in range(1, len(heading_levels)):
            if heading_levels[i] > heading_levels[i-1] + 1:
                issues += 1
                suggestions.append("发现标题层级跳跃（如 H1 直接到 H3）")
                break
    
    # 检查列表格式一致性
    list_markers = []
    for line in lines:
        match = re.match(r'^(\s*)([-*+]|\d+\.)\s', line)
        if match:
            list_markers.append(match.group(2)[0])
    
    if list_markers:
        marker_counts = Counter(list_markers)
        if len(marker_counts) > 1:
            most_common = marker_counts.most_common(1)[0][0]
            suggestions.append(f"列表标记不一致，建议统一使用 '{most_common}'")
            issues += 1
    
    # 检查中英文混排空格
    mixed_patterns = [
        (r'[\u4e00-\u9fff][a-zA-Z]', "中文后紧跟英文，建议加空格"),
        (r'[a-zA-Z][\u4e00-\u9fff]', "英文后紧跟中文，建议加空格"),
    ]
    
    for pattern, desc in mixed_patterns:
        if re.search(pattern, content):
            issues += 0.5  # 较轻的问题
            if desc not in [s for s in suggestions]:
                suggestions.append(desc)
    
    score = max(0, 100 - issues * 10)
    
    return QualityMetric(
        name="一致性",
        score=score,
        weight=0.15,
        details=f"发现 {issues} 个一致性问题",
        suggestions=suggestions
    )


def analyze_documentation(skill_dir: Path) -> QualityMetric:
    """分析文档化程度"""
    suggestions = []
    total_scripts = 0
    documented_scripts = 0
    
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.rglob("*.py"):
            # 跳过 __init__.py 文件
            if script.name == "__init__.py":
                continue
            total_scripts += 1
            try:
                content = script.read_text(encoding="utf-8")
                # 检查是否有模块级 docstring
                lines = content.split("\n")
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#") or not stripped:
                        continue
                    has_docstring = stripped.startswith('''"""''') or stripped.startswith('''"'"'"''')
                    break
                else:
                    has_docstring = False
                if has_docstring:
                    documented_scripts += 1
            except:
                pass
    
    if total_scripts > 0:
        doc_ratio = documented_scripts / total_scripts * 100
        score = doc_ratio
        
        if doc_ratio < 100:
            undocumented = total_scripts - documented_scripts
            suggestions.append(f"{undocumented} 个脚本缺少 docstring")
    else:
        score = 80  # 无脚本默认分数
    
    # 检查是否有 references 文档
    references_dir = skill_dir / "references"
    if references_dir.exists() and list(references_dir.glob("*.md")):
        score = min(100, score + 10)
    
    return QualityMetric(
        name="文档化",
        score=score,
        weight=0.15,
        details=f"有 docstring 的脚本: {documented_scripts}/{total_scripts}",
        suggestions=suggestions
    )


def analyze_practicality(content: str, skill_dir: Path) -> QualityMetric:
    """分析实用性"""
    suggestions = []
    score = 70  # 基础分
    
    # 检查代码示例数量和质量
    code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
    
    if len(code_blocks) >= 3:
        score += 10
    elif len(code_blocks) < 1:
        score -= 20
        suggestions.append("缺少代码示例，建议添加至少 1 个")
    
    # 检查示例是否有语言标注
    unlabeled = sum(1 for lang, _ in code_blocks if not lang)
    if unlabeled > 0:
        suggestions.append(f"{unlabeled} 个代码块缺少语言标注")
        score -= unlabeled * 2
    
    # 检查是否有实际可执行的命令示例
    has_command = ('```bash' in content or '```shell' in content or 
                   'python ' in content or 'npm ' in content)
    if has_command:
        score += 5
    
    # 检查是否有脚本可用
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        script_count = len(list(scripts_dir.rglob("*.py"))) + len(list(scripts_dir.rglob("*.sh")))
        if script_count > 0:
            score += min(10, script_count * 3)
    
    score = max(0, min(100, score))
    
    return QualityMetric(
        name="实用性",
        score=score,
        weight=0.10,
        details=f"代码示例: {len(code_blocks)} 个",
        suggestions=suggestions
    )


def calculate_grade(score: float) -> str:
    """计算等级"""
    if score >= 90:
        return "⭐⭐⭐⭐⭐ A+"
    elif score >= 80:
        return "⭐⭐⭐⭐ A"
    elif score >= 70:
        return "⭐⭐⭐ B"
    elif score >= 60:
        return "⭐⭐ C"
    else:
        return "⭐ D"


def evaluate_quality(skill_path: str) -> QualityResult:
    """
    执行完整的质量评估
    
    Args:
        skill_path: 技能目录路径
        
    Returns:
        QualityResult 包含评估结果
    """
    skill_dir = Path(skill_path).resolve()
    
    if not skill_dir.exists():
        return QualityResult(
            overall_score=0,
            grade="❌",
            summary=f"目录不存在: {skill_dir}"
        )
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return QualityResult(
            overall_score=0,
            grade="❌",
            summary="缺少 SKILL.md 文件"
        )
    
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        return QualityResult(
            overall_score=0,
            grade="❌",
            summary=f"无法读取 SKILL.md: {e}"
        )
    
    # 运行各维度评估
    metrics = {
        "readability": analyze_readability(content),
        "clarity": analyze_clarity(content),
        "completeness": analyze_completeness(content),
        "consistency": analyze_consistency(content),
        "documentation": analyze_documentation(skill_dir),
        "practicality": analyze_practicality(content, skill_dir),
    }
    
    # 计算加权总分
    total_weight = sum(m.weight for m in metrics.values())
    weighted_score = sum(m.score * m.weight for m in metrics.values()) / total_weight
    
    grade = calculate_grade(weighted_score)
    
    # 生成摘要
    low_metrics = [(name, m) for name, m in metrics.items() if m.score < 70]
    if low_metrics:
        summary = f"需要改进的维度: {', '.join(m.name for _, m in low_metrics)}"
    else:
        summary = "整体质量良好"
    
    return QualityResult(
        overall_score=weighted_score,
        metrics=metrics,
        grade=grade,
        summary=summary
    )


def format_report(result: QualityResult) -> str:
    """格式化质量评估报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("质量评估报告")
    lines.append("=" * 60)
    lines.append(f"综合得分: {result.overall_score:.1f}/100")
    lines.append(f"质量等级: {result.grade}")
    lines.append(f"评估摘要: {result.summary}")
    lines.append("-" * 60)
    lines.append("分项得分:")
    
    for name, metric in result.metrics.items():
        icon = "✅" if metric.score >= 70 else "⚠️" if metric.score >= 50 else "❌"
        lines.append(f"\n  {icon} {metric.name}: {metric.score:.1f}/100 (权重: {metric.weight*100:.0f}%)")
        lines.append(f"     📊 {metric.details}")
        
        if metric.suggestions:
            for suggestion in metric.suggestions:
                lines.append(f"     💡 {suggestion}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python quality_evaluator.py <skill-path>")
        print("\nExample:")
        print("  python quality_evaluator.py ./my-skill")
        sys.exit(1)
    
    skill_path = sys.argv[1]
    result = evaluate_quality(skill_path)
    print(format_report(result))
    
    # 返回码基于分数
    if result.overall_score >= 70:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
