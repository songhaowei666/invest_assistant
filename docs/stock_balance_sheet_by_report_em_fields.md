# stock_balance_sheet_by_report_em 输出字段说明

东方财富-股票-财务分析-**资产负债表（按报告期）**。数据来源于 AKShare 接口 `stock_balance_sheet_by_report_em`，单次请求返回指定 `symbol` 的多期报表行；每行 **319 列**，列名以东方财富接口英文字段为主，其中大量 `*_YOY` 列为对应科目的**同比**相关指标。

**接口示例**

```python
import akshare as ak

df = ak.stock_balance_sheet_by_report_em(symbol="SH600519")
```

**参考页面**：[东方财富 F10 财务分析](https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519)

---

## 输入参数

| 名称 | 类型 | 描述 |
|------|------|------|
| symbol | str | 股票代码，如 `SH600519`（沪市前缀 SH，深市 SZ） |

---

## 字段结构总览

| 分组 | 列数 | 说明 |
|------|------|------|
| 证券与报告元数据 | 12 | 代码、简称、报告期、公告日、币种等 |
| 资产负债表科目（绝对额） | 152 | 各资产负债权益明细科目 |
| 资产负债表科目（同比） | 152 | 与上表一一对应的 `*_YOY` 列 |
| 意见与状态 | 3 | 审计意见类型、上市状态等 |

**说明**：具体数值含义（如是否为比率、是否百分比）以东财原始接口为准；本表仅整理**可提供字段名**及常用中文对照，便于落库与映射。

---

## 一、证券与报告元数据（12 列）

| 序号 | 字段名 | 说明 |
|------|--------|------|
| 1 | SECUCODE | 证券代码（含交易所后缀，如 600519.SH） |
| 2 | SECURITY_CODE | 股票代码 |
| 3 | SECURITY_NAME_ABBR | 证券简称 |
| 4 | ORG_CODE | 机构/公司代码 |
| 5 | ORG_TYPE | 机构类型 |
| 6 | REPORT_DATE | 报告期日期 |
| 7 | REPORT_TYPE | 报告类型 |
| 8 | REPORT_DATE_NAME | 报告期名称（展示用） |
| 9 | SECURITY_TYPE_CODE | 证券类型代码 |
| 10 | NOTICE_DATE | 公告日期 |
| 11 | UPDATE_DATE | 数据更新日期 |
| 12 | CURRENCY | 币种 |

---

## 二、资产负债表科目—绝对额（152 列）

