# Stage 5 执行编排手册

> verified: 2026-04-16

Stage 5 自动建 base 时，按本文严格遵循的依赖顺序、批量约束、回滚规则。

## 进入 Stage 5 前必做

1. ✅ `04_schema_final.json` 通过 Stage 3 校验
2. ✅ `06_proposal.md` 已被用户批准
3. ✅ 当前会话中告知用户『现在切到 lark-base skill 执行建表，详细日志写入 07_execution_log.md』
4. ✅ 切换到 lark-base skill（用 Skill 工具）

## 预检清单（2026-04-16 实测加入，避免 Stage 5 中途阻塞）

**0. 联网验证铁律（2026-04-17 新增，Stage 5 第一步）**
- `lark-cli --version` 对比 https://github.com/larksuite/cli/releases 最新版；若版本差距 ≥1 minor → `npm install -g @larksuite/cli@latest`
- WebSearch 飞书多维表格「常见上限」+「高级权限常见问题」官方帮助文档（不信赖 skill 本地 reference 可能过期的配额数字）
- `lark-cli <domain> 2>&1` 穷举子命令，特别检查 `api`（通用透传，可调未封装的 OpenAPI）+ `drive permission.members` 等协作/分享相关
- 没做这 3 步就进 Stage 5 = 撞错会踩 v1.0.13 实测已修的坑 + 凭过期 reference 错判配额

**A. 表名禁忌字符**：飞书表名不能含 `/ \ ? * [ ] :`
- 先扫描所有 `tables[].name`，若含上述字符 **rename 后再建**（如「肖像/文案授权书」→「肖像文案授权书」）+ 全局替换 schema 内引用

**B. 业务层 → lark-cli 调用层 schema transformer**
- schema 中的 `single_select`/`single_link`/`property` 等业务层表达必须通过 transformer 转为 lark-cli 真实格式
- 详见 [`schema_format_contract.md`](schema_format_contract.md) § 字段类型映射表 + Transformer 模板

**C. 租户配额预检**
- `edit perm` 角色在 lark-cli API 层面**几乎必失败**（"row quota limit"），无论字段如何配置 — 这是飞书租户对 API 的硬限制
- `read_only` 角色 + `view_rule.allow_edit=true` + `record_rule={}` 是唯一稳定可建配置
- **决策**：5 个 edit 角色 → 跳过 lark-cli 直接给用户 UI 配置文档；只用 lark-cli 建 read_only 角色（如基金会脱敏角色）

**D. 团队成员 open_id 可访问性**
- 工作流的 `LarkMessageAction.receiver` 需要真实 open_id
- `lark-cli contact +search-user` 可能返回空（用户不在当前租户/scope 限制）
- **fallback**：用 owner 自己的 open_id 占位 → 工作流建成 disabled 状态 → 写入 handover 让用户 UI 改 receiver 后启用

**E. 主字段策略**
- 必须 `text` 或 `formula`（参考 `schema_format_contract.md` § 主字段设计规则）
- 若 schema 已是 auto_number primary，需要 `+field-update` 把 auto_number primary 转 formula（保留 ID 不变）

## lark-cli API 真实 schema 速查（2026-04-16 实测加入，与 lark-base reference 互补）

> 这些是实测过踩坑发现的，**不要凭官方文档上的示例字段名想当然**。

### Workflow（lark-base-workflow-create）
- 顶层 body 必传 `client_token`（任意唯一字符串如 `str(int(time.time()*1000000))`）
- `TimerTrigger.data`：`rule` ∈ NO_REPEAT/DAILY/WEEKLY/MONTHLY/YEARLY/WORKDAY/CUSTOM；MONTHLY 用 `sub_unit:[day]`；不是 `cron`
- `AddRecordTrigger.data`：必填 `table_name` + **`watched_field_name`**（缺则 800004006 validate error）
- `LarkMessageAction.data`：嵌套结构 `{receiver:[{value_type:"user",value:{id:"ou_xxx"}}], send_to_everyone:false, title:[{value_type:"text",value:"标题"}], content:[{value_type:"text",value:"正文"},{value_type:"ref",value:"$.step_id.fieldName"}], btn_list:[]}`
- 创建后 status 固定 `disabled`，需 `+workflow-enable` 启用

### Dashboard
- `+dashboard-create` 返回 `data.dashboard.dashboard_id`（不是 `data.id`）
- `+dashboard-block-create`：text block 用 `data_config={"text":"..."}`（**不是 `content`**）；其他类型用 `table_name`+`series`+`group_by`+`filter`

### Form
- `+form-create` 返回 `data.id`（直接在 data 下，不嵌套 form 子对象）
- `+form-questions-create` 一次最多 10 题；type 仅支持 `text/number/select/datetime/user/attachment/location`（无 `link`，引用 link 字段的题目要降级为 `text`）

