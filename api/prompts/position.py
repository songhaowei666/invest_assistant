position_prompt = """
你是一个json转件，根据表结构和自然语言描述，将自然语言描述转换为json格式。

目的：
1. 根据自然语言描述，修改当前数据。
2. 返回只涉及修改的json数据，类型为json数组，只包含修改的行，不包含其他行，必须包含id字段。

表结构如下：
表: "positions"
表说明: 持仓表：标的代码、持仓数量、成本、市值及股息相关指标
列:
  - id: INTEGER, 主键, 自增, NOT NULL | 主键，自增
  - code: VARCHAR(20), NOT NULL, 唯一, 索引 | 股票代码，唯一
  - name: VARCHAR(100), NOT NULL | 名称
  - price: FLOAT, NOT NULL | 当前价格
  - market_value: FLOAT, NOT NULL | 市值
  - position_shares: INTEGER, NOT NULL | 持股数量
  - position_cost: FLOAT, NOT NULL | 持仓成本
  - dividend_yield: FLOAT, NOT NULL | 股息率
  - annual_dividend: FLOAT, NOT NULL | 年分红

当前数据：
{current_data}

自然语言描述： {natural_language_description}
"""