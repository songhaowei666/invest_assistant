function StockItem({ stock, isSelected, onSelect }) {
  return (
    <button
      type="button"
      className={`stock-item ${isSelected ? 'stock-item--selected' : ''}`}
      onClick={() => onSelect(stock)}
      aria-pressed={isSelected}
    >
      <div className="stock-item__header">
        <strong>{stock.name}</strong>
        <span>{stock.code}</span>
      </div>
      <div className="stock-item__meta">
        <span>持仓 {stock.positionShares} 股</span>
        <span>成本 {stock.positionCost.toFixed(2)} 元</span>
      </div>
      <div className="stock-item__meta">
        <span>股息率 {stock.dividendYield.toFixed(2)}%</span>
        <span>年化分红 {stock.annualDividend.toFixed(2)} 元/股</span>
      </div>
    </button>
  )
}

export default StockItem
