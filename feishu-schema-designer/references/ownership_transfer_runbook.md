# Stage 6 所有权处理手册

> verified: 2026-04-16
> 核心约束来源：`lark-base/SKILL.md` §4.4 第 5 条 + `lark-base-base-create.md`

## 第一性原理

**谁创建，谁就是 owner**。lark-cli 双身份模型：
- `--as user` 创建 → 用户本人是 owner（零额外步骤）
- `--as bot` 创建 → bot 是 owner（需要给用户授权）

**lark-base 官方铁律**：
> "owner 转移必须单独确认，禁止擅自执行"

## 决策树

```
Stage 5.A 创建 base 时用了什么身份？
│
├─ --as user
│  └─ 用户已是 owner ✅
│     → Stage 6 直接进入「编写 08_handover.md」
│     → 用户登录飞书即可看到 base
│
└─ --as bot
   └─ bot 是 owner，用户暂时看不到
      → 步骤 1: 取用户 open_id
      → 步骤 2: 用 bot 身份给用户授 full_access
      → 步骤 3: 编写 08_handover.md
      → 用户登录飞书可见 base，权限为「管理员」
      → owner 仍是 bot；除非用户单独说"owner 也归我"
```

## 身份选择策略

进入 Stage 5.A 前 agent 先判断：

```
1. 检查当前 lark-cli 是否有可用 user 身份
   命令：lark-cli auth status --as user
   有 → 优先用 --as user 创建（最优）
   无 → fallback --as bot 创建
2. 询问用户是否需要 lark-cli auth login（如果当前没有 user 身份且本次任务结束需要长期使用）
   如果用户授权，走 user 路径
   如果用户拒绝，走 bot 路径
```

## 路径 A：`--as user` 创建（首选）

Stage 5.A 用 `--as user`：

```bash
lark-cli base +base-create --name "..." --as user
```

成功后：
- ✅ 用户即 owner
- ✅ 后续所有 `+table-create / +field-create / ...` 也都用 `--as user`，避免身份混乱
- ✅ Stage 6 跳过授权步骤，直接写 `08_handover.md`

## 路径 B：`--as bot` 创建（fallback）

Stage 5.A 用 `--as bot`：

```bash
lark-cli base +base-create --name "..." --as bot
```

成功后：
- ⚠️ bot 是 owner，**用户登录飞书看不到这个 base**
- ⚠️ 必须立即给用户授 full_access

### Stage 6 步骤（路径 B 专用）

#### 步骤 1：取用户 open_id

```bash
lark-cli contact +get-user --as user
```

返回示例：
```json
{ "user": { "open_id": "ou_xxxx", "name": "张三" } }
```

**失败处理**（来自 `lark-base-base-create.md` 原文规定）：
- `lark-cli contact +get-user` 无法执行 → 视为"本地没有可用 user 身份"
- 明确告知用户：base 已建好，但**未完成授权**
- 在 `08_handover.md` 注明：用户可以
  - 稍后重试授权
  - 或继续以 bot 身份处理该 base
  - 或要求 owner 转移（需用户单独确认）

#### 步骤 2：bot 身份给用户授 full_access

```bash
# 仍然用 bot 身份（lark-base-base-create.md 要求）
lark-cli base +role-create --base-token <base_token> \
  --role-name "管理员" --role-type "system" \
  --member-list '[{"open_id": "ou_xxxx", "type": "user"}]' \
  --permissions full_access \
  --as bot
```

> 实际命令格式以 `lark-base/references/lark-base-role-create.md` 为准——执行前必先读

**成功**：用户登录飞书后可见 base，权限为管理员（full_access）
**失败**：在 `08_handover.md` 注明失败原因 + 重试方法

## owner 转移（用户单独确认才执行）

用户主动说"我要做 owner，不只是管理员"时才执行。

**已实测确认（2026-04-16）**：
- 命令：`lark-cli drive permission.members transfer_owner`
- 命令性质：`danger: true`（lark-cli 标记的高风险操作）
- 必须身份：`user_access_token` 才能调用（即 `--as user`）；bot 不能转 owner
- schema 查询：`lark-cli schema drive.permission.members.transfer_owner`

### 必填参数

| 参数 | 位置 | 说明 |
|------|------|------|
| `token` | path | 云文档 token——base 的 `base_token` |
| `type` | query | 云文档类型——base 用 `bitable` |
| (body) | body | 新 owner 的 user_id，按 schema 文档结构 |

### 可选参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `need_notification` | true | 是否通知新 owner |
| `old_owner_perm` | full_access | 旧 owner 保留权限：view / edit / full_access |
| `remove_old_owner` | false | 是否移除旧 owner 权限 |
| `stay_put` | false | 个人文件夹下的文档是否留原位 |

### 执行步骤

1. **必先 dry-run**：`lark-cli drive permission.members transfer_owner --dry-run --as user --params '{"token":"<base_token>","type":"bitable"}' --data '{"member_type":"openid","member_id":"<user_open_id>"}'`
2. 把 dry-run 输出（实际请求）展示给用户，二次确认
3. 用户确认后去掉 `--dry-run` 真执行
4. 推荐 `old_owner_perm=full_access` + `remove_old_owner=false`——agent（旧 owner，bot 路径下）保留管理员权限，方便后续协助
5. 在 `08_handover.md` 明确写「owner 已转移给用户 + agent/bot 仍持有 full_access」

### bot 路径下的限制

如果 base 是 bot 创建（路径 B），bot 自己**不能**转 owner——必须先让 user 接手或者 bot 应用管理员手动操作。
处理流程：
1. 先按主路径完成：bot 给 user 授 full_access → user 登录飞书可见 base
2. user 在飞书 UI 里点击「转移所有者」（这是用户操作，不是 agent）
3. 或者 user 自己跑 `lark-cli auth login` 后用 `--as user` 调上面的命令

## 08_handover.md 模板

```markdown
# 应用交接说明

## 应用基本信息
- **名称**：客户管理系统
- **链接**：https://...
- **创建时间**：2026-04-16 10:23:15
- **创建身份**：[--as user / --as bot]
- **你的角色**：[owner（直接创建） / 管理员 full_access（bot 创建后授权） / 待授权（授权失败）]

## 接管说明

### 如果你是 owner
1. 直接登录飞书，在云空间『最近』里能看到这个 base
2. 可以邀请团队成员、修改任何配置

### 如果你是管理员（full_access）
1. 登录飞书，在分享给你的 base 列表里能看到
2. 你能改一切，但 owner 仍是 bot 应用
3. 如果想接管 owner，告诉我："把 owner 转移给我"

### 如果授权失败（路径 B 失败）
1. 当前 base 由 bot 持有，你看不到
2. 解决方法：
   - 跑 `lark-cli auth login`，授权后再让我重试 Stage 6 步骤 1-2
   - 或者告诉我 owner 转移（需要 lark-cli api PATCH 底层操作）

## 后续动作建议
1. 录入初始数据（人工 / 用 lark-base `+record-batch-create` 批量导入）
2. 邀请团队成员加入对应角色
3. 告诉相关同事飞书云文档手册的链接（见 09_user_manual.md）
4. 试运行一周，发现问题告诉我，迭代调整 schema
```

## 暴露给用户的潜在问题

每次 Stage 6 完成后，把以下问题主动告知用户：

- 当前 owner 是谁
- 当前用户身份和权限
- 是否需要做 owner 转移（明确说"非必需"）
- bot 身份的 base 是否会被 bot 应用下架影响（如果 bot 应用被卸载，base 怎么办——这是 lark-cli 文档未明确的风险点，用户应知道）
