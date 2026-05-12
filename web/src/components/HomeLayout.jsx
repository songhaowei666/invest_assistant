import { useCallback, useEffect, useState } from 'react'
import EarningsLensLayout from './EarningsLensLayout'
import InvestAssistantLayout from './InvestAssistantLayout'
import ResearchQaLayout from './ResearchQaLayout'
import StockList from './StockList'

const API_BASE = 'http://localhost:8000/api/v1'

/** 请求持仓列表 JSON */
async function fetchPositionsJson() {
  const response = await fetch(`${API_BASE}/positions`)
  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }
  return response.json()
}

/** 从接口数据解析 items 数组 */
function itemsFromResponse(data) {
  return Array.isArray(data.items) ? data.items : []
}

function HomeLayout() {
  const [stocks, setStocks] = useState([])
  const [selectedStockId, setSelectedStockId] = useState(null)
  const [activePage, setActivePage] = useState('stocks')
  const [isLoading, setIsLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState('')

  const applyItems = useCallback((items) => {
    setStocks(items)
    setSelectedStockId((prev) => {
      if (items.some((s) => s.id === prev)) {
        return prev
      }
      return items[0]?.id ?? null
    })
  }, [])

  /** 写操作成功后静默刷新列表 */
  const onStocksUpdated = useCallback(async () => {
    setErrorMsg('')
    try {
      const data = await fetchPositionsJson()
      applyItems(itemsFromResponse(data))
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : '请求持仓列表失败')
    }
  }, [applyItems])

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setIsLoading(true)
      setErrorMsg('')
      try {
        const data = await fetchPositionsJson()
        if (cancelled) return
        applyItems(itemsFromResponse(data))
      } catch (error) {
        if (!cancelled) {
          setErrorMsg(error instanceof Error ? error.message : '请求持仓列表失败')
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [applyItems])

  return (
    <div className="page-shell">
      <nav className="top-nav">
        <div className="top-nav__tabs">
          <button
            type="button"
            className={`top-nav__item top-nav__item--clickable ${activePage === 'stocks' ? 'top-nav__item--active' : ''}`}
            onClick={() => setActivePage('stocks')}
          >
            持仓数据
          </button>
          <button
            type="button"
            className={`top-nav__item top-nav__item--clickable ${activePage === 'earnings-lens' ? 'top-nav__item--active' : ''}`}
            onClick={() => setActivePage('earnings-lens')}
          >
            透视盈余
          </button>
          <button
            type="button"
            className={`top-nav__item top-nav__item--clickable ${activePage === 'assistant' ? 'top-nav__item--active' : ''}`}
            onClick={() => setActivePage('assistant')}
          >
            投资助手
          </button>
          <button
            type="button"
            className={`top-nav__item top-nav__item--clickable ${activePage === 'research-qa' ? 'top-nav__item--active' : ''}`}
            onClick={() => setActivePage('research-qa')}
          >
            投研数问
          </button>
        </div>
      </nav>
      <main
        className={`home-layout ${activePage !== 'stocks' && activePage !== 'earnings-lens' ? 'home-layout--assistant' : ''} ${activePage === 'earnings-lens' ? 'home-layout--earnings-lens' : ''}`}
      >
        {activePage === 'stocks' ? (
          <>
            {isLoading ? <p className="status-text">加载中...</p> : null}
            {!isLoading && errorMsg ? <p className="status-text status-text--error">{errorMsg}</p> : null}
            <StockList
              stocks={stocks}
              selectedStockId={selectedStockId}
              onSelectStock={setSelectedStockId}
              apiBase={API_BASE}
              onStocksUpdated={onStocksUpdated}
            />
          </>
        ) : null}
        {activePage === 'earnings-lens' ? <EarningsLensLayout apiBase={API_BASE} /> : null}
        {activePage === 'assistant' ? (
          <InvestAssistantLayout apiBase={API_BASE} />
        ) : null}
        {activePage === 'research-qa' ? <ResearchQaLayout apiBase={API_BASE} /> : null}
      </main>
    </div>
  )
}

export default HomeLayout
