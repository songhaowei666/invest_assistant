import { useEffect, useState } from 'react'

/** 请求透视盈余聚合 JSON */
async function fetchEarningsLensJson(apiBase) {
  const response = await fetch(`${apiBase}/earnings-lens`)
  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }
  return response.json()
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—'
  }
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—'
  }
  return `${Number(value).toFixed(2)}%`
}

function formatMoneyYuan(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—'
  }
  const n = Number(value)
  return `${n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}

function formatReportPeriod(period) {
  if (!period || period.length < 4) {
    return '—'
  }
  return `${period.slice(0, 4)} 年报`
}

/** 市值占比（0～1）转为百分比展示；缺失或非数按 0 */
function formatWeightShare(ratio) {
  const n = ratio === null || ratio === undefined || Number.isNaN(Number(ratio)) ? 0 : Number(ratio)
  return `${(n * 100).toFixed(2)}%`
}

/** 组合加权指标卡片的单项 */
function MetricCard({ label, value, hint }) {
  return (
    <div className="earnings-lens-metric-card">
      <div className="earnings-lens-metric-card__label">{label}</div>
      <div className="earnings-lens-metric-card__value">{value}</div>
      {hint ? <div className="earnings-lens-metric-card__hint">{hint}</div> : null}
    </div>
  )
}

/**
 * 透视盈余：按持仓展示估值快照与近四年年报（1231）摘要。
 */
export default function EarningsLensLayout({ apiBase }) {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setErrorMsg('')
      setLoading(true)
      try {
        const data = await fetchEarningsLensJson(apiBase)
        if (!cancelled) {
          setPayload(data)
        }
      } catch (e) {
        if (!cancelled) {
          setErrorMsg(e instanceof Error ? e.message : '加载透视盈余失败')
          setPayload(null)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [apiBase])

  const retry = () => {
    setLoading(true)
    setErrorMsg('')
    void (async () => {
      try {
        const data = await fetchEarningsLensJson(apiBase)
        setPayload(data)
      } catch (e) {
        setErrorMsg(e instanceof Error ? e.message : '加载透视盈余失败')
        setPayload(null)
      } finally {
        setLoading(false)
      }
    })()
  }

  if (loading) {
    return <p className="status-text earnings-lens__status">加载中...</p>
  }
  if (errorMsg) {
    return (
      <div className="earnings-lens">
        <p className="status-text status-text--error earnings-lens__status">{errorMsg}</p>
        <button type="button" className="earnings-lens__retry" onClick={retry}>
          重试
        </button>
      </div>
    )
  }
  if (!payload) {
    return null
  }

  const { summary, mcWeighted, rows } = payload
  const w = mcWeighted || {}

  return (
    <div className="earnings-lens">
      <header className="earnings-lens__header">
        <h2 className="earnings-lens__title">透视盈余</h2>
        <p className="earnings-lens__subtitle">
          共 {summary.positionCount} 只持仓；其中 {summary.withBasicSnapshotCount} 只在「基础快照」表中有记录（其余请运行数据同步脚本更新
          stock_basic_info）。
        </p>
      </header>

      <section className="earnings-lens-metrics" aria-label="按市值加权的组合指标">
        <div className="earnings-lens-metrics__head">
          <h3 className="earnings-lens-metrics__title">组合透视（按持仓市值加权）</h3>
          <p className="earnings-lens-metrics__total">
            持仓总市值（元）：<strong>{formatMoneyYuan(w.totalMarketValue ?? 0)}</strong>
          </p>
        </div>
        <p className="earnings-lens-metrics__note">
          口径：缺失或非正的持仓市值按 0 计入总市值与占比；各加权指标在无有效样本时显示 0。加权时仅对「有有效快照值」且市值大于 0
          的标的计入分子；PE、PB 仅统计正值；与简单算术平均不同，大市值对组合指标影响更大。
        </p>
        <div className="earnings-lens-metrics__grid">
          <MetricCard
            label="加权市盈率 PE(TTM)"
            value={formatNumber(w.weightedPe ?? 0, 2)}
            hint={`${w.countForPe ?? 0} 只参与`}
          />
          <MetricCard
            label="加权市净率 PB"
            value={formatNumber(w.weightedPb ?? 0, 2)}
            hint={`${w.countForPb ?? 0} 只参与`}
          />
          <MetricCard
            label="加权 ROE"
            value={formatPercent(w.weightedRoe ?? 0)}
            hint={`${w.countForRoe ?? 0} 只参与`}
          />
          <MetricCard
            label="加权股息率"
            value={formatPercent(w.weightedDividendYield ?? 0)}
            hint={`${w.countForDividendYield ?? 0} 只参与`}
          />
          <MetricCard
            label="加权毛利率"
            value={formatPercent(w.weightedGrossProfitMargin ?? 0)}
            hint={`${w.countForGrossProfitMargin ?? 0} 只参与`}
          />
          <MetricCard
            label="加权资产负债率"
            value={formatPercent(w.weightedDebtToAssetRatio ?? 0)}
            hint={`${w.countForDebtToAssetRatio ?? 0} 只参与`}
          />
        </div>
      </section>

      <div className="earnings-lens-table-wrapper">
        <table className="stock-table earnings-lens-table">
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>持仓市值(元)</th>
              <th>市值占比</th>
              <th>PE(TTM)</th>
              <th>PB</th>
              <th>快照价</th>
              <th>股息率</th>
              <th>ROE</th>
              <th>毛利率</th>
              <th>营收(元)</th>
              <th>净利(元)</th>
              <th>EPS</th>
              <th>BPS</th>
              <th>资产负债率</th>
              <th>近四年年报（营收 / 净利 / ROE）</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.code}>
                <td>{row.code}</td>
                <td>{row.name}</td>
                <td>{formatMoneyYuan(row.marketValue ?? 0)}</td>
                <td>{formatWeightShare(row.marketWeight)}</td>
                <td>{row.snapshot ? formatNumber(row.snapshot.pe, 2) : '—'}</td>
                <td>{row.snapshot ? formatNumber(row.snapshot.pb, 2) : '—'}</td>
                <td>{row.snapshot ? formatNumber(row.snapshot.price, 2) : '—'}</td>
                <td>{row.snapshot ? formatPercent(row.snapshot.dividendYield) : '—'}</td>
                <td>{row.snapshot ? formatPercent(row.snapshot.roe) : '—'}</td>
                <td>{row.snapshot ? formatPercent(row.snapshot.grossProfitMargin) : '—'}</td>
                <td>{row.snapshot ? formatMoneyYuan(row.snapshot.operatingRevenue) : '—'}</td>
                <td>{row.snapshot ? formatMoneyYuan(row.snapshot.netProfit) : '—'}</td>
                <td>{row.snapshot ? formatNumber(row.snapshot.eps, 3) : '—'}</td>
                <td>{row.snapshot ? formatNumber(row.snapshot.bps, 2) : '—'}</td>
                <td>{row.snapshot ? formatPercent(row.snapshot.debtToAssetRatio) : '—'}</td>
                <td className="earnings-lens-table__trend">
                  {!row.annualReports || row.annualReports.length === 0 ? (
                    <span className="earnings-lens-table__empty">暂无年报数据</span>
                  ) : (
                    <ul className="earnings-lens-trend-list">
                      {row.annualReports.map((a) => (
                        <li key={a.reportPeriod} className="earnings-lens-trend-list__item">
                          <span className="earnings-lens-trend-list__period">
                            {formatReportPeriod(a.reportPeriod)}
                          </span>
                          <span>
                            营收 {formatMoneyYuan(a.operatingRevenue)}；净利 {formatMoneyYuan(a.netProfit)}；ROE{' '}
                            {formatPercent(a.roe)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
