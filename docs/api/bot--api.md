# 机器人（Bot）HTTP 接口

本文档对应 `api/controllers/bot.py` 中注册的接口。应用将路由挂在 `settings.API_PREFIX` 下（默认 **`/api/v1`**），故下列路径需加上此前缀，例如：`POST /api/v1/bot/sessions/list`。

所有接口均为 **`POST`**，请求体为 **JSON**（`Content-Type: application/json`），除非另有说明。

---

## 1. 历史会话列表

- **路径**：`/bot/sessions/list`
- **方法**：`POST`
- **说明**：返回当前已持久化的会话列表，字段形态与 nanobot 示例中的 listSessions 对齐。底层按 **`created_at` 倒序** 排列（新建会话在前）；`title` 来自 PostgreSQL `nanobot_session.title` 列（旧数据可能为空，此时列表可能回退展示 `metadata_json` 中的 `title`，兼容 WebUI 等历史形态）。

### 请求体

可为空对象 `{}`，字段当前未使用。

### 响应体（JSON）

| 字段 | 类型 | 说明 |
|------|------|------|
| sessions | array | 会话条目列表 |

**sessions[] 每项字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| key | string | 会话标识，例如 `api:xxxx` |
| created_at | string / null | 创建时间 |
| updated_at | string / null | 最后更新时间 |
| title | string | 展示标题；未改名时通常由首条用户提问摘要生成；用户通过「修改标题」接口改名后会写入本字段并标记元数据 `title_user_edited`，避免被默认逻辑覆盖 |
| preview | string | 预留，当前固定为空字符串 |

### 示例

```http
POST /api/v1/bot/sessions/list
Content-Type: application/json

{}
```

---

## 2. 删除会话

- **路径**：`/bot/sessions/delete`
- **方法**：`POST`
- **说明**：按 `key` 删除指定会话。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | 是 | 会话 key，例如 `api:xxxx` |

### 响应体（JSON）

| 字段 | 类型 | 说明 |
|------|------|------|
| deleted | boolean | 是否删除成功（由底层 `delete_session` 返回值决定） |

### 示例

```http
POST /api/v1/bot/sessions/delete
Content-Type: application/json

{"key": "api:my-thread-001"}
```

---

## 3. 修改会话标题

- **路径**：`/bot/sessions/title`
- **方法**：`POST`
- **说明**：重命名已存在的会话（写入 `nanobot_session.title`，并设置元数据 `title_user_edited`，后续保存不会因「首问摘要」逻辑覆盖标题）。会话必须在数据库中已存在（至少落库过一次）；`title` 去空格后不能为空。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | 是 | 会话 key |
| title | string | 是 | 新标题，长度 1～512（与 `SessionTitleIn` 校验一致） |

### 响应体（JSON）

| 字段 | 类型 | 说明 |
|------|------|------|
| updated | boolean | 是否更新成功（会话不存在或标题非法时为 `false`） |

### 示例

```http
POST /api/v1/bot/sessions/title
Content-Type: application/json

{"key": "api:my-thread-001", "title": "复盘笔记"}
```

---

## 4. 查询会话历史

- **路径**：`/bot/sessions/history`
- **方法**：`POST`
- **说明**：按 `key` 读取会话，返回尾部若干条消息。若磁盘上尚无该会话，会自动创建空会话后再返回（消息列表可为空）。单条消息仅暴露部分字段（见下表）。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | 是 | 会话 key |
| limit | integer | 否 | 取最近多少条，默认 `30`，范围 **1～200** |

### 响应体（JSON）

| 字段 | 类型 | 说明 |
|------|------|------|
| key | string | 会话 key |
| created_at | string / null | 会话创建时间 |
| updated_at | string / null | 会话更新时间 |
| messages | array | 消息列表（自旧到新顺序中的尾部 `limit` 条） |

**messages[] 每条可能出现的字段**（仅当原始消息中存在该键时才会出现）：

| 字段 | 类型 | 说明 |
|------|------|------|
| role | string | 角色 |
| content | string | 文本内容 |
| timestamp | number / string | 时间戳（具体类型以存储为准） |
| tool_calls | array / object | 工具调用信息 |
| tool_call_id | string | 工具调用 id |
| name | string | 名称（如工具名） |

### 示例

```http
POST /api/v1/bot/sessions/history
Content-Type: application/json

{"key": "api:my-thread-001", "limit": 30}
```

---

## 5. 流式聊天

- **路径**：`/bot/chat`
- **方法**：`POST`
- **说明**：用户发送一条文本，服务端以 **Server-Sent Events（SSE）** 流式返回，事件体为 **OpenAI 兼容** 的 `chat.completion.chunk` JSON。同一 `key` 上的聊天请求在服务端会 **串行化**（按会话加锁）。单次处理超时约 **120 秒**。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | 是 | 会话 key；新会话可由前端生成唯一 key |
| content | string | 是 | 用户输入内容 |

### 响应

- **Content-Type**：`text/event-stream`
- **建议响应头**（服务端已设置）：`Cache-Control: no-cache`，`Connection: keep-alive`

### SSE 数据行格式

每行形如：`data: <JSON>\n\n`

- 流式阶段：多条 `data: {...}`，每条为 OpenAI 风格的 chunk，其中 `choices[0].delta` 可能包含 `content` 字段表示增量文本。
- 结束前：会发送一条 `delta` 为空对象、`finish_reason` 为 `"stop"` 的 chunk。
- 流结束标记：`data: [DONE]\n\n`

若流式过程中未产出任何 token，服务可能将最终回复整段作为一次或多次 chunk 补发（与 `bot_service.chat_sse_tokens` 行为一致）。

### 示例

```http
POST /api/v1/bot/chat
Content-Type: application/json

{"key": "api:my-thread-001", "content": "你好"}
```

客户端需按 SSE 解析 `data:` 行，并对每行 JSON 做增量合并或展示。

---

## 实现与依赖说明（供联调参考）

- 控制器：`api/controllers/bot.py`
- 业务逻辑：`api/services/bot_service.py`（懒加载 `Nanobot.from_config()`，会话与 Agent 循环与 nanobot 集成）
- 与 nanobot HTTP 约定一致的内部常量：`API_CHAT_ID = "default"`，渠道为 `api`。
- 会话主表 `nanobot_session` 含独立 **`title`** 列（展示用）；首次持久化时由 `SessionManager` / `effective_session_title_for_persist` 按规则写入（含首问摘要、WebUI 元数据标题、用户改名等优先级）。已有库需执行 `api/scripts/create_nanobot_tables.py` 以 **`ADD COLUMN IF NOT EXISTS`** 补列（脚本内对 `nanobot_session` 在刷新 COMMENT 前会先补 `title` 列）。