| 序号 | 字段名 | 说明 |
|------|--------|------|
| 13 | ACCEPT_DEPOSIT_INTERBANK | 存放同业及其他金融机构款项 |
| 14 | ACCOUNTS_PAYABLE | 应付账款 |
| 15 | ACCOUNTS_RECE | 应收账款 |
| 16 | ACCRUED_EXPENSE | 预提费用 / 应付费用 |
| 17 | ADVANCE_RECEIVABLES | 预收款项 / 合同负债相关预收 |
| 18 | AGENT_TRADE_SECURITY | 代理买卖证券款 |
| 19 | AGENT_UNDERWRITE_SECURITY | 代理承销证券款 |
| 20 | AMORTIZE_COST_FINASSET | 以摊余成本计量的金融资产 |
| 21 | AMORTIZE_COST_FINLIAB | 以摊余成本计量的金融负债 |
| 22 | AMORTIZE_COST_NCFINASSET | 以摊余成本计量的非流动金融资产 |
| 23 | AMORTIZE_COST_NCFINLIAB | 以摊余成本计量的非流动金融负债 |
| 24 | APPOINT_FVTPL_FINASSET | 指定为以公允价值计量且其变动计入当期损益的金融资产 |
| 25 | APPOINT_FVTPL_FINLIAB | 指定为以公允价值计量且其变动计入当期损益的金融负债 |
| 26 | ASSET_BALANCE | 资产类平衡/轧差项（接口定义） |
| 27 | ASSET_OTHER | 其他资产 |
| 28 | ASSIGN_CASH_DIVIDEND | 应付股利 |
| 29 | AVAILABLE_SALE_FINASSET | 可供出售金融资产（历史科目名，部分报表仍沿用） |
| 30 | BOND_PAYABLE | 应付债券 |
| 31 | BORROW_FUND | 拆入资金 |
| 32 | BUY_RESALE_FINASSET | 买入返售金融资产 |
| 33 | CAPITAL_RESERVE | 资本公积 |
| 34 | CIP | 在建工程 |
| 35 | CONSUMPTIVE_BIOLOGICAL_ASSET | 消耗性生物资产 |
| 36 | CONTRACT_ASSET | 合同资产 |
| 37 | CONTRACT_LIAB | 合同负债 |
| 38 | CONVERT_DIFF | 外币报表折算差额 |
| 39 | CREDITOR_INVEST | 债权投资 |
| 40 | CURRENT_ASSET_BALANCE | 流动资产平衡项 |
| 41 | CURRENT_ASSET_OTHER | 其他流动资产 |
| 42 | CURRENT_LIAB_BALANCE | 流动负债平衡项 |
| 43 | CURRENT_LIAB_OTHER | 其他流动负债 |
| 44 | DEFER_INCOME | 递延收益 |
| 45 | DEFER_INCOME_1YEAR | 一年内到期的递延收益 |
| 46 | DEFER_TAX_ASSET | 递延所得税资产 |
| 47 | DEFER_TAX_LIAB | 递延所得税负债 |
| 48 | DERIVE_FINASSET | 衍生金融资产 |
| 49 | DERIVE_FINLIAB | 衍生金融负债 |
| 50 | DEVELOP_EXPENSE | 开发支出 |
| 51 | DIV_HOLDSALE_ASSET | 划分为持有待售的资产 |
| 52 | DIV_HOLDSALE_LIAB | 划分为持有待售的负债 |
| 53 | DIVIDEND_PAYABLE | 应付股利（与 ASSIGN_CASH_DIVIDEND 口径以源数据为准） |
| 54 | DIVIDEND_RECE | 应收股利 |
| 55 | EQUITY_BALANCE | 权益平衡项 |
| 56 | EQUITY_OTHER | 其他权益工具等权益其他项 |
| 57 | EXPORT_REFUND_RECE | 应收出口退税 |
| 58 | FEE_COMMISSION_PAYABLE | 应付手续费及佣金 |
| 59 | FIN_FUND | 融出资金 / 金融业务相关资金 |
| 60 | FINANCE_RECE | 应收融资租赁款等 |
| 61 | FIXED_ASSET | 固定资产 |
| 62 | FIXED_ASSET_DISPOSAL | 固定资产清理 / 持有待售固定资产 |
| 63 | FVTOCI_FINASSET | 以公允价值计量且其变动计入其他综合收益的金融资产 |
| 64 | FVTOCI_NCFINASSET | 非流动：以公允价值计量且其变动计入其他综合收益的金融资产 |
| 65 | FVTPL_FINASSET | 以公允价值计量且其变动计入当期损益的金融资产 |
| 66 | FVTPL_FINLIAB | 以公允价值计量且其变动计入当期损益的金融负债 |
| 67 | GENERAL_RISK_RESERVE | 一般风险准备 |
| 68 | GOODWILL | 商誉 |
| 69 | HOLD_MATURITY_INVEST | 持有至到期投资（历史科目） |
| 70 | HOLDSALE_ASSET | 持有待售资产 |
| 71 | HOLDSALE_LIAB | 持有待售负债 |
| 72 | INSURANCE_CONTRACT_RESERVE | 保险合同准备金 |
| 73 | INTANGIBLE_ASSET | 无形资产 |
| 74 | INTEREST_PAYABLE | 应付利息 |
| 75 | INTEREST_RECE | 应收利息 |
| 76 | INTERNAL_PAYABLE | 内部应付款 |
| 77 | INTERNAL_RECE | 内部应收款 |
| 78 | INVENTORY | 存货 |
| 79 | INVEST_REALESTATE | 投资性房地产 |
| 80 | LEASE_LIAB | 租赁负债 |
| 81 | LEND_FUND | 拆出资金 |
| 82 | LIAB_BALANCE | 负债平衡项 |
| 83 | LIAB_EQUITY_BALANCE | 负债和权益总计平衡项 |
| 84 | LIAB_EQUITY_OTHER | 负债和所有者权益其他 |
| 85 | LIAB_OTHER | 其他负债 |
| 86 | LOAN_ADVANCE | 发放贷款及垫款 |
| 87 | LOAN_PBC | 向中央银行借款 |
| 88 | LONG_EQUITY_INVEST | 长期股权投资 |
| 89 | LONG_LOAN | 长期借款 |
| 90 | LONG_PAYABLE | 长期应付款 |
| 91 | LONG_PREPAID_EXPENSE | 长期待摊费用 |
| 92 | LONG_RECE | 长期应收款 |
| 93 | LONG_STAFFSALARY_PAYABLE | 长期应付职工薪酬 |
| 94 | MINORITY_EQUITY | 少数股东权益 |
| 95 | MONETARYFUNDS | 货币资金 |
| 96 | NONCURRENT_ASSET_1YEAR | 一年内到期的非流动资产 |
| 97 | NONCURRENT_ASSET_BALANCE | 非流动资产平衡项 |
| 98 | NONCURRENT_ASSET_OTHER | 其他非流动资产（接口细分项以外的其他） |
| 99 | NONCURRENT_LIAB_1YEAR | 一年内到期的非流动负债 |
| 100 | NONCURRENT_LIAB_BALANCE | 非流动负债平衡项 |
| 101 | NONCURRENT_LIAB_OTHER | 其他非流动负债 |
| 102 | NOTE_ACCOUNTS_PAYABLE | 应付票据及应付账款（或应付票据相关，以东财列示为准） |
| 103 | NOTE_ACCOUNTS_RECE | 应收票据及应收账款 |
| 104 | NOTE_PAYABLE | 应付票据 |
| 105 | NOTE_RECE | 应收票据 |
| 106 | OIL_GAS_ASSET | 油气资产 |
| 107 | OTHER_COMPRE_INCOME | 其他综合收益 |
| 108 | OTHER_CREDITOR_INVEST | 其他债权投资 |
| 109 | OTHER_CURRENT_ASSET | 其他流动资产 |
| 110 | OTHER_CURRENT_LIAB | 其他流动负债 |
| 111 | OTHER_EQUITY_INVEST | 其他权益工具投资 |
| 112 | OTHER_EQUITY_OTHER | 其他权益工具—其他 |
| 113 | OTHER_EQUITY_TOOL | 其他权益工具 |
| 114 | OTHER_NONCURRENT_ASSET | 其他非流动资产 |
| 115 | OTHER_NONCURRENT_FINASSET | 其他非流动金融资产 |
| 116 | OTHER_NONCURRENT_LIAB | 其他非流动负债 |
| 117 | OTHER_PAYABLE | 其他应付款 |
| 118 | OTHER_RECE | 其他应收款 |
| 119 | PARENT_EQUITY_BALANCE | 归属于母公司所有者权益平衡项 |
| 120 | PARENT_EQUITY_OTHER | 归属于母公司所有者权益其他 |
| 121 | PERPETUAL_BOND | 永续债（权益部分列示） |
| 122 | PERPETUAL_BOND_PAYBALE | 永续债（负债部分/应付永续债，字段名源数据拼写为 PAYBALE） |
| 123 | PREDICT_CURRENT_LIAB | 预计流动负债 |
| 124 | PREDICT_LIAB | 预计负债 |
| 125 | PREFERRED_SHARES | 优先股（权益） |
| 126 | PREFERRED_SHARES_PAYBALE | 应付优先股（字段名源数据拼写为 PAYBALE） |
| 127 | PREMIUM_RECE | 应收保费 |
| 128 | PREPAYMENT | 预付款项 |
| 129 | PRODUCTIVE_BIOLOGY_ASSET | 生产性生物资产 |
| 130 | PROJECT_MATERIAL | 工程物资 |
| 131 | RC_RESERVE_RECE | 应收分保合同准备金等 |
| 132 | REINSURE_PAYABLE | 应付分保账款 |
| 133 | REINSURE_RECE | 应收分保账款 |
| 134 | SELL_REPO_FINASSET | 卖出回购金融资产款 |
| 135 | SETTLE_EXCESS_RESERVE | 结算备付金 |
| 136 | SHARE_CAPITAL | 股本 / 实收资本 |
| 137 | SHORT_BOND_PAYABLE | 应付短期债券 |
| 138 | SHORT_FIN_PAYABLE | 短期应付债券等短期金融负债 |
| 139 | SHORT_LOAN | 短期借款 |
| 140 | SPECIAL_PAYABLE | 专项应付款 |
| 141 | SPECIAL_RESERVE | 专项储备 |
| 142 | STAFF_SALARY_PAYABLE | 应付职工薪酬 |
| 143 | SUBSIDY_RECE | 应收补贴款 |
| 144 | SURPLUS_RESERVE | 盈余公积 |
| 145 | TAX_PAYABLE | 应交税费 |
| 146 | TOTAL_ASSETS | 资产总计 |
| 147 | TOTAL_CURRENT_ASSETS | 流动资产合计 |
| 148 | TOTAL_CURRENT_LIAB | 流动负债合计 |
| 149 | TOTAL_EQUITY | 所有者权益（或股东权益）合计 |
| 150 | TOTAL_LIAB_EQUITY | 负债和所有者权益总计 |
| 151 | TOTAL_LIABILITIES | 负债合计 |
| 152 | TOTAL_NONCURRENT_ASSETS | 非流动资产合计 |
| 153 | TOTAL_NONCURRENT_LIAB | 非流动负债合计 |
| 154 | TOTAL_OTHER_PAYABLE | 其他应付款合计（接口汇总项） |
| 155 | TOTAL_OTHER_RECE | 其他应收款合计（接口汇总项） |
| 156 | TOTAL_PARENT_EQUITY | 归属于母公司所有者权益合计 |
| 157 | TRADE_FINASSET | 交易性金融资产 |
| 158 | TRADE_FINASSET_NOTFVTPL | 交易性金融资产（非 FVTPL 分类部分，以东财为准） |
| 159 | TRADE_FINLIAB | 交易性金融负债 |
| 160 | TRADE_FINLIAB_NOTFVTPL | 交易性金融负债（非 FVTPL 分类部分） |
| 161 | TREASURY_SHARES | 库存股 |
| 162 | UNASSIGN_RPOFIT | 未分配利润（源字段名拼写为 RPOFIT） |
| 163 | UNCONFIRM_INVEST_LOSS | 未确认投资损失 |
| 164 | USERIGHT_ASSET | 使用权资产 |

