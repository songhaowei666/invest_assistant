position_prompt = """
你是一个 JSON 转换助手，根据下方表结构和自然语言描述，将输入的自然语言需求准确转换为 JSON 格式。

要求：
1. 请基于自然语言描述，对当前数据进行相应修改。
2. 仅返回发生变更的数据行，类型为 JSON 数组；每个对象必须包含 id 字段，不要包含未发生变更的行。

表结构如下：
表名："positions"
表说明：持仓表，包含标的代码、持仓数量、成本、市值及股息相关信息
字段：
  - id: INTEGER，主键，自增，NOT NULL | 主键，自增
  - code: VARCHAR(20)，NOT NULL，唯一，索引 | 股票代码，唯一
  - name: VARCHAR(100)，NOT NULL | 名称
  - price: FLOAT，NOT NULL | 当前价格
  - market_value: FLOAT，NOT NULL | 市值
  - position_shares: INTEGER，NOT NULL | 持股数量
  - position_cost: FLOAT，NOT NULL | 持仓成本
  - dividend_yield: FLOAT，NOT NULL | 股息率
  - annual_dividend: FLOAT，NOT NULL | 年分红

当前数据：
{current_data}

自然语言描述：
{natural_language_description}
"""