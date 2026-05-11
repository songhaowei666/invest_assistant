# SQL Copilot 前端对接规格（Spec）

本文档用于前端开发对接 `SQL Copilot` 能力，覆盖接口契约、页面交互状态、错误处理和会话规则。  
后端默认前缀：`/api/v1`。

## 1. 功能目标

- 用户输入自然语言问题，系统返回：
  - 生成 SQL
  - 查询结果（结构化）
  - LLM 中文总结（润色结果）
- 提供“可查询范围”接口，前端可据此构建字段引导与提问建议。
- 会话历史持久化，支持多轮追问。

## 2. 接口清单

- `POST /api/v1/sql-copilot/chat`
- `GET /api/v1/sql-copilot/query-scope`
- `POST /api/v1/sql-copilot/sessions/list`
- `POST /api/v1/sql-copilot/sessions/delete`

---

## 3. `POST /sql-copilot/chat`

### 3.1 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| session_id | string | 否 | 自动生成 | 会话标识；不传时后端创建新会话并在响应中返回 |
| question | string | 是 | 无 | 用户自然语言问题 |
| user_id | string | 否 | `default_user` | 用户标识；用于会话隔离 |

请求示例：

```json
{
  "session_id": "chat-20260509-001",
  "user_id": "song",
  "question": "查询 600519 最近五个年报的 ROE"
}
```

自动创建会话请求示例：

```json
{
  "user_id": "song",
  "question": "查询 601328 最新市盈率"
}
```

### 3.2 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 回显请求会话 ID |
| question | string | 回显用户问题 |
| sql | string | 生成并执行的 SQL |
| columns | string[] | 结果列名 |
| rows | object[] | 查询结果数据（最多 200 行） |
| answer | string | LLM 中文总结 |
| error | string | 业务错误信息；空字符串表示成功 |

成功示例：

```json
{
  "session_id": "chat-20260509-001",
  "question": "查询 600519 最近五个年报的 ROE",
  "sql": "SELECT report_period, roe FROM stock_financial_report WHERE code = '600519' AND RIGHT(report_period, 4) = '1231' ORDER BY report_period DESC LIMIT 5;",
  "columns": ["report_period", "roe"],
  "rows": [
    {"report_period": "20241231", "roe": 31.2},
    {"report_period": "20231231", "roe": 30.1}
  ],
  "answer": "近五个年报 ROE 保持较高水平，最新一期约 31.2%。",
  "error": ""
}
```

失败示例（业务失败仍为同结构）：

```json
{
  "session_id": "chat-20260509-001",
  "question": "帮我删除 stock_basic_info 表",
  "sql": "DROP TABLE stock_basic_info;",
  "columns": [],
  "rows": [],
  "answer": "生成的 SQL 未通过只读安全校验，仅允许 SELECT 查询。",
  "error": "生成的 SQL 未通过只读安全校验，仅允许 SELECT 查询。"
}
```

### 3.3 前端处理建议

- 若 `error` 非空：
  - 将本轮标记为失败态；
  - 展示 `answer`（或 `error`）作为可读报错；
  - 允许用户一键“重试/改写问题”。
- 若 `rows` 为空且 `error` 为空：
  - 展示“查询成功但无数据”的空态，不视为失败。
- SQL 展示建议默认折叠，支持复制按钮。

---

## 4. `GET /sql-copilot/query-scope`

### 4.1 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| tables | object | 各表字段信息 |
| scope_summary | string | LLM 总结的可查询范围 |
| meta.embedding_model | string | 嵌入模型标识（设计值） |
| meta.embedding_dimensions | number | 嵌入维度（设计值） |
| meta.short_term_memory_limit | number | 短期记忆窗口 |

`tables` 内字段项结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 字段名 |
| type | string | 数据库字段类型 |
| nullable | boolean | 是否可空 |
| comment | string | 字段中文说明 |

### 4.2 前端用途

- 生成“可查询字段”面板与字段检索框。
- 生成提问模板，如“查询某股票近五年 ROE 趋势”。
- 在用户输入阶段做提示：哪些指标在哪张表可查。

---

## 5. `POST /sql-copilot/sessions/list`

### 5.1 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_id | string | 否 | `default_user` | 用户标识 |
| limit | number | 否 | `100` | 返回会话数量上限，范围 `1~500` |

### 5.2 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| sessions | object[] | 会话列表，按更新时间倒序 |
| sessions[].session_id | string | 会话 ID |
| sessions[].title | string | 会话标题 |
| sessions[].preview | string | 预览内容 |
| sessions[].created_at | string | 创建时间 |
| sessions[].updated_at | string | 更新时间 |
| sessions[].message_count | number | 消息条数 |

---

## 6. `POST /sql-copilot/sessions/delete`

### 6.1 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| session_id | string | 是 | 无 | 待删除会话 ID |
| user_id | string | 否 | `default_user` | 用户标识 |

### 6.2 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| deleted | boolean | 是否删除成功（会话存在并删除则为 `true`） |

---

## 7. 会话与记忆规则

- 会话主表：`sql_copilot_session`。
- 会话消息表：`sql_copilot_message`。
- 短期窗口：最近 20 条（按 `session_id + user_id` 读取）。
- 长期记忆：mem0 代码已保留，但当前调用入口临时注释（缺少 key 时不启用）。

前端约束：

- 可由前端生成 `session_id`，也可不传让后端自动生成。
- 同一会话内连续追问必须复用同一个 `session_id`。
- 不同登录用户应传不同 `user_id`，避免历史串线。

---

## 8. 页面状态机建议

- `idle`：未提问
- `submitting`：请求发送中
- `success`：请求成功并渲染 `answer + rows + sql`
- `empty`：成功但 `rows` 为空
- `error`：`error` 非空或网络失败

---

## 9. 非功能与边界

- SQL 安全：仅允许只读 SQL（`SELECT/WITH`）；DML/DDL 会被拦截。
- 返回行数：后端当前最多返回 200 行，前端建议分页或虚拟滚动渲染。
- 字段口径：以后端模型 `comment` 为准，前端不要自行推断财务单位。

---

## 10. 联调最小流程

1. 调 `GET /api/v1/sql-copilot/query-scope` 拉字段范围并缓存。
2. 调 `POST /api/v1/sql-copilot/sessions/list` 拉历史会话（可选）。
3. 用户提问后调 `POST /api/v1/sql-copilot/chat`。
4. 渲染 `answer`、`sql`、`rows`，并根据 `error` 控制状态。
5. 同会话复用 `session_id` 完成多轮对话；删除会话时调 `POST /api/v1/sql-copilot/sessions/delete`。
