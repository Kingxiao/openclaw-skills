#!/usr/bin/env bash
# =============================================================================
# validate-skill.sh — Skill 结构与质量自动化验证脚本
#
# 用法: bash validate-skill.sh <skill-directory>
# 示例: bash validate-skill.sh zig-enterprise-skill
#       bash validate-skill.sh skill-forge
#
# 返回码: 0 = 全部通过, 1 = 存在 FAIL 项
# =============================================================================
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# 颜色定义
# ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ─────────────────────────────────────────────────────────────
# 帮助
# ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || -z "${1:-}" ]]; then
    echo "用法: bash validate-skill.sh <skill-directory>"
    echo ""
    echo "验证一个 Skill 目录的结构和内容质量。"
    echo "skill-directory 应为 skills/ 仓库内的目录名或路径。"
    echo ""
    echo "示例:"
    echo "  bash validate-skill.sh zig-enterprise-skill"
    echo "  bash validate-skill.sh ./skill-forge"
    echo "  bash validate-skill.sh /absolute/path/to/my-skill"
    exit 0
fi

# ─────────────────────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────────────────────
SKILL_DIR="${1}"
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() {
    echo -e "  ${GREEN}✅ PASS${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "  ${RED}❌ FAIL${NC} $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
    echo -e "  ${YELLOW}⚠️  WARN${NC} $1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

info() {
    echo -e "  ${CYAN}ℹ️  INFO${NC} $1"
}

# ─────────────────────────────────────────────────────────────
# 检查目标目录
# ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Skill 验证: ${CYAN}${SKILL_DIR}${NC}"
echo -e "${BOLD}════════════════════════════════════════════════${NC}"
echo ""

if [[ ! -d "${SKILL_DIR}" ]]; then
    echo -e "${RED}错误: 目录 '${SKILL_DIR}' 不存在${NC}"
    exit 1
fi

SKILL_MD="${SKILL_DIR}/SKILL.md"
DIR_NAME=$(basename "${SKILL_DIR}")

# ─────────────────────────────────────────────────────────────
# A. 结构检查
# ─────────────────────────────────────────────────────────────
echo -e "${BOLD}[A] 结构完整性${NC}"

# A1: SKILL.md 存在
if [[ -f "${SKILL_MD}" ]]; then
    pass "SKILL.md 文件存在"
else
    fail "[CRITICAL] SKILL.md 文件不存在"
    echo -e "\n${RED}无法继续验证。请创建 SKILL.md 后重试。${NC}"
    exit 1
fi

# A2: YAML frontmatter 存在
FIRST_LINE=$(head -n 1 "${SKILL_MD}")
if [[ "${FIRST_LINE}" == "---" ]]; then
    pass "YAML frontmatter 开始标记存在"
else
    fail "[CRITICAL] SKILL.md 未以 '---' 开头（无 YAML frontmatter）"
fi

# A3: YAML frontmatter 正确闭合
FRONTMATTER_END=$(awk '/^---$/{n++; if(n==2){print NR; exit}}' "${SKILL_MD}")
if [[ -n "${FRONTMATTER_END}" ]]; then
    pass "YAML frontmatter 正确闭合 (第 ${FRONTMATTER_END} 行)"
else
    fail "[CRITICAL] YAML frontmatter 未正确闭合（找不到第二个 ---）"
fi

# A4: name 字段存在
SKILL_NAME=$(sed -n '2,'"${FRONTMATTER_END:-99}"'p' "${SKILL_MD}" | grep -E "^name:" | head -1 | sed 's/^name:[[:space:]]*//' || true)
if [[ -n "${SKILL_NAME}" ]]; then
    pass "name 字段存在: '${SKILL_NAME}'"
else
    fail "[CRITICAL] name 字段缺失"
    SKILL_NAME=""
fi

# A5: name 格式合规
if [[ -n "${SKILL_NAME}" ]]; then
    if echo "${SKILL_NAME}" | grep -qE '^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$'; then
        pass "name 格式合规 (kebab-case)"
    else
        fail "name 格式不合规: '${SKILL_NAME}' (必须为 kebab-case [a-z0-9-])"
    fi

    # A6: name 长度
    NAME_LEN=${#SKILL_NAME}
    if (( NAME_LEN <= 64 )); then
        pass "name 长度合规: ${NAME_LEN}/64 字符"
    else
        fail "name 超长: ${NAME_LEN}/64 字符"
    fi

    # A7: name 与目录名一致
    if [[ "${SKILL_NAME}" == "${DIR_NAME}" ]]; then
        pass "name 与目录名一致"
    else
        warn "name '${SKILL_NAME}' 与目录名 '${DIR_NAME}' 不一致"
    fi

    # A8: name 不含保留词
    if echo "${SKILL_NAME}" | grep -qiE '(anthropic|claude|openai|gemini|copilot|gpt)'; then
        fail "name 包含保留词"
    else
        pass "name 不含保留词"
    fi
fi

# A9: description 字段存在
DESC=$(sed -n '2,'"${FRONTMATTER_END:-99}"'p' "${SKILL_MD}" | grep -E "^description:" | head -1 || true)
if [[ -n "${DESC}" ]]; then
    pass "description 字段存在"
else
    fail "[CRITICAL] description 字段缺失"
fi

echo ""

# ─────────────────────────────────────────────────────────────
# B. 内容检查
# ─────────────────────────────────────────────────────────────
echo -e "${BOLD}[B] 内容质量${NC}"

# B1: 总行数
TOTAL_LINES=$(wc -l < "${SKILL_MD}")
BODY_START=${FRONTMATTER_END:-3}
BODY_LINES=$((TOTAL_LINES - BODY_START))

if (( BODY_LINES <= 500 )); then
    pass "Body 行数合规: ${BODY_LINES}/500 行"
else
    fail "Body 行数超限: ${BODY_LINES}/500 行"
fi

info "SKILL.md 总行数: ${TOTAL_LINES}"

# B2: Known Pitfalls 章节
if grep -qiE '(known pitfalls|已知陷阱|known issues|pitfalls|常见陷阱|反模式速查)' "${SKILL_MD}"; then
    pass "包含 Known Pitfalls / 已知陷阱章节"
else
    fail "缺少 Known Pitfalls / 已知陷阱章节"
fi

# B3: 代码示例存在
CODE_BLOCKS=$(grep -c '```' "${SKILL_MD}" || true)
CODE_PAIRS=$((CODE_BLOCKS / 2))
if (( CODE_PAIRS >= 1 )); then
    pass "包含代码示例 (${CODE_PAIRS} 个代码块)"
else
    warn "无代码示例。如果是纯方法论 skill 可以忽略"
fi

echo ""

# ─────────────────────────────────────────────────────────────
# C. 安全检查
# ─────────────────────────────────────────────────────────────
echo -e "${BOLD}[C] 安全性${NC}"

# C1: 无明文密钥模式
SECRETS_PATTERNS='(api[_-]?key|api[_-]?secret|password|passwd|secret[_-]?key|private[_-]?key|access[_-]?token)[[:space:]]*[:=][[:space:]]*["\x27][^"\x27]{8,}'
if grep -qiE "${SECRETS_PATTERNS}" "${SKILL_MD}" 2>/dev/null; then
    fail "[CRITICAL] 疑似包含硬编码密钥/密码"
else
    pass "未检测到硬编码密钥/密码"
fi

# C2: 检查 references 中的密钥
if [[ -d "${SKILL_DIR}/references" ]]; then
    REFS_SECRET=0
    for ref_file in "${SKILL_DIR}"/references/*.md; do
        [[ -f "${ref_file}" ]] || continue
        if grep -qiE "${SECRETS_PATTERNS}" "${ref_file}" 2>/dev/null; then
            fail "references/$(basename "${ref_file}") 疑似包含硬编码密钥"
            REFS_SECRET=1
        fi
    done
    if (( REFS_SECRET == 0 )); then
        pass "references/ 文件未检测到硬编码密钥"
    fi
fi

# C3: 危险命令检查
if grep -qE '(rm\s+-rf\s+/[^.]|DROP\s+DATABASE|FORMAT\s+C:|mkfs\.)' "${SKILL_MD}" 2>/dev/null; then
    warn "包含潜在危险命令，请确认已添加适当警告"
else
    pass "未检测到裸露的危险命令"
fi

echo ""

# ─────────────────────────────────────────────────────────────
# D. 引用完整性
# ─────────────────────────────────────────────────────────────
echo -e "${BOLD}[D] 引用完整性${NC}"

# D1: 检查 SKILL.md 中引用的 references/ 文件是否存在
REF_LINKS=$(grep -oE 'references/[a-zA-Z0-9_-]+\.md' "${SKILL_MD}" 2>/dev/null | sort -u || true)
if [[ -n "${REF_LINKS}" ]]; then
    ALL_REFS_FOUND=1
    while IFS= read -r ref; do
        if [[ -f "${SKILL_DIR}/${ref}" ]]; then
            pass "引用文件存在: ${ref}"
        else
            fail "引用文件缺失: ${ref}"
            ALL_REFS_FOUND=0
        fi
    done <<< "${REF_LINKS}"
else
    info "SKILL.md 中未发现 references/ 引用"
fi

# D2: references/ 目录存在性
if [[ -d "${SKILL_DIR}/references" ]]; then
    REF_COUNT=$(find "${SKILL_DIR}/references" -name "*.md" -type f | wc -l)
    info "references/ 目录包含 ${REF_COUNT} 个 .md 文件"
fi

echo ""

# ─────────────────────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────────────────────
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo -e "${BOLD}════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  验证结果汇总${NC}"
echo -e "${BOLD}════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}PASS${NC}: ${PASS_COUNT}"
echo -e "  ${RED}FAIL${NC}: ${FAIL_COUNT}"
echo -e "  ${YELLOW}WARN${NC}: ${WARN_COUNT}"
echo -e "  总计: ${TOTAL} 项检查"
echo ""

if (( FAIL_COUNT == 0 )); then
    echo -e "  ${GREEN}${BOLD}✅ 验证通过！Skill 符合质量标准。${NC}"
    echo ""
    exit 0
else
    echo -e "  ${RED}${BOLD}❌ 验证未通过。请修复上述 FAIL 项后重试。${NC}"
    echo ""
    exit 1
fi
