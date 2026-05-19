import { useEffect, useState } from 'react'
import { fetchWithBearer } from '../lib/authFetch'

/** 编辑/新增图标（铅笔） */
function IconEdit() {
  return (
    <svg className="stock-action-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm2.92 2.83H5v-.92l9.06-9.06.92.92L5.92 20.08zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"
      />
    </svg>
  )
}

/** 删除图标（垃圾桶） */
function IconDelete() {
  return (
    <svg className="stock-action-icon" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
      />
    </svg>
  )
}

/** 新增图标（加号） */
function IconAdd() {
  return (
    <svg className="stock-action-icon" viewBox="0 0 24 24" aria-hidden>
      <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
    </svg>
  )
}

/** 将列表接口的驼峰项转为写入接口用的蛇形单条 */
function stockToPayload(stock) {
  return {
    code: stock.code,
    name: stock.name,
    price: Number(stock.price),
    market_value: Number(stock.marketValue),
    position_shares: Number(stock.positionShares),
    position_cost: Number(stock.positionCost),
    dividend_yield: Number(stock.dividendYield),
    annual_dividend: Number(stock.totalDividend),
  }
}

const emptyForm = () => ({
  code: '',
  name: '',
  price: '',
  market_value: '',
  position_shares: '',
  position_cost: '',
  dividend_yield: '',
  annual_dividend: '',
})

function computeDerivedByPriceSharesDividend(priceRaw, sharesRaw, dividendYieldRaw) {
  const price = Number(priceRaw)
  const shares = Number.parseInt(String(sharesRaw), 10)
  const dividendYield = Number(dividendYieldRaw)
  if (Number.isNaN(price) || Number.isNaN(shares)) {
    return { marketValue: '', annualDividend: '' }
  }
  const marketValue = price * shares
  const marketValueText = marketValue.toFixed(2)
  if (Number.isNaN(dividendYield)) {
    return { marketValue: marketValueText, annualDividend: '' }
  }
  return {
    marketValue: marketValueText,
    annualDividend: ((marketValue * dividendYield) / 100).toFixed(2),
  }
}

