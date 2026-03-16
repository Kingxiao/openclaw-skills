# 质量标准参考

本文档定义了高质量 AI Agent Skills 应遵循的标准。

---

## 1. 写作风格

### 1.1 使用祈使句

**推荐**:
```markdown
Create a new file in the scripts directory.
Run the validation before publishing.
```

**避免**:
```markdown
You should create a new file in the scripts directory.
You need to run the validation before publishing.
```

### 1.2 动作动词优先

优先使用具体的动作动词：

| 推荐 | 避免 |
|------|------|
| Create | Make |
| Execute | Do |
| Validate | Check |
| Generate | Produce |
| Configure | Set up |
| Analyze | Look at |

### 1.3 句子长度

- **理想长度**: 10-20 词/句
- **最大长度**: 25 词/句
- **过短提示**: < 5 词可能缺少必要细节

---

## 2. 内容结构

### 2.1 必要章节

每个高质量技能应包含：

1. **Overview/概述** (必需)
   - 简明扼要的功能描述
   - 核心价值说明

2. **When to Use/使用场景** (必需)
   - 明确的触发条件
   - 适用场景列表

3. **Instructions/操作步骤** (必需)
   - 分步骤的操作指南
   - 清晰的工作流程

4. **Examples/示例** (建议)
   - 至少 2 个代码示例
   - 涵盖常见用例

5. **Best Practices/最佳实践** (可选)
   - 使用建议
   - 常见陷阱

### 2.2 章节顺序

推荐的章节组织顺序：

```
1. Overview (概述)
2. Quick Start (快速开始)
3. When to Use (使用场景)
4. Core Instructions (核心操作)
5. Examples (示例)
6. Advanced Usage (高级用法) [可选]
7. References (参考资源) [可选]
8. Troubleshooting (问题排查) [可选]
```

---

## 3. 代码示例

### 3.1 代码块规范

- **必须**标注语言类型
- 使用真实可运行的代码
- 避免占位符（如 `xxx`、`TODO`）

**推荐**:
```python
def validate_skill(skill_path: str) -> bool:
    """Validate the skill directory structure."""
    path = Path(skill_path)
    return (path / "SKILL.md").exists()
```

**避免**:
```
def validate_skill(xxx):
    # TODO: implement
    pass
```

### 3.2 示例数量

| 评级 | 代码示例数 |
|------|------------|
| 优秀 | >= 3 个 |
| 良好 | 2 个 |
| 及格 | 1 个 |
| 不及格 | 0 个 |

---

## 4. Description 规范

frontmatter 中的 `description` 字段应遵循：

### 4.1 长度要求

- 最小：50 字符
- 推荐：100-500 字符
- 最大：1024 字符

### 4.2 内容要素

```yaml
description: |
  [功能描述]。[核心能力列表]。
  [使用场景 - "Use when..." 或 "当...时使用"]。
  [输出/效果说明]。
```

### 4.3 示例

```yaml
description: 全面的 AI Agent Skills 审计工具。对技能进行多维度质量保证检查，
  包括格式验证、安全扫描、质量评估、能力分析。当需要审计技能质量或发布前检查时使用。
  生成详细的审计报告和量化评分。
```

---

## 5. 一致性规范

### 5.1 标题层级

- 从 H1 开始
- 不跳跃层级（H1 → H3 ❌）
- 同级标题保持一致格式

```markdown
# 主标题 (H1)
## 二级标题 (H2)
### 三级标题 (H3)
```

### 5.2 列表标记

在同一文档中统一使用一种列表标记：

```markdown
# 推荐 - 统一使用 "-"
- 项目 1
- 项目 2
  - 子项目

# 避免混用
- 项目 1
* 项目 2
+ 项目 3
```

### 5.3 中英文混排

中英文之间添加空格：

```markdown
# 推荐
使用 Python 编写脚本

# 避免
使用Python编写脚本
```

---

## 6. 文档化要求

### 6.1 脚本 Docstring

每个 Python 脚本应在文件开头包含 docstring：

```python
#!/usr/bin/env python3
"""
模块简短描述

详细说明（可选）：
- 功能列表
- 使用方法
- 依赖说明

Usage:
    python script.py <args>
    
Example:
    python script.py ./input --output result.json
"""
```

### 6.2 函数文档

公开函数应包含 docstring：

```python
def process_data(input_path: str, options: dict = None) -> dict:
    """
    处理输入数据并返回结果。
    
    Args:
        input_path: 输入文件路径
        options: 可选配置字典
        
    Returns:
        处理后的数据字典
        
    Raises:
        FileNotFoundError: 输入文件不存在
        ValueError: 数据格式无效
    """
```

---

## 7. 质量检查清单

发布前确保：

- [ ] SKILL.md 语法正确，无拼写错误
- [ ] 所有链接有效
- [ ] 代码示例可运行
- [ ] 没有 TODO/TBD 标记
- [ ] 没有硬编码的路径或密钥
- [ ] description 包含使用场景
- [ ] 至少有 2 个代码示例
- [ ] 脚本都有 docstring
- [ ] 引用文件都存在
