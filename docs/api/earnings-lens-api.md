# 透视盈余（Earnings Lens）HTTP 接口说明

本文档依据 [`earnings_lens` 控制器](../../api/controllers/earnings_lens.py)、[`earnings_lens_service` 服务](../../api/services/earnings_lens_service.py) 与 [`earnings_lens` 响应模型](../../api/schemas/earnings_lens.py) 整理。全局路由前缀为 `API_PREFIX`，默认 **`/api/v1`**。

与「持仓」写接口分离：本模块仅 **只读聚合**，数据源为当前 `positions` 表、`stock_basic_info`、`stock_financial_report`。持仓 CRUD 仍见 [`positions-api.md`](./positions-api.md)。

---

## 查询透视盈余

- **Method / Path**：`GET /api/v1/earnings-lens`
- **说明**：
  - 按当前持仓 `code` 左联 `stock_basic_info` 生成每行 `snapshot`；无对应行时 `snapshot` 为 `null`。
  - 对 `stock_financial_report` 取报告期以 `1231` 结尾的年报记录，每只股票最多 **4** 条（按报告期从新到旧），写入 `annualReports`。
  - **持仓市值**：`marketValue` 取自持仓表 `market_value`；缺失、非有限或小于 0 时按 **0**；`totalMarketValue` 为各持仓该值之和。
  - **市值占比**：`marketWeight` = `marketValue / totalMarketValue`（`totalMarketValue` 为 0 时全为 0）。
  - **组合加权（`mcWeighted`）**：各加权指标仅在「市值大于 0 且有有效快照字段」的标的内按市值加权；PE、PB 仅统计正值；无有效样本时对应加权值为 **0**（非 null）。`countForPe` 等为参与该指标加权的只数。

- **请求体**：无

- **成功响应**：`200`，`Content-Type: application/json`

### 响应体结构（驼峰）

根对象含 `summary`、`mcWeighted`、`rows` 三个字段。

**成功响应示例（节选）**

```json
{
  "summary": {
    "positionCount": 5,
    "withBasicSnapshotCount": 3
  },
  "mcWeighted": {
    "totalMarketValue": 350000.0,
    "weightedPe": 12.34,
    "weightedPb": 1.05,
    "weightedRoe": 10.5,
    "weightedDividendYield": 3.2,
    "weightedGrossProfitMargin": 25.0,
    "weightedDebtToAssetRatio": 45.0,
    "countForPe": 3,
    "countForPb": 3,
    "countForRoe": 3,
    "countForDividendYield": 3,
    "countForGrossProfitMargin": 3,
    "countForDebtToAssetRatio": 3
  },
  "rows": [
    {
      "code": "600519",
      "name": "贵州茅台",
      "marketValue": 207403.2,
      "marketWeight": 0.59258,
      "snapshot": {
        "pe": 28.5,
        "pb": 8.2,
        "price": 1728.36,
        "roe": 31.2,
        "grossProfitMargin": 91.5,
        "operatingRevenue": 1.23e11,
        "netProfit": 6.2e10,
        "dividendYield": 3.2,
        "eps": 50.1,
        "bps": 210.5,
        "debtToAssetRatio": 19.5
      },
      "annualReports": [
        {
          "reportPeriod": "20241231",
          "operatingRevenue": 1.23e11,
          "grossProfitMargin": 91.5,
          "netProfit": 6.2e10,
          "roe": 31.2,
          "debtToAssetRatio": 19.5,
          "eps": 50.1,
          "bps": 210.5
        }
      ]
    }
  ]
}
```

### `summary` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| positionCount | int | 当前持仓只数 |
| withBasicSnapshotCount | int | 在 `stock_basic_info` 中存在对应 `code` 行的只数 |

### `mcWeighted` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| totalMarketValue | number | 各持仓 `market_value` 安全化后的总和（见上文「持仓市值」） |
| weightedPe | number | 加权市盈率 TTM；无样本时为 0 |
| weightedPb | number | 加权市净率；无样本时为 0 |
| weightedRoe | number | 加权 ROE（与快照字段单位一致，一般为百分比数值）；无样本时为 0 |
| weightedDividendYield | number | 加权股息率；无样本时为 0 |
| weightedGrossProfitMargin | number | 加权毛利率；无样本时为 0 |
| weightedDebtToAssetRatio | number | 加权资产负债率；无样本时为 0 |
| countForPe | int | 参与 PE 加权的只数 |
| countForPb | int | 参与 PB 加权的只数 |
| countForRoe | int | 参与 ROE 加权的只数 |
| countForDividendYield | int | 参与股息率加权的只数 |
| countForGrossProfitMargin | int | 参与毛利率加权的只数 |
| countForDebtToAssetRatio | int | 参与资产负债率加权的只数 |

### `rows[]` 每行字段

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 股票代码 |
| name | string | 股票名称 |
| marketValue | number | 持仓市值（缺失等按 0） |
| marketWeight | number | 占 `mcWeighted.totalMarketValue` 的比例，0～1 |
| snapshot | object \| null | `stock_basic_info` 映射；无行时为 `null` |
| annualReports | array | 年报指标点列表，见模型 `EarningsLensReportPoint` |

### `snapshot` 与 `annualReports[]` 内指标

字段名均为驼峰，与 [`api/schemas/earnings_lens.py`](../../api/schemas/earnings_lens.py) 中 `EarningsLensSnapshot`、`EarningsLensReportPoint` 一致；单位与含义与 ORM 列 COMMENT（`stock_basic_info` / `stock_financial_report`）一致。

---

## 通用说明

- 若部署时修改了 `API_PREFIX`，请将本文档中的 `/api/v1` 替换为实际前缀。
- 无持仓时返回 `rows: []`，`summary.positionCount` 为 0，`mcWeighted` 各加权指标为 0，`totalMarketValue` 为 0。