### Role / advperm
- 必先 `+advperm-enable`（否则 role 创建无效）
- `view_rule` + `field_rule` + `record_rule` 三个**全是必填**（when perm != no_perm）
- **关键禁忌**：`view_rule.allow_edit=false` 触发租户配额；`record_rule.other_record_all_read=true` 也触发
- 安全配置（read_only）：`{"perm":"read_only","view_rule":{"allow_edit":true,"visibility":{"all_visible":true}},"field_rule":{"field_perm_mode":"all_read"},"record_rule":{}}`
- `+role-list` 返回 `data.data` 是**字符串化 JSON**，需要 `json.loads(d['data']['data'])['base_roles']` 二次解析

### Record
- `+record-upsert` 返回 `data.record.record_id_list[0]`
- link 字段格式：直接 `["recXXX"]` 字符串数组（不是 `[{"record_ids":[...]}]` 嵌套对象）

### 默认表 / 危险操作
- `+base-create` 自动创建 1 个默认"数据表"，**lark-cli `+table-delete` 拒绝删（unsafe_operation_blocked）**，需用户 UI 删
- `+advperm-disable` 也被 unsafe_operation_blocked，需 UI

## 执行依赖顺序（严格按此顺序，倒着回滚）

> **2026-04-16 实测优化**：`+table-create` 支持 `--fields` 和 `--view` 一次性传入，可在建表时同时建非关联字段和初始视图，**减少串行写入次数 + 规避 lark-base §4.3 批次间 0.5-1s 延迟约束**。

```
A. 创建 base
   └─ B. 一次性建每张表 + 该表所有非关联字段 + 该表初始视图
       （+table-create --fields '[...]' --view '[...]'）
       └─ C. 跨表创建关联字段（single_link / duplex_link，依赖目标表已存在）
           └─ D. 创建 formula / lookup 字段（依赖关联字段已建）
               └─ E. 视图细配（+view-set-filter / +view-set-sort 等，对已建视图做高级配置）
               └─ F. 启用 advperm + 创建角色（依赖表已建）
               └─ G. 创建表单 + 表单题目（依赖表已建）
               └─ H. 创建工作流（依赖字段已建）
               └─ I. 创建仪表盘 + 仪表盘组件（依赖字段已建）
```

为什么这个顺序：
- 关联字段在被关联表必须先存在，否则 `--target-table-id` 找不到
- formula/lookup 引用其他字段，其他字段必须先建
- 视图/角色/表单/工作流/仪表盘都引用字段名，字段必须先建

### B 阶段示例（一次建表 + 非关联字段 + 视图）

```bash
lark-cli base +table-create \
  --base-token <base_token> \
  --name "客户" \
  --fields '[
    {"name":"客户名称","type":"text","is_primary":true},
    {"name":"状态","type":"single_select","property":{"options":["进行中","已签约","流失"]}},
    {"name":"负责人","type":"user","property":{"multiple":false}},
    {"name":"创建时间","type":"created_time"}
  ]' \
  --view '[{"name":"客户总览","view_type":"grid"}]' \
  --as user
```

记录返回的 `table_id`，后续 C/D/E/F/G/H/I 阶段都用它。

## 每步通用规范

每个 lark-cli 命令执行时：

1. **必先读对应 reference**（lark-base SKILL.md 强制规则）
2. **`--dry-run` 验证语法**（lark-cli 内置）
3. **真执行**
4. **写入 `07_execution_log.md`**（命令/参数/返回/状态）
5. **失败立即停**，进入回滚流程

## 关键约束（来自 lark-base §4.3）

| 约束 | 说明 | 违反后果 |
|------|------|---------|
| list 命令禁并发 | `+table-list / +field-list / +record-list / +view-list / +record-history-list / +role-list / +dashboard-list / +dashboard-block-list / +workflow-list` 都必须串行 | 触发限流错误 |
| 批量记录 ≤ 200/批 | `+record-batch-create` / `+record-batch-update` 单批最多 **200 条**（lark-cli v1.0.13 起从 500 收紧到 200）| 错误码 1254104 |
| 同表连续写入串行 + 批次间 0.5-1s 延迟 | 防并发写冲突 | 错误码 1254291 |

## Stage 5.A — 创建 base

```
必读：lark-base/references/lark-base-base-create.md
必读：lark-base/references/lark-base-workspace.md
```

身份选择（依据 [`ownership_transfer_runbook.md`](ownership_transfer_runbook.md)）：
- 优先 `--as user` → 用户即 owner
- fallback `--as bot` → 后续 Stage 6 给用户授 full_access

记录返回的 `base_token` —— 后续所有命令都用它做 `--base-token`。

## Stage 5.B — 创建所有表

逐张表 `+table-create`（不能并发，按顺序）。记录每张表返回的 `table_id`，建立 `name -> table_id` 映射。

```
必读：lark-base/references/lark-base-table-create.md
```

## Stage 5.C — 创建非关联字段

按表逐个 `+field-create`（同表内串行）。

