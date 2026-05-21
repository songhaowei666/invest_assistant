---
name: get-current-positions
description: "获取当前持仓股票列表，返回包含股票代码、名称、价格、持仓股数、持仓成本、分红等字段的 JSON。"
---

# 获取当前持仓股票技能

## 功能描述

读取系统中的当前持仓股票数据，并以 JSON 格式输出。

## 执行流程（必须遵守）

1. 收到“查看持仓 / 当前持仓 / 持仓股票列表”等请求后，直接执行脚本
2. 命令：`python3 skills/get-current-positions/scripts/get_current_positions.py`
3. workdir 为工作区根目录（`api`）
4. 将脚本输出 JSON 直接返回给用户

## 使用方式

```bash
python3 skills/get-current-positions/scripts/get_current_positions.py
```

## 触发示例

- "获取当前持仓"
- "查询我现在持有哪些股票"
- "给我持仓股票列表"

## 输出格式

脚本输出 JSON，主要字段：

- `count`: 持仓数量
- `items`: 持仓列表，元素包含 `code`、`name`、`price`、`marketValue`、`positionShares`、`positionCost`、`dividendYield`、`totalDividend`
