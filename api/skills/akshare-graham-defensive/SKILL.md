---
name: akshare-graham-defensive
description: "判断单只 A 股在指定日期（为空则当前日期）是否符合格雷厄姆防御型投资者七条标准，并输出该股相关数据 JSON。"
---

# Akshare 格雷厄姆防御型选股技能（单股）

## 功能描述

基于 akshare 获取**单只股票**的行情与财务数据，按格雷厄姆防御型投资者七条标准逐条校验，输出是否全部满足及各项明细数据。**不扫描全市场。**

## 前置条件

1. 已安装依赖：`pip install akshare pandas openpyxl`
2. 网络可访问 akshare 数据源（或已用 `update_cache.py` 预拉缓存 xlsx）

## 执行流程（必须遵守）

1. 收到单股格雷厄姆校验请求后，直接执行脚本
2. 命令：`python skills/akshare-graham-defensive/scripts/get_graham_defensive_count.py <股票代码> [日期]`
3. `股票代码` 必填，支持 `600519.SH`、`000001.SZ` 或仅 6 位数字
4. `日期` 可选；为空则当前日期，格式支持 `YYYY-MM-DD` 或 `YYYYMMDD`
5. workdir 为工作区根目录
6. 将脚本输出 JSON 直接返回给用户

## 使用方式

```bash
python skills/akshare-graham-defensive/scripts/get_graham_defensive_count.py 600519.SH
python skills/akshare-graham-defensive/scripts/get_graham_defensive_count.py 600519 2025-12-31
```

## 触发示例

- "贵州茅台 600519 是否符合格雷厄姆防御型条件"
- "查一下 000001.SZ 在 2024-12-31 是否满足格雷厄姆七条"
- "单只股票按格雷厄姆规则校验并给出数据"

## 输出格式

脚本输出 JSON，主要字段：

- `stock_code` / `stock_name`: 股票代码与名称
- `query_date`: 查询日期
- `meets_all_criteria`: 七条是否全部通过
- `criteria_checks`: 长度为 7 的列表，每项含 `id`、`name`、`rule`、`passed` 及明细字段
- `financial_block_passed` / `financial_error`: 财务侧汇总与错误说明
- `spot_snapshot_raw`: 雪球个股快照原始键值（便于核对市值、快照 PE/PB）
