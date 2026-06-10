---
name: feishu-schema-designer
origin: own
verified: 2026-04-16
version: "1.0.0"
description: "飞书多维表格应用架构师工作流剧本。从原始资料/自然语言需求到真实可用的飞书 base 应用的端到端编排：消化资料 → 推理设计 → 业务追问 → 程序化校验 → 业务效果预览 → 调用 lark-base 自动建表/字段/视图/工作流/仪表盘/表单/角色 → 文档化（调 lark-doc 写云文档手册）。当用户说『设计飞书多维表格应用 / 把这些资料变成飞书 base / 搭一个飞书[CRM/项目/库存]系统 / 用飞书多维表格落地这个需求 / 帮我设计一个 bitable 系统 / 飞书应用架构』时激活。**不替代** lark-base/lark-doc 的执行能力——本 skill 是设计层和编排层，CRUD 调用全部委托给 lark-* 系列 skill。"
metadata:
  category: feishu
  depends_on:
    - lark-base
    - lark-doc
    - lark-shared
    - lark-contact
  supersedes:
    - feishu-base-builder
---

# feishu-schema-designer

> **CRITICAL — 开始前 MUST 先用 Read 工具读取以下三份文件**（避免猜命令）：
> - [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md) — 认证、身份切换、scope 处理
> - [`../lark-base/SKILL.md`](../lark-base/SKILL.md) — 全部建表/字段/视图/工作流/仪表盘/表单/角色命令
> - [`../lark-doc/SKILL.md`](../lark-doc/SKILL.md) — Stage 7 写云文档用户手册

## 第一性原理

**Skill 本质**：给 agent（你）的工作流剧本，不是软件。零 scripts、零外部 LLM、零 prompts 文件——所有推理由你（agent）承担，所有执行委托给 lark-* skill。

**核心命题**：lark-base 已覆盖『有了 schema 怎么执行』，本 skill 覆盖『从需求/资料怎么推出 schema』。两者**单向依赖**：本 skill → lark-base / lark-doc。本 skill 不复制 lark-base 的命令细节；Stage 5 执行时以当前 lark-base/SKILL.md 和其 references 为唯一可信源。

**禁止**：
- ❌ 自己写代码调 lark-cli（必须切到 lark-base skill）
- ❌ 自己调外部 LLM API（你就是 LLM）
- ❌ 发明 lark-base 不认识的字段 / workflow / dashboard / role JSON key
- ❌ 擅自做 owner 转移（必须用户单独确认）

## 触发与边界

激活条件：用户提到搭建/设计飞书多维表格应用、bitable 系统、把资料变 base。

**不应触发**（应优先用其他 skill）：
- 单纯读写记录 → `lark-base` 直接处理
- 单独写飞书云文档 → `lark-doc` 直接处理
- 仅查通讯录 → `lark-contact` 直接处理

## 8 阶段工作流

每阶段产出落到用户的项目目录：`<project_dir>/feishu-design/<timestamp>_<slug>/`

| Stage | 名称 | 是否审批门 | 产出文件 |
|-------|------|-----------|---------|
| 0 | 资料消化 | ❌ 自动 | `00_resources_summary.md` |
| 1 | 方案推理 | ❌ 自动 | `01_requirement.md` + `02_schema_draft.json` + `03_open_questions.md` |
| 2 | **业务追问审批** | ✅ 用户回答开放问题 | 收敛 `01_requirement.md` |
| 3 | Schema 完整化 + 程序化校验 | ❌ 自动（失败自修复 ≤3 次） | `04_schema_final.json` + `05_validation_report.json` |
| 4 | **业务效果预览审批** | ✅ 用户批准应用预览 | `06_proposal.md` |
| 5 | 自动执行 | ❌ 自动（best-effort 回滚） | `07_execution_log.md` |
| 6 | 所有权处理 | ❌ 自动 | `08_handover.md` |
| 7 | 文档化 | ❌ 自动（调 lark-doc） | `09_user_manual.md` |

详细每阶段动作：[`references/design_methodology.md`](references/design_methodology.md)

### 设计硬门（阻断级 · 2026-06-10 落地 pending 变更9，源自 06-01→06-08 连续 5 个复盘窗口复发）

