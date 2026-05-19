import { useCallback, useEffect, useState } from 'react'
import EarningsLensLayout from './EarningsLensLayout'
import InvestAssistantLayout from './InvestAssistantLayout'
import LoginLayout from './LoginLayout'
import ResearchQaLayout from './ResearchQaLayout'
import ScheduledTasksLayout from './ScheduledTasksLayout'
import StockList from './StockList'
import { fetchWithBearer } from '../lib/authFetch'
import { getAccessToken } from '../lib/authStorage'

const API_BASE = 'http://localhost:8000/api/v1'

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
  const [accessToken, setAccessTokenState] = useState(() => getAccessToken())
  /** 接口 401 且 refresh 无效时全屏展示登录，不作为顶部导航 */
  const [authGateOpen, setAuthGateOpen] = useState(false)
  /** 用户主动关闭登录层且仍无 token 时，不再自动请求持仓，避免 401 与弹层死循环 */
  const [skipPositionsAuthProbe, setSkipPositionsAuthProbe] = useState(false)

  const openAuthGate = useCallback(() => {
    setAuthGateOpen(true)
    setSkipPositionsAuthProbe(false)
    setErrorMsg('')
  }, [])

  const closeAuthGate = useCallback(() => {
    setAuthGateOpen(false)
    if (!getAccessToken()) {
      setSkipPositionsAuthProbe(true)
    }
  }, [])

  const syncAccessFromStorage = useCallback(() => {
    setAccessTokenState(getAccessToken())
  }, [])

  const handleAuthSuccess = useCallback(() => {
    setAuthGateOpen(false)
    setSkipPositionsAuthProbe(false)
    setAccessTokenState(getAccessToken())
  }, [])

  const applyItems = useCallback((items) => {
    setStocks(items)
    setSelectedStockId((prev) => {
      if (items.some((s) => s.id === prev)) {
        return prev
      }
      return items[0]?.id ?? null
    })
  }, [])

  const fetchPositionsJson = useCallback(async () => {
    const response = await fetchWithBearer(API_BASE, '/positions', { method: 'GET' }, openAuthGate)
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('需要登录后访问持仓接口')
      }
      throw new Error(`请求失败: ${response.status}`)
    }
    return response.json()
  }, [openAuthGate])

  /** 写操作成功后静默刷新列表 */
  const onStocksUpdated = useCallback(async () => {
    setErrorMsg('')
    try {
      const data = await fetchPositionsJson()
      applyItems(itemsFromResponse(data))
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : '请求持仓列表失败')
    }
  }, [applyItems, fetchPositionsJson])

  useEffect(() => {
    if (authGateOpen) {
      return undefined
    }
    if (skipPositionsAuthProbe && !getAccessToken()) {
      const timer = window.setTimeout(() => {
        setIsLoading(false)
        setErrorMsg('未登录：持仓接口需要鉴权。可刷新页面后再次触发登录，或先在下方操作中完成登录。')
      }, 0)
      return () => window.clearTimeout(timer)
    }
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
  }, [applyItems, authGateOpen, accessToken, fetchPositionsJson, skipPositionsAuthProbe])

  if (authGateOpen) {
    return (
      <div className="page-shell">
        <div className="auth-gate">
          <LoginLayout
            apiBase={API_BASE}
            onAuthSuccess={handleAuthSuccess}
            onCancel={closeAuthGate}
            onTokensCleared={syncAccessFromStorage}
            intro="访问受保护接口需要登录。接口约定见仓库 docs/api/auth-api.md。"
          />
        </div>
      </div>
    )
  }

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
          <button
            type="button"
            className={`top-nav__item top-nav__item--clickable ${activePage === 'scheduled-tasks' ? 'top-nav__item--active' : ''}`}
            onClick={() => setActivePage('scheduled-tasks')}
          >
            定时任务
          </button>
        </div>
      </nav>
      <main
        className={`home-layout ${activePage !== 'stocks' && activePage !== 'earnings-lens' && activePage !== 'scheduled-tasks' ? 'home-layout--assistant' : ''} ${activePage === 'earnings-lens' ? 'home-layout--earnings-lens' : ''} ${activePage === 'scheduled-tasks' ? 'home-layout--scheduled-tasks' : ''}`}
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
              onUnauthorized={openAuthGate}
            />
          </>
        ) : null}
        {activePage === 'earnings-lens' ? <EarningsLensLayout apiBase={API_BASE} /> : null}
        {activePage === 'assistant' ? (
          <InvestAssistantLayout apiBase={API_BASE} />
        ) : null}
        {activePage === 'research-qa' ? <ResearchQaLayout apiBase={API_BASE} /> : null}
        {activePage === 'scheduled-tasks' ? <ScheduledTasksLayout apiBase={API_BASE} /> : null}
      </main>
    </div>
  )
}

export default HomeLayout
