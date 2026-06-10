# Stage 5 执行编排手册

> verified: 2026-06-10（与 lark-base v1.2.2 协同）

Stage 5 自动建 base 时，按本文严格遵循的依赖顺序、批量约束、回滚规则。

## 进入 Stage 5 前必做

1. ✅ `04_schema_final.json` 通过 Stage 3 校验
2. ✅ `06_proposal.md` 已被用户批准
3. ✅ 当前会话中告知用户『现在切到 lark-base skill 执行建表，详细日志写入 07_execution_log.md』
4. ✅ 切换到 lark-base skill（用 Skill 工具）

## 预检清单（2026-04-16 实测加入，避免 Stage 5 中途阻塞）

**0. lark-base 同步铁律（Stage 5 第一步）**
- 先读当前 `../lark-base/SKILL.md`，按它的「快速路由 / 写入前置规则 / Token 与链接 / 常见恢复」执行。
- 本文件不作为 lark-cli 参数 SSOT；字段、记录值、workflow、dashboard、role 等复杂 JSON 必须回查 lark-base 对应 reference。
- 某个命令没有专门 reference 时，以 `lark-cli base <command> --help` 和当前 lark-base/SKILL.md 的路由说明为准。
- 涉及最新版、平台配额、API 能力、产品规则等易变事实时，再联网核验官方资料或版本发布信息。

**A. 表名禁忌字符**：飞书表名不能含 `/ \ ? * [ ] :`
- 先扫描所有 `tables[].name`，若含上述字符 **rename 后再建**（如「肖像/文案授权书」→「肖像文案授权书」）+ 全局替换 schema 内引用

**B. 业务层 → lark-base 调用层 schema transformer**
- schema 中的 `single_select`/`single_link`/`property` 等业务层表达必须通过 transformer 转为当前 lark-base 真实 field JSON
- 详见 [`schema_format_contract.md`](schema_format_contract.md) § 字段类型映射表 + Transformer 模板

**C. 高级权限预检**
- 创建/更新角色前必须读 `lark-base-role-guide.md` 和 `role-config.md`。
- `+role-create` 只创建自定义角色；系统角色不能删除，更新前先 `+role-get`。
- 如果 API 返回配额或权限错误，按当前 lark-base 的常见恢复和最小可复现方式排查；不要把旧实测中的某个租户限制当成全局规则。

**D. 团队成员 open_id 可访问性**
- 工作流的 `LarkMessageAction.receiver` 需要真实 open_id
- `lark-cli contact +search-user` 可能返回空（用户不在当前租户/scope 限制）
- **fallback**：用 owner 自己的 open_id 占位 → 工作流建成 disabled 状态 → 写入 handover 让用户 UI 改 receiver 后启用

**E. 主字段策略**
- 每张表第一列必须是对象/主体名称或主体可读标识（参考 `schema_format_contract.md` § 主字段设计规则）。
- 禁止 `auto_number` 作 primary 或第一列；若 schema 已是 auto_number primary，先改为主体名称字段或新增 formula 主字段，再把 auto_number 降为第二列及以后。
- 执行前抽查所有 link 目标表：关联列显示的主字段必须让业务用户一眼知道关联的是哪个对象。

## 历史踩坑提醒（不替代 lark-base reference）

> 以下只是历史排错线索。执行前必须以当前 lark-base reference 和 `--help` 为准，不得直接复制本节片段作为命令参数。

### Workflow
- 创建/更新 workflow 前读 `lark-base-workflow-guide.md` 和 `lark-base-workflow-schema.md`；不要凭自然语言猜 step type、ref 语法或 data 结构。

### Dashboard
- 创建/更新 dashboard block 前读 `lark-base-dashboard.md` 和 `dashboard-block-data-config.md`；读取图表计算结果用 `lark-base-dashboard-block-get-data.md`。

### Form
- 表单题目创建/更新读 `lark-base-form-questions-create.md` / `lark-base-form-questions-update.md`；提交读 `lark-base-form-detail.md` 和 `lark-base-form-submit.md`。

### Role / advperm
- 角色 JSON 以 `role-config.md` 为准；`+role-create` 只支持自定义角色，`+role-update` 是 delta merge。

### Record
- 写记录前读 `lark-base-cell-value.md`；附件走专用 attachment 命令，不作为普通 CellValue 写入。

### 默认表 / 危险操作
- 删除、角色更新、字段更新、关闭高级权限等高风险操作遵循当前 CLI confirmation gate；目标不明确时先 list/get 消歧。

## 执行依赖顺序（严格按此顺序，倒着回滚）

> 可用 `+table-create` 创建表；若当前 CLI 支持 `--fields` / `--view`，可在建表时带入已转换好的非关联字段和初始视图。是否支持、参数格式以 `lark-cli base +table-create --help` 为准。

