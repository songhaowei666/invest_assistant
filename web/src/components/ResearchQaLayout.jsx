import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  sqlCopilotChat,
  sqlCopilotDeleteSession,
  sqlCopilotListSessions,
  sqlCopilotQueryScope,
  sqlCopilotSessionHistory,
} from '../lib/sqlCopilotApi'

/** 会话按更新时间倒序展示 */
function sortSessionsDesc(rows) {
  return [...rows].sort((a, b) => {
    const ta = (a.updated_at || a.created_at || '') + String(a.session_id || '')
    const tb = (b.updated_at || b.created_at || '') + String(b.session_id || '')
    return tb.localeCompare(ta)
  })
}

/** 格式化会话标题，避免空标题直接展示空串 */
function sessionTitle(s) {
  const title = (s.title || '').trim()
  if (title) return title
  const id = s.session_id || ''
  if (!id) return '未命名会话'
  return id.length > 28 ? `${id.slice(0, 14)}…${id.slice(-8)}` : id
}

/**
 * 会话列表副标题：只展示用户第一条问题，不展示接口返回的 JSON 原文。
 * 优先用已加载的聊天记录；否则尝试从 preview 字段解析 JSON 中的 question。
 */
function sessionPreviewText(s, chatBySession) {
  const chat = chatBySession[s.session_id]
  if (Array.isArray(chat) && chat.length > 0) {
    const firstUser = chat.find((m) => m.role === 'user')
    const q = typeof firstUser?.question === 'string' ? firstUser.question.trim() : ''
    if (q) return q
  }
  const raw = (s.preview || '').trim()
  if (!raw) return '暂无预览内容'
  if (raw.startsWith('{')) {
    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object' && typeof parsed.question === 'string') {
        const q = parsed.question.trim()
        if (q) return q
      }
    } catch {
      /* 非 JSON 则回退为原文 */
    }
  }
  return raw
}

/** 会话列表项映射到统一结构 */
function mapSession(s) {
  return {
    session_id: s.session_id || '',
    title: s.title || '',
    preview: s.preview || '',
    created_at: s.created_at || '',
    updated_at: s.updated_at || '',
    message_count: Number(s.message_count || 0),
  }
}

function mapHistoryMessage(item) {
  const role = item?.role === 'assistant' ? 'assistant' : 'user'
  const content = typeof item?.content === 'string' ? item.content : ''

  if (role !== 'assistant') {
    return { role: 'user', question: content, answer: '', sql: '', rows: [], columns: [], error: '' }
  }

  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object') {
      return {
        role: 'assistant',
        question: typeof parsed.question === 'string' ? parsed.question : '',
        answer: typeof parsed.answer === 'string' ? parsed.answer : '',
        sql: typeof parsed.sql === 'string' ? parsed.sql : '',
        rows: Array.isArray(parsed.rows_preview) ? parsed.rows_preview : [],
        columns: [],
        error: typeof parsed.error === 'string' ? parsed.error : '',
      }
    }
  } catch {
    /* 历史中可能是纯文本，保持兼容 */
  }

  return { role: 'assistant', question: '', answer: content, sql: '', rows: [], columns: [], error: '' }
}

