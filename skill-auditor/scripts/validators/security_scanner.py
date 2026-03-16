#!/usr/bin/env python3
"""
Skill Auditor - 安全扫描器

检测 AI Agent Skills 中的潜在安全风险：
- Prompt Injection 检测
- 秘钥/密码泄露扫描
- 危险代码模式识别
- 数据外泄风险检测
- 权限过宽检查

Usage:
    python security_scanner.py <skill-path>
    
Returns:
    SecurityScanResult with findings and risk level
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "CRITICAL"  # 必须立即修复
    HIGH = "HIGH"          # 高风险，应尽快修复
    MEDIUM = "MEDIUM"      # 中等风险，建议修复
    LOW = "LOW"            # 低风险，可选修复
    INFO = "INFO"          # 信息提示


@dataclass
class SecurityFinding:
    """安全发现"""
    risk_level: RiskLevel
    category: str
    code: str
    message: str
    location: str
    line_number: Optional[int] = None
    matched_content: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class SecurityScanResult:
    """安全扫描结果"""
    passed: bool
    score: float  # 0-100
    risk_summary: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    scanned_files: list = field(default_factory=list)


# 安全检测规则
SECURITY_PATTERNS = {
    "prompt_injection": {
        "risk_level": RiskLevel.CRITICAL,
        "patterns": [
            (r"(?i)ignore\s+(previous|all|above)\s+instructions?", "忽略指令攻击"),
            (r"(?i)disregard\s+(your|all|previous)\s+", "忽略指令攻击"),
            (r"(?i)you\s+are\s+now\s+(?!going|about)", "角色覆盖攻击"),
            (r"(?i)forget\s+(everything|all|your)", "记忆清除攻击"),
            (r"(?i)new\s+instructions?:\s*", "指令注入"),
            (r"(?i)system\s*:\s*\n", "系统提示注入"),
            (r"(?i)\[SYSTEM\]", "系统提示注入"),
            (r"(?i)override\s+(?:your|the)\s+(?:rules?|instructions?)", "规则覆盖"),
            (r"(?i)jailbreak", "越狱尝试"),
            (r"(?i)DAN\s+mode", "DAN 模式攻击"),
        ],
        "remediation": "移除或重写包含可能被解释为指令的文本"
    },
    "secrets": {
        "risk_level": RiskLevel.CRITICAL,
        "patterns": [
            (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][^'\"]{10,}['\"]", "API Key 泄露"),
            (r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*['\"][^'\"]{10,}['\"]", "Secret Key 泄露"),
            (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]+['\"]", "密码泄露"),
            (r"(?i)(token|auth_token|access_token)\s*[=:]\s*['\"][^'\"]{20,}['\"]", "Token 泄露"),
            (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
            (r"sk-proj-[a-zA-Z0-9]{48,}", "OpenAI Project API Key"),
            (r"xoxb-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{24}", "Slack Bot Token"),
            (r"xoxp-[0-9]{10,}-[0-9]{10,}-[0-9]{10,}-[a-f0-9]{32}", "Slack User Token"),
            (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
            (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
            (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer Token"),
            (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "私钥泄露"),
            (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
        ],
        "remediation": "从代码中移除敏感信息，使用环境变量或安全的密钥管理服务"
    },
    "dangerous_code": {
        "risk_level": RiskLevel.HIGH,
        "patterns": [
            (r"\beval\s*\(", "危险的 eval() 调用"),
            (r"\bexec\s*\(", "危险的 exec() 调用"),
            (r"subprocess\.(?:run|call|Popen)\s*\([^)]*shell\s*=\s*True", "危险的 shell=True"),
            (r"os\.system\s*\(", "危险的 os.system() 调用"),
            (r"rm\s+-rf\s+[/~]", "危险的 rm -rf 命令"),
            (r"shutil\.rmtree\s*\(\s*['\"][/~]", "危险的目录删除"),
            (r"os\.remove\s*\(\s*['\"][/~]", "危险的文件删除"),
            (r"chmod\s+777", "不安全的权限设置"),
            (r"(?i)curl\s+.*\|\s*(?:bash|sh)", "危险的管道执行"),
            (r"(?i)wget\s+.*\|\s*(?:bash|sh)", "危险的管道执行"),
            (r"__import__\s*\(", "动态导入"),
            (r"compile\s*\([^)]+,\s*['\"]exec['\"]", "动态代码编译"),
        ],
        "remediation": "使用更安全的替代方法，添加输入验证和沙箱保护"
    },
    "data_exfiltration": {
        "risk_level": RiskLevel.HIGH,
        "patterns": [
            (r"requests\.(?:get|post|put|delete)\s*\(\s*['\"]https?://[^'\"]+", "HTTP 请求到外部 URL"),
            (r"urllib\.request\.urlopen\s*\(", "URL 请求"),
            (r"httpx\.[a-z]+\s*\(", "HTTPX 请求"),
            (r"aiohttp\.ClientSession", "异步 HTTP 客户端"),
            (r"(?i)fetch\s*\(\s*['\"]https?://", "Fetch 请求到外部 URL"),
            (r"socket\.(?:connect|sendto)\s*\(", "原始 Socket 连接"),
            (r"smtplib\.SMTP", "邮件发送"),
            (r"paramiko\.SSHClient", "SSH 连接"),
        ],
        "remediation": "确保外部请求是必要的，添加 URL 白名单验证"
    },
    "file_operations": {
        "risk_level": RiskLevel.MEDIUM,
        "patterns": [
            (r"open\s*\(\s*['\"][/~](?:etc|root|home)", "访问敏感目录"),
            (r"Path\s*\(\s*['\"][/~](?:etc|root|home)", "访问敏感目录"),
            (r"(?i)\.env['\"]?\s*\)", "读取 .env 文件"),
            (r"(?i)config\.(?:json|yaml|yml|ini)['\"]", "读取配置文件"),
            (r"sqlite3\.connect", "SQLite 数据库操作"),
            (r"pickle\.(?:load|loads)", "不安全的 Pickle 反序列化"),
            (r"yaml\.(?:load|unsafe_load)\s*\([^)]*(?!Loader)", "不安全的 YAML 加载"),
        ],
        "remediation": "限制文件操作路径，使用安全的反序列化方法"
    },
    "permission_issues": {
        "risk_level": RiskLevel.MEDIUM,
        "patterns": [
            (r"allowed-tools:\s*\*", "允许所有工具"),
            (r"allowed-tools:.*run_command", "允许执行命令"),
            (r"allowed-tools:.*write_to_file", "允许写入文件（检查范围）"),
            (r"(?i)sudo\s+", "sudo 权限提升"),
            (r"(?i)as\s+root", "root 权限"),
        ],
        "remediation": "遵循最小权限原则，仅授予必要的工具权限"
    },
}


def scan_content(content: str, file_path: str) -> list[SecurityFinding]:
    """扫描内容中的安全问题"""
    findings = []
    lines = content.split("\n")
    
    for category, config in SECURITY_PATTERNS.items():
        risk_level = config["risk_level"]
        remediation = config.get("remediation", "")
        
        for pattern, description in config["patterns"]:
            for line_num, line in enumerate(lines, 1):
                matches = re.finditer(pattern, line)
                for match in matches:
                    # 避免在注释中误报
                    line_stripped = line.strip()
                    if line_stripped.startswith("#") and category != "secrets":
                        continue
                    
                    # 截取匹配内容（隐藏敏感部分）
                    matched = match.group(0)
                    if category == "secrets" and len(matched) > 20:
                        matched = matched[:10] + "..." + matched[-5:]
                    
                    findings.append(SecurityFinding(
                        risk_level=risk_level,
                        category=category,
                        code=f"SEC-{category.upper()[:3]}-{len(findings)+1:03d}",
                        message=description,
                        location=file_path,
                        line_number=line_num,
                        matched_content=matched,
                        remediation=remediation
                    ))
    
    return findings


def scan_skill(skill_path: str, exclude_patterns: list = None) -> SecurityScanResult:
    """
    执行完整的安全扫描
    
    Args:
        skill_path: 技能目录路径
        exclude_patterns: 要排除的文件模式列表（如 ['references/*', '*.example.*']）
        
    Returns:
        SecurityScanResult 包含扫描结果
    """
    exclude_patterns = exclude_patterns or []
    
    # 默认排除的目录和文件模式
    default_excludes = [
        'venv/*', '.venv/*', 'env/*', '.env/*',
        'node_modules/*',
        '__pycache__/*', '*.pyc',
        '.git/*',
        '.tox/*', '.nox/*',
        'dist/*', 'build/*', '*.egg-info/*',
    ]
    all_excludes = default_excludes + exclude_patterns
    
    skill_dir = Path(skill_path).resolve()
    findings = []
    scanned_files = []
    
    if not skill_dir.exists():
        return SecurityScanResult(
            passed=False,
            score=0,
            findings=[SecurityFinding(
                risk_level=RiskLevel.CRITICAL,
                category="system",
                code="SEC-SYS-001",
                message=f"目录不存在: {skill_dir}",
                location=str(skill_dir)
            )]
        )
    
    # 扫描所有相关文件
    scan_extensions = {".md", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml"}
    
    for file_path in skill_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in scan_extensions:
            rel_path = str(file_path.relative_to(skill_dir))
            
            # 检查是否应排除
            should_exclude = False
            for pattern in all_excludes:
                if '*' in pattern:
                    # 简单 glob 匹配
                    import fnmatch
                    if fnmatch.fnmatch(rel_path, pattern):
                        should_exclude = True
                        break
                elif pattern in rel_path:
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
                    
            scanned_files.append(rel_path)
            
            try:
                content = file_path.read_text(encoding="utf-8")
                file_findings = scan_content(content, rel_path)
                findings.extend(file_findings)
            except Exception as e:
                findings.append(SecurityFinding(
                    risk_level=RiskLevel.LOW,
                    category="system",
                    code="SEC-SYS-002",
                    message=f"无法读取文件: {e}",
                    location=rel_path
                ))
    
    # 统计风险分布
    risk_summary = {
        RiskLevel.CRITICAL.value: 0,
        RiskLevel.HIGH.value: 0,
        RiskLevel.MEDIUM.value: 0,
        RiskLevel.LOW.value: 0,
        RiskLevel.INFO.value: 0,
    }
    
    for finding in findings:
        risk_summary[finding.risk_level.value] += 1
    
    # 计算得分
    # CRITICAL=-25, HIGH=-15, MEDIUM=-5, LOW=-2
    score = max(0, 100 
                - risk_summary[RiskLevel.CRITICAL.value] * 25
                - risk_summary[RiskLevel.HIGH.value] * 15
                - risk_summary[RiskLevel.MEDIUM.value] * 5
                - risk_summary[RiskLevel.LOW.value] * 2)
    
    # 如果有 CRITICAL 或 HIGH 级别问题，则不通过
    passed = (risk_summary[RiskLevel.CRITICAL.value] == 0 and 
              risk_summary[RiskLevel.HIGH.value] == 0)
    
    return SecurityScanResult(
        passed=passed,
        score=score,
        risk_summary=risk_summary,
        findings=findings,
        scanned_files=scanned_files
    )


def format_report(result: SecurityScanResult) -> str:
    """格式化安全扫描报告"""
    lines = []
    lines.append("=" * 70)
    lines.append("安全扫描报告")
    lines.append("=" * 70)
    lines.append(f"扫描文件数: {len(result.scanned_files)}")
    lines.append(f"发现问题数: {len(result.findings)}")
    lines.append("-" * 70)
    lines.append("风险分布:")
    
    risk_icons = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🔵",
        "INFO": "⚪",
    }
    
    for level, count in result.risk_summary.items():
        icon = risk_icons.get(level, "⚪")
        lines.append(f"  {icon} {level}: {count}")
    
    lines.append("-" * 70)
    lines.append(f"安全评分: {result.score:.1f}/100")
    lines.append(f"扫描结果: {'✅ 通过' if result.passed else '❌ 不通过'}")
    lines.append("-" * 70)
    
    if result.findings:
        lines.append("详细发现:")
        
        # 按风险等级排序
        sorted_findings = sorted(
            result.findings,
            key=lambda f: ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].index(f.risk_level.value)
        )
        
        for finding in sorted_findings:
            icon = risk_icons.get(finding.risk_level.value, "⚪")
            lines.append(f"\n  {icon} [{finding.code}] {finding.risk_level.value}")
            lines.append(f"     类别: {finding.category}")
            lines.append(f"     问题: {finding.message}")
            lines.append(f"     位置: {finding.location}" + 
                        (f":{finding.line_number}" if finding.line_number else ""))
            if finding.matched_content:
                lines.append(f"     匹配: {finding.matched_content}")
            if finding.remediation:
                lines.append(f"     💡 建议: {finding.remediation}")
    else:
        lines.append("✨ 未发现安全问题")
    
    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python security_scanner.py <skill-path>")
        print("\nExample:")
        print("  python security_scanner.py ./my-skill")
        sys.exit(1)
    
    skill_path = sys.argv[1]
    result = scan_skill(skill_path)
    print(format_report(result))
    
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