function StockList({ stocks, selectedStockId, onSelectStock, apiBase, onStocksUpdated, onUnauthorized = () => {} }) {
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorMode, setEditorMode] = useState('add')
  const [form, setForm] = useState(emptyForm)
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [nameSuggestItems, setNameSuggestItems] = useState([])
  const [nameSuggestOpen, setNameSuggestOpen] = useState(false)
  const [nameSuggestLoading, setNameSuggestLoading] = useState(false)
  const [nameSuggestError, setNameSuggestError] = useState('')
  const [priceDividendLoading, setPriceDividendLoading] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteSubmitting, setDeleteSubmitting] = useState(false)

  const openAdd = () => {
    setEditorMode('add')
    setForm(emptyForm())
    setFormError('')
    setNameSuggestItems([])
    setNameSuggestOpen(false)
    setNameSuggestLoading(false)
    setNameSuggestError('')
    setPriceDividendLoading(false)
    setEditorOpen(true)
  }

  const openEdit = (stock, event) => {
    event.stopPropagation()
    setEditorMode('edit')
    const p = stockToPayload(stock)
    const derived = computeDerivedByPriceSharesDividend(p.price, p.position_shares, p.dividend_yield)
    setForm({
      code: p.code,
      name: p.name,
      price: String(p.price),
      market_value: derived.marketValue,
      position_shares: String(p.position_shares),
      position_cost: String(p.position_cost),
      dividend_yield: String(p.dividend_yield),
      annual_dividend: derived.annualDividend,
    })
    setFormError('')
    setNameSuggestItems([])
    setNameSuggestOpen(false)
    setNameSuggestLoading(false)
    setNameSuggestError('')
    setPriceDividendLoading(false)
    setEditorOpen(true)
  }

  const closeEditor = () => {
    if (submitting) return
    setEditorOpen(false)
    setFormError('')
    setNameSuggestOpen(false)
    setNameSuggestError('')
    setPriceDividendLoading(false)
  }

  const refreshPriceDividendByCode = async (code) => {
    setPriceDividendLoading(true)
    try {
      const params = new URLSearchParams({ code })
      const response = await fetchWithBearer(
        apiBase,
        `/positions/price-dividend?${params.toString()}`,
        { method: 'GET' },
        onUnauthorized,
      )
      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`)
      }
      const data = await response.json()
      setForm((prev) => {
        // 统一按弹窗当前值重算，保证年分红与弹窗字段同步
        const derived = computeDerivedByPriceSharesDividend(data.price, prev.position_shares, data.dividendYield)
        return {
          ...prev,
          price: String(data.price),
          dividend_yield: String(data.dividendYield),
          market_value: derived.marketValue,
          annual_dividend: derived.annualDividend,
        }
      })
      setNameSuggestError('')
    } catch (e) {
      setNameSuggestError(e instanceof Error ? e.message : '查询价格和股息率失败')
    } finally {
      setPriceDividendLoading(false)
    }
  }

  useEffect(() => {
    if (!editorOpen || editorMode !== 'add') {
      return undefined
    }
    const keyword = form.name.trim()
    if (!keyword) {
      return undefined
    }
    const timer = window.setTimeout(async () => {
      setNameSuggestLoading(true)
      setNameSuggestError('')
      try {
        const params = new URLSearchParams({ keyword, limit: '10' })
        const response = await fetchWithBearer(
          apiBase,
          `/positions/stock-name-suggest?${params.toString()}`,
          { method: 'GET' },
          onUnauthorized,
        )
        if (!response.ok) {
          throw new Error(`请求失败: ${response.status}`)
        }
        const data = await response.json()
        const items = Array.isArray(data?.items) ? data.items : []
        const normalized = items
          .filter((item) => item && typeof item.name === 'string' && typeof item.code === 'string')
          .slice(0, 10)
          .map((item) => ({ name: item.name, code: item.code }))
        setNameSuggestItems(normalized)
        setNameSuggestOpen(normalized.length > 0)
      } catch (e) {
        setNameSuggestItems([])
        setNameSuggestOpen(false)
        setNameSuggestError(e instanceof Error ? e.message : '股票名称联想请求失败')
      } finally {
        setNameSuggestLoading(false)
      }
    }, 250)
    return () => {
      window.clearTimeout(timer)
    }
  }, [apiBase, editorMode, editorOpen, form.name, onUnauthorized])

  useEffect(() => {
    if (!editorOpen || editorMode !== 'edit') {
      return undefined
    }
    const code = form.code.trim()
    if (!code) {
      return undefined
    }
    const timer = window.setTimeout(() => {
      void refreshPriceDividendByCode(code)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [editorMode, editorOpen, form.code])

  const parsePayloadFromForm = () => {
    const code = form.code.trim()
    const name = form.name.trim()
    const price = Number(form.price)
    const market_value = Number(form.market_value)
    const position_shares = Number.parseInt(form.position_shares, 10)
    const position_cost = Number(form.position_cost)
    const dividend_yield = Number(form.dividend_yield)
    const annual_dividend = Number(form.annual_dividend)
    if (!code || !name) {
      return { error: '请填写股票代码与名称' }
    }
    if (
      Number.isNaN(price) ||
      Number.isNaN(market_value) ||
      Number.isNaN(position_shares) ||
      Number.isNaN(position_cost) ||
      Number.isNaN(dividend_yield) ||
      Number.isNaN(annual_dividend)
    ) {
      return { error: '数值字段请填写有效数字' }
    }
    return {
      payload: {
        code,
        name,
        price,
        market_value,
        position_shares,
        position_cost,
        dividend_yield,
        annual_dividend,
      },
    }
  }

  const handleEditorConfirm = async () => {
    const parsed = parsePayloadFromForm()
    if (parsed.error) {
      setFormError(parsed.error)
      return
    }
    setFormError('')
    setSubmitting(true)
    try {
      const path = editorMode === 'add' ? '/positions/add' : '/positions/modify'
      const body = JSON.stringify([parsed.payload])
      const response = await fetchWithBearer(apiBase, path, { method: 'POST', body }, onUnauthorized)
      if (!response.ok) {
        let detail = `请求失败: ${response.status}`
        try {
          const errJson = await response.json()
          if (errJson?.detail) detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
        } catch {
          /* 忽略非 JSON 错误体 */
        }
        setFormError(detail)
        return
      }
      await onStocksUpdated()
      setEditorOpen(false)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '网络错误')
    } finally {
      setSubmitting(false)
    }
  }

  const openDelete = (stock, event) => {
    event.stopPropagation()
    setDeleteTarget(stock)
  }

  const closeDelete = () => {
    if (deleteSubmitting) return
    setDeleteTarget(null)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleteSubmitting(true)
    try {
      const response = await fetchWithBearer(
        apiBase,
        '/positions/delete',
        {
          method: 'POST',
          body: JSON.stringify([{ code: deleteTarget.code }]),
        },
        onUnauthorized,
      )
      if (!response.ok) {
        let detail = `请求失败: ${response.status}`
        try {
          const errJson = await response.json()
          if (errJson?.detail) detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
        } catch {
          /* 忽略 */
        }
        window.alert(detail)
        return
      }
      await onStocksUpdated()
      setDeleteTarget(null)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : '网络错误')
    } finally {
      setDeleteSubmitting(false)
    }
  }

  const updateField = (key) => (e) => {
    const { value } = e.target
    setForm((prev) => {
      if (key === 'name' && editorMode === 'add') {
        return { ...prev, name: value, code: '' }
      }
      if (key === 'position_shares') {
        const derived = computeDerivedByPriceSharesDividend(prev.price, value, prev.dividend_yield)
        return { ...prev, position_shares: value, market_value: derived.marketValue, annual_dividend: derived.annualDividend }
      }
      return { ...prev, [key]: value }
    })
    if (key === 'name' && editorMode === 'add') {
      if (!value.trim()) {
        setNameSuggestItems([])
      }
      setNameSuggestOpen(Boolean(value.trim()))
      setNameSuggestError('')
    }
  }

  const handleSelectNameSuggest = async (item) => {
    setForm((prev) => ({
      ...prev,
      name: item.name,
      code: item.code,
      price: '',
      dividend_yield: '',
    }))
    setNameSuggestOpen(false)
    setNameSuggestError('')
    await refreshPriceDividendByCode(item.code)
  }

  const renderTable = () => (
    <div className="stock-table-wrapper">
      <table className="stock-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>价格(元)</th>
            <th>市值(元)</th>
            <th>持仓股数</th>
            <th>股息率</th>
            <th>总分红(元)</th>
            <th className="stock-table__col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => (
            <tr
              key={stock.id}
              className={selectedStockId === stock.id ? 'stock-row--selected' : ''}
              onClick={() => onSelectStock(stock.id)}
            >
              <td>{stock.code}</td>
              <td>{stock.name}</td>
              <td>{stock.price.toFixed(2)}</td>
              <td>{stock.marketValue.toFixed(2)}</td>
              <td>{stock.positionShares}</td>
              <td>{stock.dividendYield.toFixed(2)}%</td>
              <td>{stock.totalDividend.toFixed(2)}</td>
              <td className="stock-table__col-actions">
                <div className="stock-row-actions" onClick={(e) => e.stopPropagation()}>
                  <button type="button" className="stock-icon-btn" title="修改" onClick={(e) => openEdit(stock, e)}>
                    <IconEdit />
                  </button>
                  <button type="button" className="stock-icon-btn stock-icon-btn--danger" title="删除" onClick={(e) => openDelete(stock, e)}>
                    <IconDelete />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <section className="panel stock-list-panel">
      <header className="panel__header panel__header--row">
        <h2>股票列表</h2>
        <button type="button" className="stock-toolbar-add" onClick={openAdd}>
          <IconAdd />
          <span>新增持仓</span>
        </button>
      </header>

      {!stocks.length ? (
        <>
          <p className="status-text">暂无持仓数据</p>
          <p className="status-text">
            <button type="button" className="stock-toolbar-add stock-toolbar-add--inline" onClick={openAdd}>
              <IconAdd />
              <span>新增一条</span>
            </button>
          </p>
        </>
      ) : (
        renderTable()
      )}

      {editorOpen ? (
        <div className="ai-modal-mask" role="presentation" onClick={closeEditor}>
          <div
            className="ai-modal position-editor-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="position-editor-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="position-editor-title">{editorMode === 'add' ? '新增持仓' : '修改持仓'}</h3>
            <div className="position-form-grid">
              <label className="position-form-field">
                <span>名称</span>
                <div className="position-suggest">
                  <input
                    className="ai-modal__input"
                    value={form.name}
                    onChange={updateField('name')}
                    onFocus={() => {
                      if (editorMode === 'add' && nameSuggestItems.length) setNameSuggestOpen(true)
                    }}
                    onBlur={() => {
                      window.setTimeout(() => setNameSuggestOpen(false), 150)
                    }}
                    maxLength={100}
                  />
                  {editorMode === 'add' && nameSuggestOpen ? (
                    <div className="position-suggest__menu">
                      {nameSuggestLoading ? <div className="position-suggest__empty">搜索中...</div> : null}
                      {!nameSuggestLoading && nameSuggestItems.length
                        ? nameSuggestItems.map((item) => (
                            <button
                              type="button"
                              key={`${item.code}-${item.name}`}
                              className="position-suggest__item"
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => {
                                void handleSelectNameSuggest(item)
                              }}
                            >
                              <span className="position-suggest__item-name">{item.name}</span>
                              <span className="position-suggest__item-code">{item.code}</span>
                            </button>
                          ))
                        : null}
                      {!nameSuggestLoading && !nameSuggestItems.length ? (
                        <div className="position-suggest__empty">暂无匹配股票</div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </label>
              <label className="position-form-field">
                <span>股票代码</span>
                <input
                  className="ai-modal__input"
                  value={form.code}
                  onChange={updateField('code')}
                  disabled
                  maxLength={20}
                />
              </label>
              <label className="position-form-field">
                <span>持股数量</span>
                <input className="ai-modal__input" value={form.position_shares} onChange={updateField('position_shares')} inputMode="numeric" />
              </label>
              <label className="position-form-field">
                <span>持仓成本</span>
                <input className="ai-modal__input" value={form.position_cost} onChange={updateField('position_cost')} inputMode="decimal" />
              </label>
              <label className="position-form-field">
                <span>当前价格</span>
                <input
                  className="ai-modal__input"
                  value={form.price}
                  onChange={updateField('price')}
                  inputMode="decimal"
                  disabled
                />
              </label>
              <label className="position-form-field">
                <span>市值</span>
                <input
                  className="ai-modal__input"
                  value={form.market_value}
                  onChange={updateField('market_value')}
                  inputMode="decimal"
                  disabled
                />
              </label>
              <label className="position-form-field">
                <span>股息率（小数，如 0.032）</span>
                <input
                  className="ai-modal__input"
                  value={form.dividend_yield}
                  onChange={updateField('dividend_yield')}
                  inputMode="decimal"
                  disabled
                />
              </label>
              <label className="position-form-field">
                <span>年分红</span>
                <input
                  className="ai-modal__input"
                  value={form.annual_dividend}
                  onChange={updateField('annual_dividend')}
                  inputMode="decimal"
                  disabled
                />
              </label>
            </div>
            {formError ? <p className="position-form-error">{formError}</p> : null}
            {!formError && nameSuggestError ? <p className="position-form-error">{nameSuggestError}</p> : null}
            <div className="ai-modal__actions">
              <button type="button" onClick={handleEditorConfirm} disabled={submitting || priceDividendLoading}>
                {submitting ? '提交中...' : priceDividendLoading ? '加载中...' : '确认'}
              </button>
              <button type="button" onClick={closeEditor} disabled={submitting}>
                取消
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteTarget ? (
        <div className="ai-modal-mask" role="presentation" onClick={closeDelete}>
          <div
            className="ai-modal confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-confirm-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="delete-confirm-title">确认删除</h3>
            <p className="confirm-dialog__body">
              确定删除持仓「{deleteTarget.name}」（{deleteTarget.code}）吗？此操作不可撤销。
            </p>
            <div className="ai-modal__actions">
              <button type="button" className="confirm-dialog__danger" onClick={handleDeleteConfirm} disabled={deleteSubmitting}>
                {deleteSubmitting ? '删除中...' : '确认删除'}
              </button>
              <button type="button" onClick={closeDelete} disabled={deleteSubmitting}>
                取消
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}

export default StockList