```
A. 创建 base
   └─ B. 一次性建每张表 + 该表所有非关联字段 + 该表初始视图
       （+table-create --fields '[...]' --view '[...]'）
       └─ C. 跨表创建关联字段（single_link / duplex_link，依赖目标表已存在）
           └─ D. 创建 formula / lookup 字段（依赖关联字段已建）
               └─ E. 视图细配（filter 用 +view-set-filter；其他视图配置先 get 现状再按当前 CLI 更新）
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
    {"name":"状态","type":"select","multiple":false,"options":[{"name":"进行中","hue":"Blue","lightness":"Lighter"},{"name":"已签约","hue":"Green","lightness":"Light"},{"name":"流失","hue":"Gray","lightness":"Lighter"}]},
    {"name":"负责人","type":"user","multiple":false},
    {"name":"创建时间","type":"created_at"}
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

注意：当前 `lark-cli base +table-create --dry-run` 可能只展示建表主体请求，不展开 `--fields` / `--view` 的后续请求。使用 `+table-create --fields` 前，必须先把字段数组按 `lark-base-field-json.md` 转换，并用以下方式至少做一种验证：
- 对每类字段抽样运行 `+field-create --dry-run`，确认请求体没有业务层 type / `property` 泄漏；
- 或运行本地 schema transformer 校验，确认第一列主字段、link 目标表、字段 type 和 JSON key 全部符合当前 lark-base。

## 关键约束（来自当前 lark-base）

| 约束 | 说明 | 违反后果 |
|------|------|---------|
| list 命令禁并发 | `+table-list / +field-list / +record-list / +view-list / +record-history-list / +role-list / +dashboard-list / +dashboard-block-list / +workflow-list` 都必须串行 | 触发限流错误 |
| 批量记录 ≤ 200/批 | `+record-batch-create` / `+record-batch-update` 单批最多 **200 条**（lark-cli v1.0.13 起从 500 收紧到 200）| 错误码 1254104 |
| 同表连续写入串行 + 批次间 0.5-1s 延迟 | 防并发写冲突 | 错误码 1254291 |

## Stage 5.A — 创建 base

```
必读：../lark-base/SKILL.md 的「快速路由」「身份与权限降级」
必要时读：lark-cli base +base-create --help
```

身份选择（依据 [`ownership_transfer_runbook.md`](ownership_transfer_runbook.md)）：
- 优先 `--as user` → 用户即 owner
- fallback `--as bot` → 后续 Stage 6 给用户授 full_access

记录返回的 `base_token` —— 后续所有命令都用它做 `--base-token`。

## Stage 5.B — 创建所有表

逐张表 `+table-create`（不能并发，按顺序）。记录每张表返回的 `table_id`，建立 `name -> table_id` 映射。

```
必读：../lark-base/SKILL.md 的「快速路由」
必要时读：lark-cli base +table-create --help
```

## Stage 5.C — 创建非关联字段

按表逐个 `+field-create`（同表内串行）。

```
必读：lark-base/references/lark-base-field-create.md
必读：lark-base/references/lark-base-field-json.md
```

跳过：`single_link / duplex_link / formula / lookup / 系统字段`（C 阶段不建）。

## Stage 5.D — 创建关联字段

```
必读：lark-base/references/lark-base-field-json.md §link
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
必读：../lark-base/SKILL.md「表单与视图细节」
筛选必读：lark-base/references/lark-base-view-set-filter.md
必要时读：lark-cli base +view-create --help / +view-update --help / 对应 +view-* --help
```

创建视图后，按需配置：
- `+view-set-filter` （视图筛选）
- sort/group/card/timebar/visible-fields 等配置：先用对应 get 命令读现状，保留未修改字段，只替换用户要求变更的配置；具体命令和参数以当前 `lark-cli base +view-* --help` 为准。

只有 `+view-set-filter` 有保留 reference；其他视图配置不要套旧 reference 名。

## Stage 5.G — 启用 advperm + 创建角色

```
必读：lark-base/references/lark-base-role-guide.md
必读：lark-base/references/role-config.md
必要时读：lark-cli base +advperm-enable --help / +role-create --help / +role-update --help
```

执行顺序：
1. `+advperm-enable`（必先启用，否则角色管理不生效）
2. 逐个 `+role-create`

注意 `+role-update` 是 Delta Merge——`role_name` 和 `role_type` 即使不改也必须传当前值。

## Stage 5.H — 创建表单 + 题目

```
必读：lark-base/references/lark-base-form-questions-create.md
必要时读：lark-cli base +form-create --help / +form-questions-create --help
```

执行顺序：
1. `+form-create` 拿到 `form-id`
2. 逐个 `+form-questions-create`（按表单题目顺序）

## Stage 5.I — 创建工作流

```
必读：lark-base/references/lark-base-workflow-guide.md
必读：lark-base/references/lark-base-workflow-schema.md（CRITICAL）
必要时读：lark-cli base +workflow-create --help / +workflow-update --help
```

禁止凭自然语言猜 step type。每个 step 的 `type` 必须查 schema 文档。

创建后默认是禁用状态——按需 `+workflow-enable` 启用。

## Stage 5.J — 创建仪表盘 + 组件

```
必读：lark-base/references/lark-base-dashboard.md
必读：lark-base/references/dashboard-block-data-config.md
必要时读：lark-cli base +dashboard-create --help / +dashboard-block-create --help
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

回滚命令（执行前以当前 `lark-cli base <command> --help` 核对）：
- `+dashboard-block-delete` / `+dashboard-delete`
- workflow 回滚优先 `+workflow-disable`；是否支持删除以当前 CLI 为准
- `+form-questions-delete` / `+form-delete`
- `+role-delete` / `+advperm-disable`
- `+view-delete`
- `+field-delete`
- `+table-delete`
- base 删除属于高风险 drive 文件操作；除非用户明确确认，否则只报告残留 Base 链接和已建对象清单

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
