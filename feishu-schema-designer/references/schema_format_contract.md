# Schema 格式契约（v2）

> verified: 2026-06-10（与当前 lark-base v1.2.2 对齐）

`04_schema_final.json` 是**业务层 schema**：用于设计推理、审批预览、覆盖校验和执行编排。Stage 5 真正调用 `lark-cli base +...` 前，必须按当前 lark-base references 转成调用层 JSON；调用层格式以 lark-base 为唯一可信源。

## 为什么不复制 lark-base reference

lark-base 的 reference 是单一可信源（SSOT）。**一旦本文件复制了 lark-base 内容，就有版本漂移风险**。本文件只定义 feishu-schema-designer 的业务层 schema 约定、校验点和转换原则；字段、CellValue、workflow、dashboard、role 的最终 JSON 必须回查 lark-base。

## 强制查阅的 lark-base reference（Stage 3 前必读）

| 我要做什么 | 必查 reference（必亲自 Read） |
|----------|--------------|
| 字段 | [`../../lark-base/references/lark-base-field-json.md`](../../lark-base/references/lark-base-field-json.md) + [`../../lark-base/references/lark-base-field-create.md`](../../lark-base/references/lark-base-field-create.md) / [`../../lark-base/references/lark-base-field-update.md`](../../lark-base/references/lark-base-field-update.md) |
| 记录值 | [`../../lark-base/references/lark-base-cell-value.md`](../../lark-base/references/lark-base-cell-value.md) |
| 公式字段 | [`../../lark-base/references/formula-field-guide.md`](../../lark-base/references/formula-field-guide.md) |
| lookup 字段 | [`../../lark-base/references/lookup-field-guide.md`](../../lark-base/references/lookup-field-guide.md) |
| workflow | [`../../lark-base/references/lark-base-workflow-schema.md`](../../lark-base/references/lark-base-workflow-schema.md) + [`../../lark-base/references/lark-base-workflow-guide.md`](../../lark-base/references/lark-base-workflow-guide.md) |
| dashboard block | [`../../lark-base/references/dashboard-block-data-config.md`](../../lark-base/references/dashboard-block-data-config.md) |
| form questions | [`../../lark-base/references/lark-base-form-questions-create.md`](../../lark-base/references/lark-base-form-questions-create.md) |
| role | [`../../lark-base/references/role-config.md`](../../lark-base/references/role-config.md) |
| data-query | [`../../lark-base/references/lark-base-data-query.md`](../../lark-base/references/lark-base-data-query.md) |

## schema.json 顶层结构

```json
{
  "$verified": "YYYY-MM-DD",
  "app": {
    "name": "...",
    "description": "...",
    "folder_token": null,
    "time_zone": "Asia/Shanghai"
  },
  "tables": [ /* Table[] */ ],
  "relationships": [ /* 可选，用于文档化展示；实际建表时从 fields[].type=single_link/duplex_link 推导 */ ],
  "workflows": [ /* Workflow[] —— 顶层字段 steps */ ],
  "dashboards": [ /* Dashboard[] —— 顶层字段 blocks */ ],
  "forms": [ /* Form[] —— 顶层字段 questions */ ],
  "roles": [ /* AdvPermBaseRoleConfig[] —— 顶层字段 role_name/role_type/base_rule_map/table_rule_map/dashboard_rule_map */ ]
}
```

## 字段类型：业务层 schema vs lark-base 调用层

⚠️ **重大澄清**：本 skill 的 `04_schema_final.json` 是**业务层抽象**，便于设计推理；`lark-cli base +field-create --json` 用的是当前 lark-base 认可的**调用层 field JSON**。Stage 5 执行前必须 transform，并再次核对 `lark-base-field-json.md`。

### 业务层 ⇄ lark-cli 调用层映射表

