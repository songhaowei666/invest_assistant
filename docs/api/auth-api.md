# 认证（Auth）HTTP 接口说明

本文档依据 `api/controllers/auth.py`、`api/schemas/auth.py`、`api/services/account_service.py` 及 `api/deps/auth.py` 整理。

全局路由前缀来自配置项 `API_PREFIX`，默认值为 **`/api/v1`**（见 `api/configs/config.py`）。下列 Path 均为该前缀之后的相对路径。

基准示例：`http://localhost:8000` + Path。

手动联调可参考仓库内命令清单：[`api/scripts/test_auth_flow_curl.txt`](../../api/scripts/test_auth_flow_curl.txt)。

---

## 通用约定

### Access 令牌（JWT）

- **请求头**：`Authorization: Bearer <access_token>`
- **适用接口**：需登录态的接口（例如 `GET /auth/me`）。**整组路由批量拦截**：在 `api/controllers/router.py` 中对 `include_router(positions_router, dependencies=[Depends(get_current_account_id)])` 已挂载，故 **`/api/v1/positions` 下全部接口**须带本头，否则 `401`。单接口可写 `Depends(get_current_account)` / `Depends(get_current_account_id)`。
- **载荷**：服务端签发时包含 `sub`（账户 UUID 字符串）、`exp`（过期时间）、`ver`（整数，与库表 `accounts.access_token_version` 一致才有效）。
- **失效场景**：`exp` 过期；`ver` 与数据库不一致（例如已调用 **刷新** 或 **登出** 后旧 access 作废）；签名错误。

### Refresh 令牌

- **传递方式**：请求 JSON 体字段 `refresh_token`（**不要**放在 `Authorization` 里，除非自行扩展；当前实现仅支持 body）。
- **存储**：服务端仅存哈希；明文仅在注册/登录/刷新响应中返回一次，请客户端安全保存。
- **旋转**：每次 `POST /auth/refresh` 成功后，旧 refresh 记录删除并签发新 refresh；旧 refresh 不可再用。

### Refresh 与登出对 Access 的影响

- 调用 **`POST /auth/refresh`** 或 **`POST /auth/logout`**（且 logout 能匹配到有效 refresh）成功后，账户的 **`access_token_version` 会递增**，此前签发的 **access JWT 一律作废**（即使未过期），需使用新 access 或重新登录。

### CSRF 字段

- 响应中的 `csrf_token` 当前为占位（空字符串）；纯 Bearer 场景下可不使用。

---

## 1. 注册

- **Method / Path**：`POST /api/v1/auth/register`
- **Content-Type**：`application/json`
- **说明**：创建账户并签发令牌（效果上等同注册后立即登录）。

**请求体（JSON）**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| email | string | 合法邮箱格式 | 入库为小写；唯一 |
| password | string | 非空 | 登录密码 |
| name | string | 可选 | 显示名；缺省时由邮箱本地部分推导 |

**请求示例**

```json
{
  "email": "user@example.com",
  "password": "YourPass123",
  "name": "昵称"
}
```

**成功响应**：`201 Created`，JSON 见「令牌响应结构」一节。

**错误响应**

| HTTP 状态码 | 说明 |
|-------------|------|
| 400 | 邮箱或密码等业务校验失败（`detail` 为字符串说明） |
| 409 | 邮箱已注册 |
| 422 | 请求体 JSON 非法或字段校验失败（FastAPI 标准 `detail` 结构） |

---

## 2. 登录

- **Method / Path**：`POST /api/v1/auth/login`
- **Content-Type**：`application/json`
- **说明**：邮箱 + 密码认证；成功则更新最近登录时间与 IP（若可解析），并签发新令牌对。

**请求体（JSON）**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| email | string | 合法邮箱格式 | 与注册时一致（小写存储） |
| password | string | 非空 | 密码 |
| invite_token | string | 可选 | 邀请场景下与密码配合为「无密码账户」首次设密；一般可不传 |

**请求示例**

```json
{
  "email": "user@example.com",
  "password": "YourPass123"
}
```

**成功响应**：`200 OK`，JSON 见「令牌响应结构」。

**错误响应**

| HTTP 状态码 | 说明 |
|-------------|------|
| 401 | 邮箱或密码错误等（`detail` 字符串） |
| 403 | 账户封禁等（`detail` 字符串） |
| 422 | 请求体非法或字段校验失败 |

---

