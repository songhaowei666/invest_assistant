function ChatPanelPlaceholder({ stock }) {
  if (!stock) {
    return (
      <section className="panel chat-panel">
        <header className="panel__header">
          <h2>AI 聊天区</h2>
        </header>
        <div className="chat-empty">
          <p>请先从左侧选择一只股票。</p>
          <p>选择后将展示该股票的分析上下文。</p>
        </div>
      </section>
    )
  }

  return (
    <section className="panel chat-panel">
      <header className="panel__header">
        <h2>AI 聊天区</h2>
      </header>
      <div className="chat-context">
        <p className="chat-context__title">
          当前股票：{stock.name}（{stock.code}）
        </p>
        <ul>
          <li>持仓股数：{stock.positionShares} 股</li>
          <li>持仓成本：{stock.positionCost.toFixed(2)} 元</li>
          <li>股息率：{stock.dividendYield.toFixed(2)}%</li>
          <li>年化分红：{stock.annualDividend.toFixed(2)} 元/股</li>
        </ul>
        <p className="chat-context__hint">后续将接入 AI 聊天能力。</p>
      </div>
    </section>
  )
}

export default ChatPanelPlaceholder
