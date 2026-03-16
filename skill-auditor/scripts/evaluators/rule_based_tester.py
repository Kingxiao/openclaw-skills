#!/usr/bin/env python3
"""
基于规则的确定性测试器 (rule_based_tester.py)

提供确定性断言测试，不依赖 LLM 判断。
与 dynamic_tester.py 配合，提供双重验证。

用法:
    python rule_based_tester.py /path/to/skill
    python rule_based_tester.py /path/to/skill --json
    python rule_based_tester.py /path/to/skill --verbose
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

# 语义明确的路径导航
EVALUATORS_DIR = Path(__file__).resolve().parent     # evaluators/
AUDITOR_SCRIPTS = EVALUATORS_DIR.parent              # scripts/
AUDITOR_DIR = AUDITOR_SCRIPTS.parent                 # skill-auditor/
SKILLS_DIR = AUDITOR_DIR.parent                      # skills/
SKILL_MANAGER_DATA = SKILLS_DIR / "skill-manager" / "data"


@dataclass
class TestAssertion:
    """测试断言"""
    name: str
    description: str
    category: str  # structure, content, security, capability
    severity: str  # critical, high, medium, low
    passed: bool
    message: str
    evidence: str = ""


@dataclass
class RuleTestResult:
    """规则测试结果"""
    skill_name: str
    skill_path: str
    test_time: str
    total_assertions: int
    passed_assertions: int
    failed_assertions: int
    pass_rate: float
    assertions: List[TestAssertion]
    score: float  # 0-100
    verdict: str  # pass, warning, fail


# ==================== 规则定义 ====================

class SkillRules:
    """技能规则集合"""
    
    @staticmethod
    def check_skill_md_exists(skill_path: Path) -> TestAssertion:
        """检查 SKILL.md 是否存在"""
        exists = (skill_path / "SKILL.md").exists()
        return TestAssertion(
            name="SKILL.md 存在",
            description="技能必须包含 SKILL.md 主文件",
            category="structure",
            severity="critical",
            passed=exists,
            message="✅ SKILL.md 存在" if exists else "❌ 缺少 SKILL.md",
            evidence=str(skill_path / "SKILL.md")
        )
    
    @staticmethod
    def check_skill_md_has_yaml_header(skill_path: Path) -> TestAssertion:
        """检查 SKILL.md 是否有 YAML 头"""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return TestAssertion(
                name="YAML 头存在",
                description="SKILL.md 必须包含 YAML frontmatter",
                category="structure",
                severity="high",
                passed=False,
                message="❌ 无法检查（SKILL.md 不存在）"
            )
        
        content = skill_md.read_text(encoding="utf-8")
        has_yaml = content.startswith("---")
        
        return TestAssertion(
            name="YAML 头存在",
            description="SKILL.md 必须包含 YAML frontmatter",
            category="structure",
            severity="high",
            passed=has_yaml,
            message="✅ 包含 YAML 头" if has_yaml else "❌ 缺少 YAML 头",
            evidence=content[:100] if has_yaml else ""
        )
    
    @staticmethod
    def check_name_field(skill_path: Path) -> TestAssertion:
        """检查 name 字段"""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return TestAssertion(
                name="name 字段存在",
                description="YAML 头必须包含 name 字段",
                category="content",
                severity="high",
                passed=False,
                message="❌ 无法检查"
            )
        
        content = skill_md.read_text(encoding="utf-8")
        # 查找 name: 行
        match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
        has_name = match is not None and len(match.group(1).strip()) > 0
        
        return TestAssertion(
            name="name 字段存在",
            description="YAML 头必须包含 name 字段",
            category="content",
            severity="high",
            passed=has_name,
            message=f"✅ name: {match.group(1).strip()}" if has_name else "❌ 缺少 name 字段",
            evidence=match.group(0) if match else ""
        )
    
    @staticmethod
    def check_description_field(skill_path: Path) -> TestAssertion:
        """检查 description 字段"""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return TestAssertion(
                name="description 字段存在",
                description="YAML 头必须包含 description 字段",
                category="content",
                severity="high",
                passed=False,
                message="❌ 无法检查"
            )
        
        content = skill_md.read_text(encoding="utf-8")
        # 查找 description
        has_desc = "description:" in content
        
        return TestAssertion(
            name="description 字段存在",
            description="YAML 头必须包含 description 字段",
            category="content",
            severity="high",
            passed=has_desc,
            message="✅ 包含 description" if has_desc else "❌ 缺少 description 字段"
        )
    
    @staticmethod
    def check_no_hardcoded_secrets(skill_path: Path) -> TestAssertion:
        """检查是否有硬编码的密钥"""
        patterns = [
            r'sk-[a-zA-Z0-9]{20,}',  # OpenAI style
            r'["\']api[_-]?key["\']\s*[:=]\s*["\'][^"\']{20,}["\']',  # API key assignments
            r'password\s*[:=]\s*["\'][^"\']+["\']',  # Passwords
            r'secret\s*[:=]\s*["\'][^"\']+["\']',  # Secrets
        ]
        
        issues = []
        for file_path in skill_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix in [".pyc", ".pyo", ".exe", ".bin", ".png", ".jpg", ".gif"]:
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8")
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        # 检查是否是环境变量读取模式
                        if "os.environ" not in content[:content.find(matches[0])]:
                            issues.append({
                                "file": str(file_path.relative_to(skill_path)),
                                "pattern": pattern,
                                "match": matches[0][:30] + "..."
                            })
            except:
                pass
        
        passed = len(issues) == 0
        return TestAssertion(
            name="无硬编码密钥",
            description="代码中不应包含硬编码的 API 密钥或密码",
            category="security",
            severity="critical",
            passed=passed,
            message="✅ 未发现硬编码密钥" if passed else f"❌ 发现 {len(issues)} 处潜在密钥",
            evidence=json.dumps(issues[:3], ensure_ascii=False) if issues else ""
        )
    
    @staticmethod
    def check_no_dangerous_commands(skill_path: Path) -> TestAssertion:
        """检查是否有危险命令"""
        dangerous_patterns = [
            r'rm\s+-rf\s+/',  # 删除根目录
            r'sudo\s+rm',  # sudo 删除
            r':(){ :|:& };:',  # Fork bomb
            r'dd\s+if=.*of=/dev/',  # 覆写设备
            r'mkfs',  # 格式化
            r'chmod\s+777\s+/',  # 开放权限
        ]
        
        issues = []
        for file_path in skill_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix in [".pyc", ".pyo", ".exe", ".bin"]:
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8")
                for pattern in dangerous_patterns:
                    if re.search(pattern, content):
                        issues.append({
                            "file": str(file_path.relative_to(skill_path)),
                            "pattern": pattern
                        })
            except:
                pass
        
        passed = len(issues) == 0
        return TestAssertion(
            name="无危险命令",
            description="代码中不应包含可能造成系统损害的命令",
            category="security",
            severity="critical",
            passed=passed,
            message="✅ 未发现危险命令" if passed else f"❌ 发现 {len(issues)} 处危险命令",
            evidence=json.dumps(issues[:3], ensure_ascii=False) if issues else ""
        )
    
    @staticmethod
    def check_scripts_have_docstrings(skill_path: Path) -> TestAssertion:
        """检查脚本是否有文档字符串"""
        scripts_dir = skill_path / "scripts"
        if not scripts_dir.exists():
            return TestAssertion(
                name="脚本有文档",
                description="Python 脚本应该包含模块级文档字符串",
                category="content",
                severity="medium",
                passed=True,
                message="✅ 无脚本目录"
            )
        
        py_files = list(scripts_dir.rglob("*.py"))
        if not py_files:
            return TestAssertion(
                name="脚本有文档",
                description="Python 脚本应该包含模块级文档字符串",
                category="content",
                severity="medium",
                passed=True,
                message="✅ 无 Python 脚本"
            )
        
        missing_docstring = []
        for py_file in py_files:
            content = py_file.read_text(encoding="utf-8")
            # 检查是否以 """ 或 ''' 开头的行（跳过空行和注释）
            lines = content.strip().split("\n")
            has_docstring = False
            for line in lines[:5]:  # 检查前 5 行
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    has_docstring = True
                    break
                if stripped and not stripped.startswith("#"):
                    break
            
            if not has_docstring:
                missing_docstring.append(str(py_file.relative_to(skill_path)))
        
        passed = len(missing_docstring) == 0
        return TestAssertion(
            name="脚本有文档",
            description="Python 脚本应该包含模块级文档字符串",
            category="content",
            severity="medium",
            passed=passed,
            message="✅ 所有脚本都有文档" if passed else f"⚠️ {len(missing_docstring)} 个脚本缺少文档",
            evidence=", ".join(missing_docstring[:3]) if missing_docstring else ""
        )
    
    @staticmethod
    def check_reasonable_file_sizes(skill_path: Path) -> TestAssertion:
        """检查文件大小是否合理"""
        large_files = []
        
        for file_path in skill_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > 10:  # 大于 10MB
                large_files.append({
                    "file": str(file_path.relative_to(skill_path)),
                    "size_mb": round(size_mb, 2)
                })
        
        passed = len(large_files) == 0
        return TestAssertion(
            name="文件大小合理",
            description="技能文件不应超过 10MB",
            category="structure",
            severity="medium",
            passed=passed,
            message="✅ 所有文件大小合理" if passed else f"⚠️ {len(large_files)} 个文件过大",
            evidence=json.dumps(large_files, ensure_ascii=False) if large_files else ""
        )
    
    @staticmethod
    def check_no_broken_links(skill_path: Path) -> TestAssertion:
        """检查 SKILL.md 中的内部链接"""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return TestAssertion(
                name="内部链接有效",
                description="SKILL.md 中引用的文件应该存在",
                category="content",
                severity="medium",
                passed=True,
                message="⚠️ 无法检查"
            )
        
        content = skill_md.read_text(encoding="utf-8")
        
        # 查找 markdown 链接
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        links = re.findall(link_pattern, content)
        
        broken_links = []
        for text, href in links:
            # 跳过外部链接
            if href.startswith("http://") or href.startswith("https://"):
                continue
            if href.startswith("#"):  # 锚点链接
                continue
            
            # 检查相对路径
            target = skill_path / href
            if not target.exists():
                broken_links.append(href)
        
        passed = len(broken_links) == 0
        return TestAssertion(
            name="内部链接有效",
            description="SKILL.md 中引用的文件应该存在",
            category="content",
            severity="medium",
            passed=passed,
            message="✅ 所有内部链接有效" if passed else f"⚠️ {len(broken_links)} 个链接断开",
            evidence=", ".join(broken_links[:5]) if broken_links else ""
        )
    
    @staticmethod
    def check_content_quality(skill_path: Path) -> TestAssertion:
        """检查内容质量（长度、结构）"""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return TestAssertion(
                name="内容质量",
                description="SKILL.md 应该有足够的内容和结构",
                category="content",
                severity="medium",
                passed=False,
                message="❌ 无法检查"
            )
        
        content = skill_md.read_text(encoding="utf-8")
        lines = content.split("\n")
        
        issues = []
        
        # 检查行数
        if len(lines) < 50:
            issues.append("内容过短（< 50 行）")
        
        # 检查标题结构
        h2_count = len([l for l in lines if l.startswith("## ")])
        if h2_count < 3:
            issues.append("二级标题过少（< 3 个）")
        
        # 检查代码示例
        code_blocks = content.count("```")
        if code_blocks < 2:
            issues.append("代码示例过少")
        
        passed = len(issues) == 0
        return TestAssertion(
            name="内容质量",
            description="SKILL.md 应该有足够的内容和结构",
            category="content",
            severity="medium",
            passed=passed,
            message="✅ 内容质量良好" if passed else f"⚠️ {', '.join(issues)}",
            evidence=f"行数: {len(lines)}, 二级标题: {h2_count}, 代码块: {code_blocks // 2}"
        )


def run_all_rules(skill_path: Path) -> List[TestAssertion]:
    """运行所有规则检查"""
    rules = [
        SkillRules.check_skill_md_exists,
        SkillRules.check_skill_md_has_yaml_header,
        SkillRules.check_name_field,
        SkillRules.check_description_field,
        SkillRules.check_no_hardcoded_secrets,
        SkillRules.check_no_dangerous_commands,
        SkillRules.check_scripts_have_docstrings,
        SkillRules.check_reasonable_file_sizes,
        SkillRules.check_no_broken_links,
        SkillRules.check_content_quality,
    ]
    
    assertions = []
    for rule in rules:
        try:
            result = rule(skill_path)
            assertions.append(result)
        except Exception as e:
            assertions.append(TestAssertion(
                name=rule.__name__,
                description="规则执行失败",
                category="error",
                severity="medium",
                passed=False,
                message=f"❌ 执行错误: {e}"
            ))
    
    return assertions


def calculate_score(assertions: List[TestAssertion]) -> float:
    """计算分数"""
    if not assertions:
        return 0.0
    
    weights = {
        "critical": 25,
        "high": 15,
        "medium": 10,
        "low": 5
    }
    
    total_weight = 0
    earned_weight = 0
    
    for assertion in assertions:
        weight = weights.get(assertion.severity, 10)
        total_weight += weight
        if assertion.passed:
            earned_weight += weight
    
    return (earned_weight / total_weight) * 100 if total_weight > 0 else 0


def run_rule_tests(skill_path: Path, verbose: bool = False) -> RuleTestResult:
    """运行规则测试"""
    assertions = run_all_rules(skill_path)
    
    passed = [a for a in assertions if a.passed]
    failed = [a for a in assertions if not a.passed]
    
    score = calculate_score(assertions)
    pass_rate = len(passed) / len(assertions) * 100 if assertions else 0
    
    # 判定
    critical_failed = [a for a in failed if a.severity == "critical"]
    if critical_failed:
        verdict = "fail"
    elif score >= 80:
        verdict = "pass"
    elif score >= 60:
        verdict = "warning"
    else:
        verdict = "fail"
    
    result = RuleTestResult(
        skill_name=skill_path.name,
        skill_path=str(skill_path),
        test_time=datetime.now().isoformat(),
        total_assertions=len(assertions),
        passed_assertions=len(passed),
        failed_assertions=len(failed),
        pass_rate=round(pass_rate, 1),
        assertions=[asdict(a) for a in assertions],
        score=round(score, 1),
        verdict=verdict
    )
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"📋 规则测试结果: {skill_path.name}")
        print(f"{'='*60}")
        
        for assertion in assertions:
            status = "✅" if assertion.passed else "❌"
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(assertion.severity, "⚪")
            print(f"{status} [{severity_icon} {assertion.severity}] {assertion.name}")
            print(f"   {assertion.message}")
            if assertion.evidence and not assertion.passed:
                print(f"   证据: {assertion.evidence[:100]}")
        
        print(f"\n{'='*60}")
        print(f"总断言数: {len(assertions)}")
        print(f"通过: {len(passed)} | 失败: {len(failed)}")
        print(f"通过率: {pass_rate:.1f}%")
        print(f"得分: {score:.1f}/100")
        print(f"判定: {verdict.upper()}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="基于规则的确定性测试")
    parser.add_argument("skill_path", help="技能目录路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    skill_path = Path(args.skill_path).expanduser().resolve()
    
    if not skill_path.exists():
        print(f"❌ 目录不存在: {skill_path}")
        sys.exit(1)
    
    result = run_rule_tests(skill_path, verbose=not args.json)
    
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    
    sys.exit(0 if result.verdict == "pass" else 1)


if __name__ == "__main__":
    main()