**第 0 步 — 核心实体基数关系确认（最高优先）**：输出任何 schema 草稿前，先列出全部核心实体对的基数关系（1:1 / 1:N / N:N，例："一张票据图片 = 一行记录 = 对应一笔费用"），每条标注出处：`[一手资料 <文件:位置>]` / `[用户确认 <日期>]` / `[待确认]`。**存在任何 [待确认] 的核心基数关系时，禁止进入 Stage 3 建表、禁止导数、禁止跑 OCR/批处理**——基数关系错 = 全表结构错，返工成本最高（2026-06-08 新民票据↔费用通宵返工实证）。Stage 2 业务追问必须把 [待确认] 基数关系列为第一组问题。

**维度出处门**：`02_schema_draft.json` 中每个表 / 一等维度 / 关键字段，必须在 `01_requirement.md` 能找到出处标注（一手资料行号 / 用户原话 / `[待确认]`）。无出处维度 = 现状捏造，禁止进入模型（feedback_cognitive_discipline §7：引入任何建模维度 = 现状陈述，须一手出处或标待确认）。

**设计四件套先于建表**：Stage 4 审批包必须四件齐备——①目标数据模型 ②数据流程 ③重构后系统交互 ④数据迁移方案——缺一不得进 Stage 5。"先建表填数、设计后补"是已知返工模式（2026-06-06 新民 19 表返工实证）。

### 关键阶段约束

**Stage 0**：资料量大时**必须用 subagent 读**（隔离 context）；但 subagent 的摘要**不能作为最终结论**——agent 必须亲自 Read 关键原文（特别是要引用/建模的具体表/流程/字段）。subagent 报告用于概览，不用于决策。

**Stage 1**：除了 `01_requirement.md` + `02_schema_draft.json` + `03_open_questions.md`，**新增强制产出** `01b_coverage_matrix.md`（角色×场景×生命周期矩阵）。矩阵未产出不得进 Stage 2。详见 [`references/coverage_audit.md`](references/coverage_audit.md)。

**Stage 0-1**：所有"能从资料推断"的部分直接产出，不能推断的标 `⚠️ 待确认` 进 `03_open_questions.md`。问题措辞用业务语言（不用 "外键"/"关联字段"等术语）。**必问非飞书用户角色**——详见 [`references/business_questioning_guide.md`](references/business_questioning_guide.md) § 非飞书用户角色识别。

**Stage 3**：schema.json 必须 100% 对齐 lark-base 期望格式。字段类型、workflow 节点、role 配置全部参照 [`references/schema_format_contract.md`](references/schema_format_contract.md)。

**Stage 4**：`06_proposal.md` 用业务语言展示『最终应用长什么样』——表/字段/视图/自动化/仪表盘/表单/角色全部用人话描述，**禁止出现 lark-cli 命令**。命令清单留到 `07_execution_log.md`。

**Stage 5**：严格按 [`references/execution_playbook.md`](references/execution_playbook.md) 编排顺序和当前 lark-base 约束执行。关键规则：先读真实结构；表/字段/视图/workflow/dashboard 名称和 ID 以命令返回为准；同表连续写入串行；批量记录单批最多 200 条。每步失败立即停下、记录、按 best-effort 回滚已建对象。

**Stage 6**：所有权处理见 [`references/ownership_transfer_runbook.md`](references/ownership_transfer_runbook.md)。优先 `--as user` 创建（用户即 owner，零额外步骤）；否则 `--as bot` 创建后给用户授 `full_access`。**不擅自转 owner**——除非用户明确要求。

**Stage 7**：调 lark-doc skill 写云文档用户手册。涉及"架构/流程/角色权限"等可视化语义时，按 lark-doc 规范主动用画板。

## 设计模式库

常见场景的 schema 推理模板：

- [`references/design_patterns/crm.md`](references/design_patterns/crm.md) — 客户管理（客户/联系人/订单/跟进记录/状态机）
- [`references/design_patterns/project_mgmt.md`](references/design_patterns/project_mgmt.md) — 项目管理（项目/任务/里程碑/工时/角色权限）
- [`references/design_patterns/inventory.md`](references/design_patterns/inventory.md) — 库存管理（SKU/批次/出入库/盘点/预警）

匹配现成模式时优先用，但仍需按用户具体业务调整。

## 跨 skill 编排约定

| 我的动作 | 调用方式 |
|---------|---------|
| 建 base/表/字段/视图/工作流/仪表盘/表单/角色 | 切到 `lark-base` skill 执行 |
| 查用户 open_id（Stage 6 授权用） | 调 `lark-cli contact +get-user`（lark-shared 范围内） |
| 写飞书云文档用户手册（Stage 7） | 切到 `lark-doc` skill 执行 |
| 涉及画板可视化 | lark-doc 内嵌 → 转 `lark-whiteboard-cli` |

