# SQL Copilot 接口测试输出

- 脚本: `test_sql_copilot_api.py`
- 生成时间: `2026-05-09T16:38:29`

## 1. POST /api/v1/sql-copilot/chat

### 请求参数
```json
{
  "session_id": "demo-session-001",
  "user_id": "song",
  "question": "查询 600519 最近五个年报的 ROE"
}
```

### 接口返回
```json
{
  "session_id": "demo-session-001",
  "question": "查询 600519 最近五个年报的 ROE",
  "sql": "SELECT report_period, roe FROM stock_financial_report LIMIT 5;",
  "columns": [
    "report_period",
    "roe"
  ],
  "rows": [
    {
      "report_period": "20241231",
      "roe": 31.2
    }
  ],
  "answer": "这是总结内容。",
  "error": ""
}
```

## 2. POST /api/v1/sql-copilot/chat

### 请求参数
```json
{
  "user_id": "song",
  "question": "查询 601328 最新市盈率"
}
```

### 接口返回
```json
{
  "session_id": "sqlc-auto-001",
  "question": "查询 601328 最新市盈率",
  "sql": "SELECT pe FROM stock_basic_info WHERE code = '601328';",
  "columns": [
    "pe"
  ],
  "rows": [
    {
      "pe": 5.6
    }
  ],
  "answer": "已返回交通银行最新市盈率。",
  "error": ""
}
```

## 3. GET /api/v1/sql-copilot/query-scope

### 请求参数
```json
{}
```

### 接口返回
```json
{
  "tables": {
    "stock_basic_info": [
      {
        "name": "code",
        "type": "VARCHAR(20)",
        "nullable": false,
        "comment": "股票编码"
      }
    ],
    "stock_financial_report": [
      {
        "name": "report_period",
        "type": "VARCHAR(16)",
        "nullable": false,
        "comment": "报告期"
      }
    ]
  },
  "scope_summary": "这是可查询范围摘要。",
  "meta": {
    "embedding_model": "text-embedding-3-large",
    "embedding_dimensions": 3072
  }
}
```

## 4. POST /api/v1/sql-copilot/sessions/delete

### 请求参数
```json
{
  "session_id": "demo-session-001",
  "user_id": "song"
}
```

### 接口返回
```json
{
  "deleted": true
}
```

## 5. POST /api/v1/sql-copilot/sessions/list

### 请求参数
```json
{
  "user_id": "song",
  "limit": 50
}
```

### 接口返回
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