| 业务层 type | lark-cli `--json` type | lark-cli 必填子字段 | 备注 |
|------------|------------------------|--------------------|------|
| `text` | `text` | — | 可选 `style.type=plain/phone/url/email/barcode` |
| `number` | `number` | — | 可选 `style.type=plain/currency/progress/rating` + style 子字段 |
| `phone` | `text` | `style: {type: "phone"}` | lark-cli 无独立 phone type |
| `url` | `text` | `style: {type: "url"}` | 同上 |
| `currency` | `number` | `style: {type: "currency", precision: 2, currency_code: "CNY"}` | |
| `progress` | `number` | `style: {type: "progress", percentage: true, color: "Blue"}` | |
| `rating` | `number` | `style: {type: "rating", icon: "star", min: 1, max: 5}` | |
| `single_select` | `select` | `multiple: false, options: [{name, hue, lightness}]` | hue ∈ Red/Orange/Yellow/Lime/Green/Turquoise/Wathet/Blue/Carmine/Purple/Gray |
| `multi_select` | `select` | `multiple: true, options: [...]` | 同上 |
| `datetime` | `datetime` | — | 可选 `style.format` |
| `checkbox` | `checkbox` | — | |
| `user` | `user` | `multiple: bool` | |
| `attachment` | `attachment` | — | |
| `location` | `location` | — | |
| `auto_number` | `auto_number` | `style.rules: [{type:"text",text:"NO."},{type:"incremental_number",length:4}]` | |
| `single_link` | `link` | `link_table: <表名>, bidirectional: false` | 业务层名称，不可直接传给 lark-cli |
| `duplex_link` | `link` | `link_table: <表名>, bidirectional: true, bidirectional_link_field_name: <反向名>` | 业务层名称，不可直接传给 lark-cli |
| `formula` | `formula` | `expression: "<lark-base 公式语法>"` | **公式用 `[字段名]` 不是 `{字段名}`；`==` → `=`；拼接用 `&` 或 `CONCATENATE()`；引用 link 字段返回列表，需 FIRST/SUM/&** |
| `lookup` | `lookup` | `from, select, where`（必读 lookup-field-guide.md）| |
| `created_time` | `created_at` | — | **lark-cli 改名！** |
| `modified_time` | `updated_at` | — | **同上** |
| `created_user` | `created_by` | — | **同上** |
| `modified_user` | `updated_by` | — | **同上** |
| `group_chat` | （未实测）| — | |

### Transformer 模板（业务层 → lark-base 调用层）

```python
COLOR_TO_HUE = {0:"Red", 1:"Green", 2:"Blue", 3:"Orange", 4:"Purple"}
TYPE_RENAMES = {"created_time":"created_at", "modified_time":"updated_at",
                "created_user":"created_by", "modified_user":"updated_by"}

def transform_field(f):
    """业务 field → lark-cli field JSON"""
    name, t = f["name"], f["type"]
    out = {"name": name}
    if f.get("description"): out["description"] = f["description"]

    if t in ("text","number","datetime","checkbox","attachment","location"):
        out["type"] = t
    elif t in TYPE_RENAMES:
        out["type"] = TYPE_RENAMES[t]
    elif t == "phone":
        out.update(type="text", style={"type":"phone"})
    elif t == "url":
        out.update(type="text", style={"type":"url"})
    elif t == "currency":
        out.update(type="number", style={"type":"currency","precision":2,"currency_code":"CNY"})
    elif t == "progress":
        out.update(type="number", style={"type":"progress","percentage":True,"color":"Blue"})
    elif t == "rating":
        out.update(type="number", style={"type":"rating","icon":"star","min":1,"max":5})
    elif t in ("single_select","multi_select"):
        out["type"] = "select"
        out["multiple"] = (t == "multi_select")
        opts = f.get("property",{}).get("options",[])
        out["options"] = [{"name":o["name"], "hue":COLOR_TO_HUE.get(o.get("color",2),"Blue"),
                           "lightness":"Lighter"} for o in opts]
    elif t == "user":
        out.update(type="user", multiple=f.get("property",{}).get("multiple",False))
    elif t == "auto_number":
        out.update(type="auto_number", style={"rules":[{"type":"text","text":"NO."},
                                                       {"type":"incremental_number","length":4}]})
    elif t in ("single_link","duplex_link"):
        out.update(type="link", link_table=f["property"]["table_name"],
                   bidirectional=(t=="duplex_link"))
    elif t == "formula":
        out.update(type="formula", expression=f["property"]["formula_expression"])
    return out
```

## Workflow 结构（业务层约定）

顶层字段：**`steps`**（数组）。每个 step：

```json
{
  "id": "step_唯一ID",
  "type": "AddRecordTrigger",
  "title": "步骤标题",
  "children": { "links": [ { "kind": "if_true", "to": "step_其他ID", "label": "", "desc": "" } ] },
  "next": "step_后继ID或null",
  "data": { /* 按 type 不同而异，查 workflow-schema.md */ }
}
```

**Step type 枚举不要在本文件内认定为完整列表**。创建/更新或解释 workflow 时，必须读当前 lark-base 的 `lark-base-workflow-guide.md` 和 `lark-base-workflow-schema.md`，以那里列出的 StepType、data 结构和 ref 语法为准。

