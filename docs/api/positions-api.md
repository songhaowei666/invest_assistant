# 持仓（Positions）HTTP 接口说明

本文档依据 `api/controllers/positions.py` 及 `api/schemas/position.py` 整理。全局路由前缀来自配置项 `API_PREFIX`，默认值为 **`/api/v1`**（见 `api/configs/config.py`）。下列 Path 均为该前缀之后的相对路径。

**认证**：本模块全部接口在 `api/controllers/router.py` 中已挂载 `Depends(get_current_account_id)`，须在请求头携带 `Authorization: Bearer <access_token>`，否则返回 `401`。签发与刷新令牌见 [`auth-api.md`](./auth-api.md)。

**相关只读接口**：按当前持仓聚合「透视盈余」（快照、年报、市值加权组合指标）见独立模块 [`earnings-lens-api.md`](./earnings-lens-api.md)（`GET /api/v1/earnings-lens`），不在本文档 Path 下。

基准示例：`http://localhost:8000` + Path。

---

## 1. 查询持仓列表

- **Method / Path**：`GET /api/v1/positions`
- **说明**：返回当前库中全部持仓，按股票代码升序。
- **请求体**：无
- **成功响应**：`200`，JSON 结构如下。

```json
{
  "items": [
    {
      "id": 1,
      "code": "600519",
      "name": "贵州茅台",
      "price": 1728.36,
      "marketValue": 207403.2,
      "positionShares": 120,
      "positionCost": 1680.5,
      "dividendYield": 0.032,
      "totalDividend": 62.3
    }
  ]
}
```

- **字段说明（`items[]`，响应为驼峰命名）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| code | string | 股票代码 |
| name | string | 名称 |
| price | number | 当前价格 |
| marketValue | number | 市值 |
| positionShares | int | 持股数量 |
| positionCost | number | 持仓成本 |
| dividendYield | number | 股息率 |
| totalDividend | number | 年分红（对应库字段 `annual_dividend`） |

---

## 2. 批量新增持仓

- **Method / Path**：`POST /api/v1/positions/add`
- **Content-Type**：`application/json`
- **请求体**：JSON **数组**；每个元素字段与 ORM 一致，为 **蛇形命名**。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | string | 1～20 字符 | 股票代码，全局唯一 |
| name | string | 1～100 字符 | 名称 |
| price | number | | 当前价格 |
| market_value | number | | 市值 |
| position_shares | int | | 持股数量 |
| position_cost | number | | 持仓成本 |
| dividend_yield | number | | 股息率 |
| annual_dividend | number | | 年分红 |

**请求示例**

```json
[
  {
    "code": "600000",
    "name": "浦发银行",
    "price": 8.5,
    "market_value": 8500.0,
    "position_shares": 1000,
    "position_cost": 8.2,
    "dividend_yield": 0.04,
    "annual_dividend": 0.32
  }
]
```

- **成功响应**：`200`，结构与「1. 查询持仓列表」相同（返回更新后的全表 `items`）。
- **错误响应**
  - `422`：同一请求数组内 `code` 重复。
  - `409`：某 `code` 在数据库中已存在。

---

## 3. 批量删除持仓

- **Method / Path**：`POST /api/v1/positions/delete`
- **Content-Type**：`application/json`
- **请求体**：JSON **数组**；每项仅含 `code`。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| code | string | 1～20 字符 | 待删除股票代码 |

**请求示例**

```json
[
  { "code": "600000" },
  { "code": "601328" }
]
```

- **成功响应**：`200`，结构与「1. 查询持仓列表」相同。
- **错误响应**
  - `404`：某一 `code` 在库中不存在（detail 中会指明代码）。

---

## 4. 批量全量修改持仓

- **Method / Path**：`POST /api/v1/positions/modify`
- **Content-Type**：`application/json`
- **请求体**：JSON **数组**；元素字段与「2. 批量新增」相同（蛇形命名）。按 `code` 定位记录并 **整行覆盖** 除主键外的业务字段。

**请求示例**

```json
[
  {
    "code": "600519",
    "name": "贵州茅台",
    "price": 1700.0,
    "market_value": 204000.0,
    "position_shares": 120,
    "position_cost": 1680.5,
    "dividend_yield": 0.032,
    "annual_dividend": 62.3
  }
]
```

- **成功响应**：`200`，结构与「1. 查询持仓列表」相同。
- **错误响应**
  - `404`：某一 `code` 在库中不存在。

---

## 5. 股票名称模糊搜索（返回代码与名称）

- **Method / Path**：`GET /api/v1/positions/stock-name-suggest`
- **说明**：用户输入部分股票名称，后端使用 `LIKE` 在 `stock_all_info` 表中检索相似项，返回股票代码和名称列表。
- **请求参数（Query）**

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| keyword | string | 是 | 无 | 最小长度 1 | 股票名称关键词，例如“茅台” |
| limit | int | 否 | 10 | 1～100 | 返回条数上限 |

**请求示例**

```text
GET /api/v1/positions/stock-name-suggest?keyword=茅台&limit=10
```

**成功响应（200）**

```json
{
  "items": [
    {
      "code": "600519",
      "name": "贵州茅台"
    }
  ]
}
```

- **字段说明（`items[]`）**

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 股票代码 |
| name | string | 股票名称 |

---

## 6. 按股票代码查询价格与股息率

- **Method / Path**：`GET /api/v1/positions/price-dividend`
- **说明**：根据股票代码，从 `stock_basic_info` 表查询该代码的当前价格与股息率（`code` 须在该表中存在；与持仓表是否录入该代码无关）。
- **请求参数（Query）**

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|------|------|------|--------|------|------|
| code | string | 是 | 无 | 1～20 字符 | 股票代码，例如 `600519` |

**请求示例**

```text
GET /api/v1/positions/price-dividend?code=600519
```

**成功响应（200）**

```json
{
  "code": "600519",
  "price": 1700.0,
  "dividendYield": 0.032
}
```

**错误响应**

- `404`：股票代码在持仓表中不存在。

---

## 通用说明

- 所有写操作在服务端成功后会 **提交事务**（`commit`），成功时返回的均为 **当前全表** 列表。
- 若部署时修改了 `API_PREFIX`，请将本文档中的 `/api/v1` 替换为实际前缀。