```
必读：lark-base/references/lark-base-field-create.md
必读：lark-base/references/lark-base-shortcut-field-properties.md
```

跳过：`single_link / duplex_link / formula / lookup / 系统字段`（C 阶段不建）。

## Stage 5.D — 创建关联字段

```
必读：lark-base/references/lark-base-shortcut-field-properties.md §single_link / §duplex_link
```

注意：双向关联建一边即可，反向字段自动出现，**不要重复建**。

## Stage 5.E — 创建 formula/lookup 字段

```
必读：lark-base/references/formula-field-guide.md（创建 formula 前）
必读：lark-base/references/lookup-field-guide.md（创建 lookup 前）
```

公式中引用的字段名必须精确匹配，否则 1254045。

## Stage 5.F — 创建视图

```
必读：lark-base/references/lark-base-view-create.md
```

创建视图后，按需配置：
- `+view-set-filter` （视图筛选）
- `+view-set-sort` （排序）
- `+view-set-group` （分组）
- `+view-set-visible-fields` （可见字段）
- `+view-set-card` / `+view-set-timebar` （特殊视图类型）

每条 `+view-set-*` 必先读对应 reference。

## Stage 5.G — 启用 advperm + 创建角色

```
必读：lark-base/references/lark-base-advperm-enable.md
必读：lark-base/references/lark-base-role-create.md
必读：lark-base/references/role-config.md
```

执行顺序：
1. `+advperm-enable`（必先启用，否则角色管理不生效）
2. 逐个 `+role-create`

注意 `+role-update` 是 Delta Merge——`role_name` 和 `role_type` 即使不改也必须传当前值。

## Stage 5.H — 创建表单 + 题目

```
必读：lark-base/references/lark-base-form-create.md
必读：lark-base/references/lark-base-form-questions-create.md
```

执行顺序：
1. `+form-create` 拿到 `form-id`
2. 逐个 `+form-questions-create`（按表单题目顺序）

## Stage 5.I — 创建工作流

```
必读：lark-base/references/lark-base-workflow-create.md
必读：lark-base/references/lark-base-workflow-schema.md（CRITICAL）
```

禁止凭自然语言猜 step type。每个 step 的 `type` 必须查 schema 文档。

创建后默认是禁用状态——按需 `+workflow-enable` 启用。

## Stage 5.J — 创建仪表盘 + 组件

```
必读：lark-base/references/lark-base-dashboard.md
必读：lark-base/references/lark-base-dashboard-create.md
必读：lark-base/references/lark-base-dashboard-block-create.md
必读：lark-base/references/dashboard-block-data-config.md
```

执行顺序：
1. `+dashboard-create` 拿到 `dashboard-id`
2. 逐个 `+dashboard-block-create`（每个图表组件单独）
3. 可选 `+dashboard-arrange` 调布局

## 失败回滚（best-effort）

任何步骤失败 → 立即停 → 按倒序回滚已建对象：

```
J 失败 → 删 dashboard-block / dashboard
I 失败 → 删 workflow
H 失败 → 删 form-questions / form
G 失败 → 删 role / disable advperm
F 失败 → 删 view
E 失败 → 删 formula/lookup field
D 失败 → 删 link field
C 失败 → 删 field
B 失败 → 删 table
A 失败 → 删 base（如已建）
```

回滚命令：
- `+dashboard-block-delete` / `+dashboard-delete`
- `+workflow-disable` 然后 `+workflow-update`（lark-base 1.2.0 暂无 +workflow-delete，需查最新版）
- `+form-questions-delete` / `+form-delete`
- `+role-delete` / `+advperm-disable`
- `+view-delete`
- `+field-delete`
- `+table-delete`
- base 删除走 `lark-cli drive +file-delete`（base 是 drive file 的一种）

回滚前先 `--dry-run` 看会删什么；回滚也写日志（`07_execution_log.md` 加 `## ROLLBACK` 章节）。

复杂回滚（删一半失败）→ 停下，把已建对象 + 删失败列表完整报告用户，等指示。

## 写入日志格式

`07_execution_log.md`：

```markdown
# 执行日志

## Stage 5.A - 创建 base
- 时间：2026-04-16 10:23:15
- 命令：lark-cli base +base-create --name "客户管理系统" --as user
- 状态：✅ 成功
- 返回：base_token=bascn...
- 链接：https://...

## Stage 5.B - 创建表
### 客户表
- 时间：...
- 命令：...
- 状态：✅
- 返回：table_id=tblxxx

### 订单表
- 时间：...
- 命令：...
- 状态：❌ 失败
- 错误：1254015 字段值类型不匹配
- 已停止后续步骤

## ROLLBACK
- 删除已建表 [客户表] - 命令 - 状态
- ...

## 最终状态
执行 12/45 步成功，13 步失败，13-45 步未执行。
回滚 11/12 成功（1 步回滚失败：客户表删除返回 403）。
请用户处理：base 中残留 1 张客户表 [https://...]
```