**关键规则**：
- 线性后继用 `next: "step_id"`，流程结束 `next: null`
- 分支/循环用 `children.links` 数组，不用嵌套
- Trigger 节点**不要设 `children`**，只用 `next`
- **禁止凭自然语言猜 type**

## Dashboard 结构（业务层约定）

顶层字段：**`blocks`**（数组）。

```json
{
  "name": "仪表盘名",
  "blocks": [
    {
      "name": "组件标题",
      "type": "statistics",
      "data_config": {
        "table_name": "订单表",
        "series": [{ "field_name": "金额", "rollup": "SUM" }],
        "group_by": [{ "field_name": "类别", "mode": "integrated" }],
        "filter": { "conjunction": "and", "conditions": [ { "field_name": "状态", "operator": "is", "value": "已成交" } ] }
      }
    }
  ]
}
```

**常见 block type**（最终以当前 `dashboard-block-data-config.md` 为准）：
```
column / bar / line / pie / ring / area / combo / scatter /
funnel / wordCloud / radar / statistics / text
```

**禁止**用 `number_card` / `pie_chart` / `bar_chart` / `widget` 等——lark-base 不认。

`data_config` 的 `series`、`group_by`、`filter`、operator 和图表返回协议全部以 `dashboard-block-data-config.md` / `lark-base-dashboard-block-get-data.md` 为准；本文件只约束 Stage 4 预览和 Stage 5 编排时要有 `blocks`，不替代底层协议。

## Form 结构（业务层约定）

顶层字段：**`questions`**（数组）。

```json
{
  "name": "表单名",
  "target_table": "目标表名",
  "visibility": "share_link",
  "questions": [
    {
      "title": "问题标题（对应字段名）",
      "type": "text",
      "required": true,
      "description": "可选描述（支持 Markdown 链接）",
      "multiple": false,
      "options": [ { "name": "选项1", "hue": "Blue" } ]
    }
  ]
}
```

**Question type 枚举**（原文）：
```
text / number / select / datetime / user / attachment / location
```

**注意**：form 的 `type` 枚举和字段的 `type` 枚举**不一样**——form 只有 7 个。

`options[].hue` 可选值：`Red / Orange / Yellow / Green / Blue / Purple / Gray`

## Role 结构（业务层约定）

顶层字段沿用当前 lark-base `role-config.md` 的 `AdvPermBaseRoleConfig`：**`role_name` / `role_type` / `base_rule_map` / `table_rule_map` / `dashboard_rule_map` / `docx_rule_map`**。创建/更新角色前必须读 `lark-base-role-guide.md` 和 `role-config.md`。

```json
{
  "role_name": "项目经理",
  "role_type": "custom_role",
  "base_rule_map": { "copy": false, "download": false },
  "table_rule_map": {
    "表名": {
      "perm": "edit",
      "view_rule": {...},
      "field_rule": {...},
      "record_rule": {...}
    }
  },
  "dashboard_rule_map": { "看板名": { "perm": "read_only" } }
}
```

**关键**：
- `role_type`：创建时只能 `custom_role`；更新时可 `editor` / `reader` / `custom_role`
- `base_rule_map` 默认 false，**禁止擅自设 true**
- `table_rule_map` 是 map，**key 是表名**，value 是 TableRule（含 `perm` + 视图/字段/记录 三层过滤）
- `dashboard_rule_map.<名>.perm`：`read_only` / `no_perm`

**禁止**用 `permissions` 数组结构——那不是当前 lark-base role JSON。

## 主字段（primary）设计规则（2026-06-10 强化）

**背景**：在飞书多维表格中，**主字段（第一列）是关联字段显示的文本**。A 表关联到 B 表，A 里看到的就是 B 的主字段值。如果主字段是 `auto_number`（显示 001/002/003），关联列就是一串无意义的序号——业务用户无法判断这是哪个老人/哪个站点/哪笔请款。

**硬规则**：
1. **主字段必须是对象/主体名称或主体可读标识**——优先用 `客户名称`、`项目名称`、`站点名称`、`老人编号`、`SKU名称`、`任务标题`、`订单号` 这类业务用户会用来识别一条记录的字段。
2. **主字段必须放第一列**——第一列不是“内部 ID 位”，而是跨表引用、单向/双向关联、表单视图、记录分享、lookup 展示时的默认可读标题。
3. **禁止 `auto_number` 作主字段或第一列**——`auto_number` 允许保留，但只能放第二列及以后，通常命名为 `内部序号` / `系统编号`；它不是业务主键，也不是跨表展示名。
4. **没有自然名称时才用 `formula` 主字段**——公式必须拼出业务可读标识，如 `站点 · 数据月份`、`客户 · 合同月份`、`老人编号 · 签署日期`。
5. **每表字段顺序**：主体名称/主体可读标识主字段 → 内部序号/业务编号等辅助标识 → 业务描述字段 → 关联字段 → 状态/状态机字段 → 时间戳/系统字段最后。