export default function ResearchQaLayout({ apiBase }) {
  const [scopeLoading, setScopeLoading] = useState(false)
  const [scopeHintVisible, setScopeHintVisible] = useState(false)
  const [scopeHintTitle, setScopeHintTitle] = useState('功能提示')
  const [scopeHintContent, setScopeHintContent] = useState('')

  const [sessions, setSessions] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState('')

  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [chatBySession, setChatBySession] = useState({})
  const [historyLoadedBySession, setHistoryLoadedBySession] = useState({})
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')

  const [draft, setDraft] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const selectedChat = useMemo(() => {
    if (!selectedSessionId) return []
    return Array.isArray(chatBySession[selectedSessionId]) ? chatBySession[selectedSessionId] : []
  }, [selectedSessionId, chatBySession])

  const handleShowScopeHint = useCallback(async () => {
    setScopeLoading(true)
    try {
      const data = await sqlCopilotQueryScope(apiBase)
      const summary = typeof data.scope_summary === 'string' ? data.scope_summary : ''
      setScopeHintTitle('功能提示')
      setScopeHintContent(summary || '暂无功能提示')
      setScopeHintVisible(true)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载可查询范围失败'
      setScopeHintTitle('提示加载失败')
      setScopeHintContent(msg)
      setScopeHintVisible(true)
    } finally {
      setScopeLoading(false)
    }
  }, [apiBase])

  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true)
    setSessionsError('')
    try {
      const list = await sqlCopilotListSessions(apiBase)
      const sorted = sortSessionsDesc(list.map(mapSession))
      setSessions(sorted)
      return sorted
    } catch (e) {
      setSessionsError(e instanceof Error ? e.message : '加载会话列表失败')
      return []
    } finally {
      setSessionsLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const sorted = await refreshSessions()
      if (!cancelled) {
        setSelectedSessionId((prev) => prev || sorted[0]?.session_id || '')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshSessions])

  useEffect(() => {
    if (!selectedSessionId) {
      setHistoryLoading(false)
      setHistoryError('')
      return
    }
    if (historyLoadedBySession[selectedSessionId]) {
      return
    }

    let cancelled = false
    ;(async () => {
      setHistoryLoading(true)
      setHistoryError('')
      try {
        const messages = await sqlCopilotSessionHistory(apiBase, { sessionId: selectedSessionId })
        if (cancelled) return
        const mapped = messages.map(mapHistoryMessage)
        setChatBySession((prev) => ({ ...prev, [selectedSessionId]: mapped }))
        setHistoryLoadedBySession((prev) => ({ ...prev, [selectedSessionId]: true }))
      } catch (e) {
        if (cancelled) return
        setHistoryError(e instanceof Error ? e.message : '加载会话历史失败')
      } finally {
        if (!cancelled) {
          setHistoryLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [apiBase, selectedSessionId, historyLoadedBySession])

  const handleNewSession = () => {
    setSubmitError('')
    setSelectedSessionId('')
    setHistoryError('')
    setDraft('')
  }

  const handleDeleteSession = async (sessionId, ev) => {
    ev.stopPropagation()
    if (!window.confirm('确定删除该会话？删除后无法恢复。')) return
    try {
      await sqlCopilotDeleteSession(apiBase, sessionId)
      setChatBySession((prev) => {
        const next = { ...prev }
        delete next[sessionId]
        return next
      })
      setHistoryLoadedBySession((prev) => {
        const next = { ...prev }
        delete next[sessionId]
        return next
      })
      const sorted = await refreshSessions()
      setSelectedSessionId((prev) => {
        if (prev && prev !== sessionId) return prev
        return sorted[0]?.session_id || ''
      })
    } catch (e) {
      window.alert(e instanceof Error ? e.message : '删除失败')
    }
  }

  const handleSend = async () => {
    const question = draft.trim()
    if (!question || isSubmitting) return

    setIsSubmitting(true)
    setSubmitError('')
    setDraft('')

    const pendingId = `pending-${Date.now()}`
    const baseSessionId = selectedSessionId
    const targetSessionId = baseSessionId || pendingId
    const askRecord = { role: 'user', question, answer: '', sql: '', rows: [], columns: [], error: '' }
    setSelectedSessionId(targetSessionId)
    setChatBySession((prev) => ({
      ...prev,
      [targetSessionId]: [...(Array.isArray(prev[targetSessionId]) ? prev[targetSessionId] : []), askRecord],
    }))
    setHistoryLoadedBySession((prev) => ({ ...prev, [targetSessionId]: true }))

    try {
      const result = await sqlCopilotChat(apiBase, {
        sessionId: baseSessionId || undefined,
        question,
      })

      const resolvedSessionId = typeof result.session_id === 'string' ? result.session_id : targetSessionId
      const responseRecord = {
        role: 'assistant',
        question: typeof result.question === 'string' ? result.question : question,
        answer: typeof result.answer === 'string' ? result.answer : '',
        sql: typeof result.sql === 'string' ? result.sql : '',
        rows: Array.isArray(result.rows) ? result.rows : [],
        columns: Array.isArray(result.columns) ? result.columns : [],
        error: typeof result.error === 'string' ? result.error : '',
      }

      setChatBySession((prev) => {
        const pendingList = Array.isArray(prev[targetSessionId]) ? prev[targetSessionId] : []
        const nextList = [...pendingList, responseRecord]
        const next = { ...prev, [resolvedSessionId]: nextList }
        if (resolvedSessionId !== targetSessionId) {
          delete next[targetSessionId]
        }
        return next
      })
      setHistoryLoadedBySession((prev) => {
        const next = { ...prev, [resolvedSessionId]: true }
        if (resolvedSessionId !== targetSessionId) {
          delete next[targetSessionId]
        }
        return next
      })
      setSelectedSessionId(resolvedSessionId)
      await refreshSessions()
    } catch (e) {
      const msg = e instanceof Error ? e.message : '发送失败'
      setSubmitError(msg)
      setChatBySession((prev) => {
        const list = Array.isArray(prev[targetSessionId]) ? prev[targetSessionId] : []
        if (!list.length) return prev
        const nextList = [...list]
        nextList[nextList.length - 1] = {
          ...nextList[nextList.length - 1],
          error: msg,
        }
        return { ...prev, [targetSessionId]: nextList }
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const closeScopeHint = () => {
    setScopeHintVisible(false)
  }

  return (
    <div className="research-qa">
      <aside className="research-qa__sidebar" aria-label="投研数问会话">
        <div className="research-qa__sidebar-top">
          <button type="button" className="research-qa__new-btn" onClick={handleNewSession}>
            新建会话
          </button>
          <button type="button" className="research-qa__new-btn" onClick={() => void handleShowScopeHint()} disabled={scopeLoading}>
            {scopeLoading ? '加载中…' : '功能提示'}
          </button>
        </div>

        <div className="research-qa__sidebar-bottom">
          <div className="research-qa__history-head">
            <h3>会话历史</h3>
            <button type="button" className="research-qa__refresh-btn" onClick={() => void refreshSessions()} disabled={sessionsLoading}>
              {sessionsLoading ? '刷新中…' : '刷新'}
            </button>
          </div>
          {sessionsError ? <p className="research-qa__error">{sessionsError}</p> : null}
          <ul className="research-qa__session-list">
            {sessions.map((s) => (
              <li key={s.session_id}>
                <div
                  role="button"
                  tabIndex={0}
                  className={`research-qa__session-item ${selectedSessionId === s.session_id ? 'research-qa__session-item--active' : ''}`}
                  onClick={() => setSelectedSessionId(s.session_id)}
                  onKeyDown={(ev) => {
                    if (ev.key === 'Enter' || ev.key === ' ') {
                      ev.preventDefault()
                      setSelectedSessionId(s.session_id)
                    }
                  }}
                >
                  <div className="research-qa__session-row">
                    <span className="research-qa__session-title">{sessionTitle(s)}</span>
                    <button
                      type="button"
                      className="research-qa__session-del"
                      aria-label="删除会话"
                      title="删除会话"
                      onClick={(ev) => void handleDeleteSession(s.session_id, ev)}
                    >
                      ×
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {!sessionsLoading && !sessions.length ? <p className="research-qa__empty">暂无会话，点击「新建会话」开始提问</p> : null}
        </div>
      </aside>

      <section className="research-qa__main" aria-label="投研数问聊天区">
        {historyError ? <p className="research-qa__submit-error">{historyError}</p> : null}
        <div className="research-qa__chat-list">
          {historyLoading ? (
            <div className="research-qa__placeholder">历史聊天加载中...</div>
          ) : !selectedChat.length ? (
            <div className="research-qa__placeholder">请输入问题开始投研数问。</div>
          ) : (
            selectedChat.map((item, index) => {
              if (item.role === 'user') {
                return (
                  <div key={`u-${index}`} className="research-qa__bubble research-qa__bubble--user">
                    <div className="research-qa__bubble-title">我</div>
                    <div className="research-qa__bubble-text">{item.question}</div>
                    {item.error ? <div className="research-qa__bubble-error">{item.error}</div> : null}
                  </div>
                )
              }

              return (
                <div key={`a-${index}`} className="research-qa__bubble research-qa__bubble--assistant">
                  <div className="research-qa__bubble-title">投研数问</div>
                  <div className="research-qa__bubble-text">{item.answer || '未返回总结内容'}</div>
                  {item.sql ? (
                    <details className="research-qa__sql-box">
                      <summary>查看 SQL</summary>
                      <pre>{item.sql}</pre>
                    </details>
                  ) : null}
                  {item.error ? <div className="research-qa__bubble-error">{item.error}</div> : null}
                </div>
              )
            })
          )}
        </div>
        {submitError ? <p className="research-qa__submit-error">{submitError}</p> : null}
        <footer className="research-qa__composer">
          <textarea
            className="research-qa__textarea"
            rows={3}
            placeholder="请输入问题，Enter 发送，Shift+Enter 换行"
            value={draft}
            disabled={isSubmitting}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSend()
              }
            }}
          />
          <div className="research-qa__actions">
            <button type="button" className="research-qa__send-btn" onClick={() => void handleSend()} disabled={isSubmitting || !draft.trim()}>
              {isSubmitting ? '发送中…' : '发送'}
            </button>
          </div>
        </footer>
      </section>
      {scopeHintVisible ? (
        <div className="research-qa__hint-mask" onClick={closeScopeHint}>
          <div
            className="research-qa__hint-modal"
            role="dialog"
            aria-modal="true"
            aria-label={scopeHintTitle}
            onClick={(ev) => ev.stopPropagation()}
          >
            <div className="research-qa__hint-head">
              <h3>{scopeHintTitle}</h3>
              <button type="button" className="research-qa__hint-close" onClick={closeScopeHint} aria-label="关闭提示框">
                ×
              </button>
            </div>
            <div className="research-qa__hint-body">{scopeHintContent}</div>
            <div className="research-qa__hint-actions">
              <button type="button" className="research-qa__hint-btn" onClick={closeScopeHint}>
                我知道了
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