---

## 三、资产负债表科目—同比（152 列）

与第二节科目**一一对应**，字段名为「第二节英文名 + `_YOY`」。表示该科目在东财接口中的**同比增长/同比变动**口径数据（具体为增长率还是变动额需结合返回数值与东财页面核对）。

| 序号 | 字段名 | 说明 |
|------|--------|------|
| 165 | ACCEPT_DEPOSIT_INTERBANK_YOY | 存放同业款项—同比 |
| 166 | ACCOUNTS_PAYABLE_YOY | 应付账款—同比 |
| 167 | ACCOUNTS_RECE_YOY | 应收账款—同比 |
| 168 | ACCRUED_EXPENSE_YOY | 预提费用—同比 |
| 169 | ADVANCE_RECEIVABLES_YOY | 预收款项—同比 |
| 170 | AGENT_TRADE_SECURITY_YOY | 代理买卖证券款—同比 |
| 171 | AGENT_UNDERWRITE_SECURITY_YOY | 代理承销证券款—同比 |
| 172 | AMORTIZE_COST_FINASSET_YOY | 以摊余成本计量的金融资产—同比 |
| 173 | AMORTIZE_COST_FINLIAB_YOY | 以摊余成本计量的金融负债—同比 |
| 174 | AMORTIZE_COST_NCFINASSET_YOY | 以摊余成本计量的非流动金融资产—同比 |
| 175 | AMORTIZE_COST_NCFINLIAB_YOY | 以摊余成本计量的非流动金融负债—同比 |
| 176 | APPOINT_FVTPL_FINASSET_YOY | 指定 FVTPL 金融资产—同比 |
| 177 | APPOINT_FVTPL_FINLIAB_YOY | 指定 FVTPL 金融负债—同比 |
| 178 | ASSET_BALANCE_YOY | 资产平衡项—同比 |
| 179 | ASSET_OTHER_YOY | 其他资产—同比 |
| 180 | ASSIGN_CASH_DIVIDEND_YOY | 应付股利—同比 |
| 181 | AVAILABLE_SALE_FINASSET_YOY | 可供出售金融资产—同比 |
| 182 | BOND_PAYABLE_YOY | 应付债券—同比 |
| 183 | BORROW_FUND_YOY | 拆入资金—同比 |
| 184 | BUY_RESALE_FINASSET_YOY | 买入返售金融资产—同比 |
| 185 | CAPITAL_RESERVE_YOY | 资本公积—同比 |
| 186 | CIP_YOY | 在建工程—同比 |
| 187 | CONSUMPTIVE_BIOLOGICAL_ASSET_YOY | 消耗性生物资产—同比 |
| 188 | CONTRACT_ASSET_YOY | 合同资产—同比 |
| 189 | CONTRACT_LIAB_YOY | 合同负债—同比 |
| 190 | CONVERT_DIFF_YOY | 外币报表折算差额—同比 |
| 191 | CREDITOR_INVEST_YOY | 债权投资—同比 |
| 192 | CURRENT_ASSET_BALANCE_YOY | 流动资产平衡项—同比 |
| 193 | CURRENT_ASSET_OTHER_YOY | 其他流动资产—同比 |
| 194 | CURRENT_LIAB_BALANCE_YOY | 流动负债平衡项—同比 |
| 195 | CURRENT_LIAB_OTHER_YOY | 其他流动负债—同比 |
| 196 | DEFER_INCOME_1YEAR_YOY | 一年内到期递延收益—同比 |
| 197 | DEFER_INCOME_YOY | 递延收益—同比 |
| 198 | DEFER_TAX_ASSET_YOY | 递延所得税资产—同比 |
| 199 | DEFER_TAX_LIAB_YOY | 递延所得税负债—同比 |
| 200 | DERIVE_FINASSET_YOY | 衍生金融资产—同比 |
| 201 | DERIVE_FINLIAB_YOY | 衍生金融负债—同比 |
| 202 | DEVELOP_EXPENSE_YOY | 开发支出—同比 |
| 203 | DIV_HOLDSALE_ASSET_YOY | 划分为持有待售的资产—同比 |
| 204 | DIV_HOLDSALE_LIAB_YOY | 划分为持有待售的负债—同比 |
| 205 | DIVIDEND_PAYABLE_YOY | 应付股利—同比 |
| 206 | DIVIDEND_RECE_YOY | 应收股利—同比 |
| 207 | EQUITY_BALANCE_YOY | 权益平衡项—同比 |
| 208 | EQUITY_OTHER_YOY | 权益其他—同比 |
| 209 | EXPORT_REFUND_RECE_YOY | 应收出口退税—同比 |
| 210 | FEE_COMMISSION_PAYABLE_YOY | 应付手续费及佣金—同比 |
| 211 | FIN_FUND_YOY | 融出资金等—同比 |
| 212 | FINANCE_RECE_YOY | 应收融资租赁款等—同比 |
| 213 | FIXED_ASSET_DISPOSAL_YOY | 固定资产清理—同比 |
| 214 | FIXED_ASSET_YOY | 固定资产—同比 |
| 215 | FVTOCI_FINASSET_YOY | FVTOCI 金融资产—同比 |
| 216 | FVTOCI_NCFINASSET_YOY | 非流动 FVTOCI 金融资产—同比 |
| 217 | FVTPL_FINASSET_YOY | FVTPL 金融资产—同比 |
| 218 | FVTPL_FINLIAB_YOY | FVTPL 金融负债—同比 |
| 219 | GENERAL_RISK_RESERVE_YOY | 一般风险准备—同比 |
| 220 | GOODWILL_YOY | 商誉—同比 |
| 221 | HOLD_MATURITY_INVEST_YOY | 持有至到期投资—同比 |
| 222 | HOLDSALE_ASSET_YOY | 持有待售资产—同比 |
| 223 | HOLDSALE_LIAB_YOY | 持有待售负债—同比 |
| 224 | INSURANCE_CONTRACT_RESERVE_YOY | 保险合同准备金—同比 |
| 225 | INTANGIBLE_ASSET_YOY | 无形资产—同比 |
| 226 | INTEREST_PAYABLE_YOY | 应付利息—同比 |
| 227 | INTEREST_RECE_YOY | 应收利息—同比 |
| 228 | INTERNAL_PAYABLE_YOY | 内部应付款—同比 |
| 229 | INTERNAL_RECE_YOY | 内部应收款—同比 |
| 230 | INVENTORY_YOY | 存货—同比 |
| 231 | INVEST_REALESTATE_YOY | 投资性房地产—同比 |
| 232 | LEASE_LIAB_YOY | 租赁负债—同比 |
| 233 | LEND_FUND_YOY | 拆出资金—同比 |
| 234 | LIAB_BALANCE_YOY | 负债平衡项—同比 |
| 235 | LIAB_EQUITY_BALANCE_YOY | 负债和权益总计平衡项—同比 |
| 236 | LIAB_EQUITY_OTHER_YOY | 负债和所有者权益其他—同比 |
| 237 | LIAB_OTHER_YOY | 其他负债—同比 |
| 238 | LOAN_ADVANCE_YOY | 发放贷款及垫款—同比 |
| 239 | LOAN_PBC_YOY | 向中央银行借款—同比 |
| 240 | LONG_EQUITY_INVEST_YOY | 长期股权投资—同比 |
| 241 | LONG_LOAN_YOY | 长期借款—同比 |
| 242 | LONG_PAYABLE_YOY | 长期应付款—同比 |
| 243 | LONG_PREPAID_EXPENSE_YOY | 长期待摊费用—同比 |
| 244 | LONG_RECE_YOY | 长期应收款—同比 |
| 245 | LONG_STAFFSALARY_PAYABLE_YOY | 长期应付职工薪酬—同比 |
| 246 | MINORITY_EQUITY_YOY | 少数股东权益—同比 |
| 247 | MONETARYFUNDS_YOY | 货币资金—同比 |
| 248 | NONCURRENT_ASSET_1YEAR_YOY | 一年内到期的非流动资产—同比 |
| 249 | NONCURRENT_ASSET_BALANCE_YOY | 非流动资产平衡项—同比 |
| 250 | NONCURRENT_ASSET_OTHER_YOY | 其他非流动资产—同比 |
| 251 | NONCURRENT_LIAB_1YEAR_YOY | 一年内到期的非流动负债—同比 |
| 252 | NONCURRENT_LIAB_BALANCE_YOY | 非流动负债平衡项—同比 |
| 253 | NONCURRENT_LIAB_OTHER_YOY | 其他非流动负债—同比 |
| 254 | NOTE_ACCOUNTS_PAYABLE_YOY | 应付票据及应付账款—同比 |
| 255 | NOTE_ACCOUNTS_RECE_YOY | 应收票据及应收账款—同比 |
| 256 | NOTE_PAYABLE_YOY | 应付票据—同比 |
| 257 | NOTE_RECE_YOY | 应收票据—同比 |
| 258 | OIL_GAS_ASSET_YOY | 油气资产—同比 |
| 259 | OTHER_COMPRE_INCOME_YOY | 其他综合收益—同比 |
| 260 | OTHER_CREDITOR_INVEST_YOY | 其他债权投资—同比 |
| 261 | OTHER_CURRENT_ASSET_YOY | 其他流动资产—同比 |
| 262 | OTHER_CURRENT_LIAB_YOY | 其他流动负债—同比 |
| 263 | OTHER_EQUITY_INVEST_YOY | 其他权益工具投资—同比 |
| 264 | OTHER_EQUITY_OTHER_YOY | 其他权益工具其他—同比 |
| 265 | OTHER_EQUITY_TOOL_YOY | 其他权益工具—同比 |
| 266 | OTHER_NONCURRENT_ASSET_YOY | 其他非流动资产—同比 |
| 267 | OTHER_NONCURRENT_FINASSET_YOY | 其他非流动金融资产—同比 |
| 268 | OTHER_NONCURRENT_LIAB_YOY | 其他非流动负债—同比 |
| 269 | OTHER_PAYABLE_YOY | 其他应付款—同比 |
| 270 | OTHER_RECE_YOY | 其他应收款—同比 |
| 271 | PARENT_EQUITY_BALANCE_YOY | 归母权益平衡项—同比 |
| 272 | PARENT_EQUITY_OTHER_YOY | 归母权益其他—同比 |
| 273 | PERPETUAL_BOND_PAYBALE_YOY | 应付永续债—同比 |
| 274 | PERPETUAL_BOND_YOY | 永续债—同比 |
| 275 | PREDICT_CURRENT_LIAB_YOY | 预计流动负债—同比 |
| 276 | PREDICT_LIAB_YOY | 预计负债—同比 |
| 277 | PREFERRED_SHARES_PAYBALE_YOY | 应付优先股—同比 |
| 278 | PREFERRED_SHARES_YOY | 优先股—同比 |
| 279 | PREMIUM_RECE_YOY | 应收保费—同比 |
| 280 | PREPAYMENT_YOY | 预付款项—同比 |
| 281 | PRODUCTIVE_BIOLOGY_ASSET_YOY | 生产性生物资产—同比 |
| 282 | PROJECT_MATERIAL_YOY | 工程物资—同比 |
| 283 | RC_RESERVE_RECE_YOY | 应收分保准备金等—同比 |
| 284 | REINSURE_PAYABLE_YOY | 应付分保账款—同比 |
| 285 | REINSURE_RECE_YOY | 应收分保账款—同比 |
| 286 | SELL_REPO_FINASSET_YOY | 卖出回购金融资产款—同比 |
| 287 | SETTLE_EXCESS_RESERVE_YOY | 结算备付金—同比 |
| 288 | SHARE_CAPITAL_YOY | 股本—同比 |
| 289 | SHORT_BOND_PAYABLE_YOY | 应付短期债券—同比 |
| 290 | SHORT_FIN_PAYABLE_YOY | 短期应付债券等—同比 |
| 291 | SHORT_LOAN_YOY | 短期借款—同比 |
| 292 | SPECIAL_PAYABLE_YOY | 专项应付款—同比 |
| 293 | SPECIAL_RESERVE_YOY | 专项储备—同比 |
| 294 | STAFF_SALARY_PAYABLE_YOY | 应付职工薪酬—同比 |
| 295 | SUBSIDY_RECE_YOY | 应收补贴款—同比 |
| 296 | SURPLUS_RESERVE_YOY | 盈余公积—同比 |
| 297 | TAX_PAYABLE_YOY | 应交税费—同比 |
| 298 | TOTAL_ASSETS_YOY | 资产总计—同比 |
| 299 | TOTAL_CURRENT_ASSETS_YOY | 流动资产合计—同比 |
| 300 | TOTAL_CURRENT_LIAB_YOY | 流动负债合计—同比 |
| 301 | TOTAL_EQUITY_YOY | 所有者权益合计—同比 |
| 302 | TOTAL_LIAB_EQUITY_YOY | 负债和所有者权益总计—同比 |
| 303 | TOTAL_LIABILITIES_YOY | 负债合计—同比 |
| 304 | TOTAL_NONCURRENT_ASSETS_YOY | 非流动资产合计—同比 |
| 305 | TOTAL_NONCURRENT_LIAB_YOY | 非流动负债合计—同比 |
| 306 | TOTAL_OTHER_PAYABLE_YOY | 其他应付款合计—同比 |
| 307 | TOTAL_OTHER_RECE_YOY | 其他应收款合计—同比 |
| 308 | TOTAL_PARENT_EQUITY_YOY | 归属于母公司所有者权益合计—同比 |
| 309 | TRADE_FINASSET_NOTFVTPL_YOY | 交易性金融资产（非 FVTPL）—同比 |
| 310 | TRADE_FINASSET_YOY | 交易性金融资产—同比 |
| 311 | TRADE_FINLIAB_NOTFVTPL_YOY | 交易性金融负债（非 FVTPL）—同比 |
| 312 | TRADE_FINLIAB_YOY | 交易性金融负债—同比 |
| 313 | TREASURY_SHARES_YOY | 库存股—同比 |
| 314 | UNASSIGN_RPOFIT_YOY | 未分配利润—同比 |
| 315 | UNCONFIRM_INVEST_LOSS_YOY | 未确认投资损失—同比 |
| 316 | USERIGHT_ASSET_YOY | 使用权资产—同比 |

---

## 四、审计意见与状态（3 列）

| 序号 | 字段名 | 说明 |
|------|--------|------|
| 317 | OPINION_TYPE | 审计意见类型（代码或枚举，以东财返回为准） |
| 318 | OSOPINION_TYPE | 其他审计意见类型 / 明细（可能为空） |
| 319 | LISTING_STATE | 上市状态标识 |

---

## 版本与核对说明

- 字段列表以本机实际调用 `ak.stock_balance_sheet_by_report_em(symbol="SH600519")` 得到的 **319 列**为准；AKShare 或东财接口升级后列名或数量可能变化，接入前建议抽样打印 `df.columns` 核对。
- 部分字段名为东财接口历史拼写（如 `UNASSIGN_RPOFIT`、`PERPETUAL_BOND_PAYBALE`、`PREFERRED_SHARES_PAYBALE`），落库时建议沿用原名以保持与源数据一致。