**选择策略（决策树）**：
- 表已有「对象/主体名称」类 `text` 字段 → 直接提升为 primary，放第一位
- 表没有名称，但有稳定业务编号（非自增、用户会拿它沟通，如老人编号、订单号、SKU编码）→ 可作为 primary，放第一位
- 表无自然名字，但可由多字段拼接得业务可读标识（如"站点+月份"/"站点+季度"/"老人+签署日期"）→ 新增 `formula` 字段作 primary
- 常见 formula 拼接模板：
  - `CONCATENATE({关联表}, " · ", TEXT({日期}, "yyyy-mm"))`
  - `CONCATENATE({名称}, " × ", {角色})`
  - `CONCATENATE({类型}, " · ", {金额}, "元 · ", TEXT({日期}, "yyyy-mm-dd"))`

**常见误用**：
- ❌ 请款单 primary=auto_number → 关联表显示"001" → 改为 formula "{站点} · {请款季度}"
- ❌ 授权书 primary=auto_number → 看不出是谁的授权书 → 改为 formula "{关联老人} · {签署日期}"
- ❌ 月度数据 primary=auto_number → 历史关联看不出是哪个月 → 改为 formula "{站点} · {数据月份}"
- ❌ 客户表第一列=自增序号，第二列=客户名称 → 关联订单时只显示"001" → 改为第一列 `客户名称`，自增序号放第二列
- ❌ 项目表第一列=项目ID，第二列=项目名称 → 表单/关联/看板默认标题不可读 → 改为第一列 `项目名称`

## 程序化校验规则（Stage 3 必跑）

除了之前的 5 项（外键闭合/字段类型白名单/主字段唯一性/formula 引用/命名一致性），**v2 新增**：

6. **workflow 实质性**：每个 workflow 的 `steps` 数组非空，且至少含 1 个 Trigger type + 1 个 Action type
7. **dashboard 实质性**：每个 dashboard 的 `blocks` 数组非空，每个 block 的 `type` 在 13 种枚举内
8. **form 实质性**：每个 form 的 `questions` 数组非空，每个 question 的 `type` 在 7 种枚举内
9. **role 实质性**：每个 role 含 `role_name` + `role_type=custom_role` + `base_rule_map` 必填；`table_rule_map` 至少覆盖 1 张表
10. **覆盖度**：每个 roles[].role_name 都出现在至少 1 张 dashboard 的 audience 或表的 table_rule_map 中（否则角色形同虚设）
11. **主字段业务语义**：主字段必须是第一列，类型必须是 `text` 或 `formula`，且字段名/说明应指向对象/主体名称或主体可读标识；**禁止 `auto_number` 作主字段或第一列**。校验逻辑：`for t in tables: assert t.fields[0].is_primary and t.fields[0].type in ('text','formula') and t.fields[0].type != 'auto_number'`

## 不可违反约束

1. **字段名精确匹配**——workflow/formula/lookup/data-query/role 中引用的字段名必须与 `tables[].fields[].name` 字面一致
2. **主字段唯一且有语义**——每表恰好一个 `is_primary: true`，必须在第一列，且应是对象/主体名称或主体可读标识
3. **系统字段不写入** `is_primary`、`required` 等用户字段属性
4. **双向关联自动反向**——不要在两张表都声明 duplex_link，lark-base 会自动生成反向字段
5. **禁止发明调用层 JSON key**——不要自造 `widgets / actions / fields / permissions / panels / pages` 等 lark-base 不认识的字段；业务层扩展字段只能用于设计文档，Stage 5 前必须丢弃或转换
6. **字段顺序**——对象/主体名称主字段第一位，auto_number 若保留则放第二列及以后

## Stage 3 校验失败处理

校验失败 → 按 issue 自修复 → 重跑校验。最多 3 次。

3 次仍失败的常见原因：
- 跨表关联引用了不存在的表（用户漏说了某实体）
- workflow step type 凭自然语言猜测（应回查 workflow-schema.md）
- role_type 写成了 `editor` 或 `reader`（创建时必须 `custom_role`）
- dashboard block type 用了自造名（如 `number_card`）

报告用户 → 等指示。