切换时机：每个 Stage 5/6/7 进入前明确告诉用户『现在切到 lark-base / lark-doc 执行』。

## 不可违反规则（继承 lark-base 约束）

1. **先拿结构再写命令**——以当前 lark-base「Base 心智模型 / 写入前置规则」为准
2. **不猜表名/字段名**——一律以真实返回为准
3. **写字段前必读 `lark-base-field-json.md`；创建/更新命令细节读 `lark-base-field-create.md` / `lark-base-field-update.md`**
4. **写记录前必先 `+field-list`**
5. **workflow 必先读 `lark-base-workflow-guide.md` 和 `lark-base-workflow-schema.md`**
6. **公式/lookup 字段必先读对应 guide**
7. **dashboard 必先读 `lark-base-dashboard.md` 和 `dashboard-block-data-config.md`**
8. **owner 转移必须用户单独确认才执行**

## 常见错误与自检

- 用户给的是 wiki 链接 → 按当前 lark-base「Token 与链接」规则先 `wiki +node-get` 解析，**禁止**直接当 base_token
- bot 创建成功但用户看不到 → 检查是否完成 `--as bot` 给 user 授 `full_access`
- workflow 创建失败 → 必读 `lark-base-workflow-schema.md`，禁止凭自然语言猜 type
- formula/lookup 创建失败 → 必读对应 guide，guide 未读不得创建

## 旧 skill 关系

本 skill 取代 `feishu-base-builder`（CrewAI 多 Agent 版，2024 年末 / 2026-02-11 last_updated）。旧 skill 已归档至 `_deprecated/`。触发词覆盖旧 skill 的全部场景。

## Known Pitfalls

