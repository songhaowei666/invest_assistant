# SQL Copilot HTTP 接口说明

本文档对应 `api/controllers/sql_copilot.py` 中注册的接口。应用路由统一挂在 `settings.API_PREFIX` 下，默认前缀为 **`/api/v1`**（见 `api/configs/config.py`）。

基准示例：`http://localhost:8000` + Path。

---

## 1. 会话查询（自然语言 -> SQL -> 结果 -> 总结）

- **Method / Path**：`POST /api/v1/sql-copilot/chat`
- **Content-Type**：`application/json`
- **说明**：
  - 接收自然语言问题；
  - 生成并执行只读 SQL；
  - 返回 SQL、结构化结果和 LLM 中文总结；
  - 会话历史写入数据库表 `sql_copilot_message`，用于短期记忆（最近 20 条）。

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 否 | 会话 ID；不传或空字符串时后端自动创建新会话 |
| question | string | 是 | 用户自然语言问题 |
| user_id | string | 否 | 用户 ID，默认 `default_user` |

### 请求示例

```json
{
  "session_id": "demo-session-001",
  "user_id": "song",
  "question": "查询 600519 最近五个年报的 ROE"
}
```

### 成功响应（200）示例

```json
{
  "session_id": "demo-session-001",
  "question": "查询 600519 最近五个年报的 ROE",
  "sql": "SELECT report_period, roe FROM stock_financial_report WHERE code = '600519' AND RIGHT(report_period, 4) = '1231' ORDER BY report_period DESC LIMIT 5;",
  "columns": ["report_period", "roe"],
  "rows": [
    {"report_period": "20241231", "roe": 31.2},
    {"report_period": "20231231", "roe": 30.1}
  ],
  "answer": "近五个年报 ROE 维持在较高水平，最新一期约为 31.2%。整体盈利能力稳定，建议结合行业均值和估值指标进一步判断。",
  "error": ""
}
```

### 自动创建会话示例（不传 `session_id`）

```json
{
  "user_id": "song",
  "question": "查询 601328 最新市盈率"
}
```

响应示例：

```json
{
  "session_id": "sqlc-a1b2c3d4e5f6",
  "question": "查询 601328 最新市盈率",
  "sql": "SELECT pe FROM stock_basic_info WHERE code = '601328';",
  "columns": ["pe"],
  "rows": [{"pe": 5.6}],
  "answer": "已返回交通银行最新市盈率。",
  "error": ""
}
```

### 失败响应特征

- 业务失败时仍返回统一结构，`error` 字段有值，`answer` 会给出错误说明。
- 典型场景：
  - SQL 安全校验失败（只允许 `SELECT` / `WITH`）；
  - SQL 执行失败（字段不存在、语法异常等）；
  - 底层模型或数据库连接异常。

---

## 2. 可查询范围接口

- **Method / Path**：`GET /api/v1/sql-copilot/query-scope`
- **说明**：
  - 返回 `stock_basic_info`、`stock_financial_report` 两张表的可查询字段清单；
  - 返回 LLM 生成的查询范围总结；
  - 返回记忆相关元信息（embedding 模型、维度、短期窗口）。

### 成功响应（200）示例

```json
{
  "tables": {
    "stock_basic_info": [
      {"name": "code", "type": "VARCHAR(20)", "nullable": false, "comment": "股票编码（6位数字代码，如 600519）"},
      {"name": "pe", "type": "FLOAT", "nullable": true, "comment": "市盈率 TTM（倍，无单位）"}
    ],
    "stock_financial_report": [
      {"name": "code", "type": "VARCHAR(20)", "nullable": false, "comment": "股票编码（6位数字代码，如 600519）"},
      {"name": "report_period", "type": "VARCHAR(16)", "nullable": false, "comment": "报告期（YYYYMMDD，如 20241231 表示 2024 年年报）"}
    ]
  },
  "scope_summary": "可查询范围包含估值快照和多期财务指标历史。若问 PE/PB 请使用 stock_basic_info，若问多期 ROE/营收请使用 stock_financial_report。",
  "meta": {
    "embedding_model": "text-embedding-3-large",
    "embedding_dimensions": 3072,
    "short_term_memory_limit": 20
  }
}
```

---

## 3. 会话列表接口

- **Method / Path**：`POST /api/v1/sql-copilot/sessions/list`
- **说明**：按用户查询会话列表，按更新时间倒序返回。

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 否 | 用户 ID，默认 `default_user` |
| limit | integer | 否 | 返回条数上限，默认 `100`，范围 `1~500` |

### 成功响应（200）示例

```json
{
  "sessions": [
    {
      "session_id": "demo-session-001",
      "user_id": "song",
      "title": "查询茅台 ROE",
      "preview": "查询 600519 最近五个年报的 ROE",
      "created_at": "2026-05-09T16:00:00+08:00",
      "updated_at": "2026-05-09T16:05:00+08:00",
      "message_count": 4
    }
  ]
}
```

---

## 4. 会话删除接口

- **Method / Path**：`POST /api/v1/sql-copilot/sessions/delete`
- **说明**：按 `session_id + user_id` 删除会话及其消息历史。

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID |
| user_id | string | 否 | 用户 ID，默认 `default_user` |

### 成功响应（200）示例

```json
{
  "deleted": true
}
```

---

## 5. 记忆与历史策略（当前实现状态）

- **短期会话历史（已启用）**
  - 会话主表：`sql_copilot_session`
  - 消息表：`sql_copilot_message`
  - 读取策略：按 `session_id + user_id` 读取最近 20 条消息拼接上下文
  - 写入时机：每次 `chat` 会写入用户问题与 assistant 结果摘要

- **长期记忆 mem0（代码保留，调用临时注释）**
  - 目标角色：长期语义记忆召回
  - 计划配置：`text-embedding-3-large`（3072 维）
  - 当前状态：因缺少 `MEM0_API_KEY`，调用入口临时注释，后续可直接恢复

---

## 6. 相关代码位置

- 控制器：`api/controllers/sql_copilot.py`
- 服务层：`api/services/sql_copilot_service.py`
- LangGraph 流程：`api/ai/sql_copilot_graph.py`
- 会话模型：`api/models/sql_copilot_session.py`
- 会话历史模型：`api/models/sql_copilot_message.py`
- 会话建表脚本：`api/scripts/create_sql_copilot_session_table.py`
- 会话历史建表脚本：`api/scripts/create_sql_copilot_message_table.py`