## 3. 刷新令牌

- **Method / Path**：`POST /api/v1/auth/refresh`
- **Content-Type**：`application/json`
- **说明**：校验 refresh 后旋转存储，返回 **新** `access_token` 与 **新** `refresh_token`；并使此前所有 access JWT 作废（版本递增）。

**请求体（JSON）**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| refresh_token | string | 非空 | 当前有效的 refresh 明文 |

**请求示例**

```json
{
  "refresh_token": "<当前 refresh 明文>"
}
```

**成功响应**：`200 OK`，JSON 见「令牌响应结构」。

**错误响应**

| HTTP 状态码 | 说明 |
|-------------|------|
| 401 | refresh 无效、已过期或账户不可用（`detail` 字符串） |
| 422 | 请求体非法或字段校验失败 |

---

## 4. 登出

- **Method / Path**：`POST /api/v1/auth/logout`
- **Content-Type**：`application/json`
- **说明**：删除与 body 中 refresh 对应的库记录；若命中则递增 `access_token_version`，使当前 access 与其他旧 access 失效。**未命中 refresh 时仍返回 204**（幂等）。

**请求体（JSON）**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| refresh_token | string | 非空 | 要撤销的 refresh 明文 |

**成功响应**：`204 No Content`，**无响应体**。

**错误响应**

| HTTP 状态码 | 说明 |
|-------------|------|
| 422 | 请求体非法或字段校验失败 |

---

## 5. 当前用户

- **Method / Path**：`GET /api/v1/auth/me`
- **说明**：校验 access JWT（含 `ver` 与库一致），返回当前用户摘要；并在请求生命周期内写入 `user_context`（供下游按用户隔离逻辑使用）。

**请求头**

| 头 | 必填 | 说明 |
|----|------|------|
| Authorization | 是 | `Bearer <access_token>` |

**请求体**：无

**成功响应**：`200 OK`

```json
{
  "id": "6d6c4f88-b7b1-4334-83ff-0f4fbbe69661",
  "email": "user@example.com",
  "name": "昵称",
  "status": "active"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 账户 UUID |
| email | string | 邮箱（小写） |
| name | string | 显示名 |
| status | string | 如 `active` / `pending` / `banned` |

**错误响应**

| HTTP 状态码 | 说明 |
|-------------|------|
| 401 | 未携带 Bearer、令牌无效/过期、`ver` 不一致（已刷新或登出）、账户不存在或封禁（`detail` 字符串） |

---

## 令牌响应结构（注册 / 登录 / 刷新）

以下三种成功响应体结构相同（字段为蛇形命名，与 Pydantic 模型一致）。

```json
{
  "access_token": "<JWT>",
  "refresh_token": "<明文 refresh，仅此次响应可见>",
  "csrf_token": ""
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | string | JWT，供 `Authorization: Bearer` 使用 |
| refresh_token | string | 明文 refresh，仅用于 `POST /auth/refresh` 与 `POST /auth/logout` 的 body |
| csrf_token | string | 当前固定为空串，占位 |

---

## 环境与运维提示

- **JWT 配置**：`api/.env` 中需配置 `JWT_SECRET_KEY`（及可选 `ACCESS_TOKEN_EXPIRE_MINUTES`、`REFRESH_TOKEN_EXPIRE_DAYS` 等），见 `api/configs/config.py`。
- **数据表**：账户与 refresh 表由 `api/models/account.py` 定义；PostgreSQL 环境可执行 `api/scripts/create_account_tables.py` 建表/补列（**可重复执行**）。
- **升级后出现 `column accounts.access_token_version does not exist`**：说明库结构落后于当前 ORM。请在 `api` 目录下执行：  
  `python3 scripts/create_account_tables.py`  
  该脚本会 `ALTER TABLE accounts ADD COLUMN IF NOT EXISTS access_token_version ...` 并刷新列备注。执行后无需改代码，重启或重试登录即可。
- **CORS**：后端对前端源等配置见 `api/main.py` 中 `CORSMiddleware`；携带 Cookie 非本认证方案必需，Bearer 即可。

---

## 相关源码索引

| 模块 | 路径 |
|------|------|
| 路由 | `api/controllers/auth.py` |
| 请求/响应模型 | `api/schemas/auth.py` |
| 业务逻辑 | `api/services/account_service.py` |
| 登录态依赖 | `api/deps/auth.py` |
| ORM | `api/models/account.py` |