1. **二手转述 lark-base 内容** — 决不能凭印象引用 lark-base 命令；每次进入 Stage 5 必须先 Read lark-base 对应 reference
2. **Subagent 摘要当真相** —（2026-04-16 银杏家园实测三连犯）subagent 报告"已完成 X 工作流 Y 表 Z 字段"时，必须亲自 `jq` / `Read` 抽查实质内容，不能只看数量
3. **schema JSON key 自造名** —（2026-04-16 新增）workflow 用 `steps` 不是 `actions` / form 用 `questions` 不是 `fields` / dashboard block 用 `blocks` 不是 `widgets` / role 用 `role_name/role_type/base_rule_map/table_rule_map` 不是 `permissions` 数组。Stage 3 前必**亲自读** [`references/schema_format_contract.md`](references/schema_format_contract.md) 对照真实 key 名
4. **跳过角色×场景矩阵** —（2026-04-16 新增）按 5 维度并列推理会漏 20+ 角色交叉场景。Stage 1 必产出 `01b_coverage_matrix.md`，详见 [`references/coverage_audit.md`](references/coverage_audit.md)
5. **遗漏非飞书用户角色** —（2026-04-16 新增）站点端/外部用户通过表单+看板交互，他们的"上行通道"（C 场景）和"下行通道"（R 场景）必须显式建模为独立 Forms 和 Dashboard 分享链接
6. **审批门变命令清单** — Stage 4 审批的是『效果预览』（业务语言 + 按角色维度展示），不是命令清单。命令清单在 Stage 5 内部 dry-run
7. **Stage 4 按系统维度组织** —（2026-04-16 新增）按"表/视图/工作流"分节审批，用户难判断"我这个角色能干啥"。应按**角色维度**组织，每个角色一段完整故事
8. **跳过 Stage 0 资料消化** — 直接进 Stage 1 推理会遗漏用户已知信息，导致 Stage 2 反复追问已答问题
9. **执行前不切 skill** — 在 Stage 5 不切到 lark-base 直接自己拼 lark-cli 命令，等于放弃官方 reference 防错机制
10. **schema 字段类型用 lark-base 不认识的名字** — 业务层可用 `single_select` / `single_link` 等抽象，但 Stage 5 前必须按 `schema_format_contract.md` 转成当前 `lark-base-field-json.md` 认可的调用层 JSON；严禁直接把业务层 type 当 lark-cli 入参
11. **批量写记录不分批** — 单批超 **200 条**触发 1254104 错误（v1.0.13 实测确认，此前 reference 里的 500 已作废）
12. **list 命令并发** — `+table-list / +field-list / +record-list / +view-list` 等明确禁止并发，必须串行
13. **主字段用 auto_number 或内部序号** — 关联字段、单向/双向关联、表单视图、记录分享和 lookup 展示默认都看主字段。若第一列是 `auto_number`，跨表看到的就是"001/002/003"，业务用户无法识别对象。每张表第一列必须是对象/主体名称或主体可读标识（如客户名称、项目名称、站点名称、老人编号、订单号）；`auto_number` 若保留只能放第二列及以后。详见 [`references/schema_format_contract.md`](references/schema_format_contract.md) § 主字段设计规则
14. **Stage 4 审批让用户跳出对话读文件** —（2026-04-16 银杏家园实测暴露）proposal 只写进 `06_proposal.md` 然后让用户自己打开文件审阅是反模式。Stage 4 必须**把方案内容直接在对话里呈现**（完整角色故事 + 架构 + 校验结果 + 确认清单），文件只作留档。用户在对话里一次看完即可决定，不需要切窗口
15. **遇到 API 错误就借口"配额"/"context 收紧"放弃** —（2026-04-16 银杏家园实测暴露）首次 +role-create 失败"row quota limit"我直接打包成"租户限制需 UI 手动建"的借口；用户拷问后，深入排查发现根因是 `view_rule.allow_edit=false` 和 `other_record_all_read=true` 触发配额，而 `allow_edit=true` + `record_rule={}` 工作。同样模式：dashboard text block 失败、workflow 4 个失败 — 实际都是 schema 字段名差异（`text` vs `content` / `watched_field_name` 必填），不是真的不可建。**规则**：lark-cli API 错误必须**逐项排查**（最小可复现样本 → 比对成功配置 → 找出差异），禁止包装成"用户手动做"的甩锅。"放弃"必须是真正撞墙后的结论，不是遇阻就立刻退场
16. **schema_format_contract.md 字段类型映射 bug** —（2026-04-16 实测暴露）我列出的字段类型白名单（`single_select`/`single_link`/`property` 包装等）**完全是 Open API 概念名**，不是 lark-cli `+field-create --json` 的实际字段。lark-cli 真实用：`select`+`multiple` / `link`+`bidirectional` / `created_at`/`updated_at` / `style.type=phone/url/currency/progress/rating` 等扁平 + 嵌套 `style` 子对象格式。**已修**：schema_format_contract.md 已重写映射表 + 内置 transformer 模板
17. **凭过期 reference 下结论** — Stage 5 前必须先读当前环境中的 `lark-base/SKILL.md` 和本次涉及的 lark-base reference；命令缺少 reference 时读 `lark-cli base <command> --help`。涉及最新版本、配额、接口能力等易变事实时再联网核验，禁止依据旧 feishu-schema-designer 里的命令片段执行
18.5 **未确认基数关系就建表/导数** —（2026-06-08 新民通宵自主执行实测暴露）用户睡前下令无监督执行，Claude 在未确认"一张票据图 = 一行 = 一笔费用"这一核心基数关系的情况下建好表、导了数、跑了 OCR，醒来发现模型与业务实体不符，全量返工。**规则**：见上方「设计硬门」第 0 步——核心实体基数关系存在 [待确认] 时禁止建表/导数，无监督模式下宁可停在 Stage 2 等用户醒来，不可带病推进
19. **`lark-cli api <method> <path>` 万能透传** —（2026-04-17 联网发现）所有 lark-cli 未封装的飞书 OpenAPI 都可通过 `lark-cli api POST /open-apis/drive/v1/permissions/:token/public` 等直接调用。Stage 5 遇到"lark-cli 不支持"时先查 `lark-cli api --help`，禁止直接宣布"API 不可达"

## 参考文档

- [`references/design_methodology.md`](references/design_methodology.md) — 8 阶段每阶段详细动作 + 第一性原理领域建模法
- [`references/business_questioning_guide.md`](references/business_questioning_guide.md) — 业务友好追问模板（按场景分类）
- [`references/schema_format_contract.md`](references/schema_format_contract.md) — schema.json 格式契约（指向 lark-base reference 不复制）
- [`references/execution_playbook.md`](references/execution_playbook.md) — Stage 5 lark-base 命令编排顺序、依赖、批量约束
- [`references/ownership_transfer_runbook.md`](references/ownership_transfer_runbook.md) — Stage 6 所有权处理详细步骤
- [`references/design_patterns/`](references/design_patterns/) — CRM / 项目管理 / 库存等场景模式库
