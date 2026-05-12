import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { botDeleteSession, botListSessions, botSessionHistoryMessages, streamBotChat } from '../lib/botApi'

/** 生成新会话 key（与文档示例 api:xxxx 一致） */
function newSessionKey() {
  return `api:${crypto.randomUUID()}`
}

/** 会话列表按更新时间倒序（字符串比较，ISO 日期可排序） */
function sortSessionsDesc(rows) {
  return [...rows].sort((a, b) => {
    const ta = (a.updated_at || a.created_at || '') + String(a.key)
    const tb = (b.updated_at || b.created_at || '') + String(b.key)
    return tb.localeCompare(ta)
  })
}

/** 单条历史消息转界面模型 */
function historyMessageToUi(m, index) {
  const content = typeof m.content === 'string' ? m.content : ''
  const id = `hist-${index}-${m.timestamp ?? index}`
  return {
    id,
    role: m.role || 'unknown',
    content,
    hasTool: Boolean(m.tool_calls || m.tool_call_id || m.name),
  }
}

/** 仅展示用户与助手的有效文本消息，过滤工具消息与空内容 */
function shouldRenderMessage(message) {
  if (!message) return false
  if (message.role === 'tool') return false
  if (message.hasTool) return false
  if (typeof message.content !== 'string') return false
  if (!message.content.trim()) return false
  return message.role === 'user' || message.role === 'assistant'
}

/** 聊天内容统一走 Markdown 渲染，普通文本也可正常展示 */
function MessageContent({ content }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
  )
}

export default function InvestAssistantLayout({ apiBase }) {
  const [sessions, setSessions] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState('')

  const [selectedKey, setSelectedKey] = useState(null)
  const [messages, setMessages] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')

  const [draft, setDraft] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState('')

  const abortRef = useRef(null)

  /** 刷新会话列表（按钮、删除后调用；不在 effect 中直接引用以避免 lint） */
  const refreshSessions = useCallback(async () => {
    setSessionsError('')
    setSessionsLoading(true)
    try {
      const list = await botListSessions(apiBase)
      const sorted = sortSessionsDesc(list)
      setSessions(sorted)
      return sorted
    } catch (e) {
      setSessionsError(e instanceof Error ? e.message : '加载会话失败')
      return []
    } finally {
      setSessionsLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setSessionsError('')
      setSessionsLoading(true)
      try {
        const list = await botListSessions(apiBase)
        if (cancelled) return
        const sorted = sortSessionsDesc(list)
        setSessions(sorted)
        setSelectedKey((prev) => prev ?? sorted[0]?.key ?? null)
      } catch (e) {
        if (!cancelled) {
          setSessionsError(e instanceof Error ? e.message : '加载会话失败')
        }
      } finally {
        if (!cancelled) {
          setSessionsLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [apiBase])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    abortRef.current?.abort()
    if (!selectedKey) {
      return undefined
    }
    let cancelled = false
    ;(async () => {
      setHistoryError('')
      setHistoryLoading(true)
      try {
        const raw = await botSessionHistoryMessages(apiBase, selectedKey, 100)
        if (cancelled) return
        setMessages(raw.map(historyMessageToUi))
      } catch (e) {
        if (!cancelled) {
          setHistoryError(e instanceof Error ? e.message : '加载历史失败')
          setMessages([])
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [selectedKey, apiBase])

  /** 发送完成后与 Abort 恢复时同步服务端历史 */
  const syncHistoryFromServer = useCallback(
    async (key) => {
      if (!key) return
      try {
        const raw = await botSessionHistoryMessages(apiBase, key, 100)
        setMessages(raw.map(historyMessageToUi))
      } catch (e) {
        setHistoryError(e instanceof Error ? e.message : '加载历史失败')
      }
    },
    [apiBase],
  )

  /** 侧栏展示：服务端列表 + 当前选中但尚未出现在列表中的新会话 */
  const displaySessions = useMemo(() => {
    const keys = new Set(sessions.map((s) => s.key))
    const merged = [...sessions]
    if (selectedKey && !keys.has(selectedKey)) {
      merged.unshift({
        key: selectedKey,
        title: '新会话',
        created_at: null,
        updated_at: null,
        preview: '',
      })
    }
    return sortSessionsDesc(merged)
  }, [sessions, selectedKey])

  const displayMessages = useMemo(() => {
    return messages.filter(shouldRenderMessage)
  }, [messages])

  const handleNewChat = () => {
    abortRef.current?.abort()
    setStreamError('')
    const key = newSessionKey()
    setSelectedKey(key)
    setMessages([])
  }

  const handleSelectSession = (key) => {
    if (key === selectedKey) return
    setStreamError('')
    setSelectedKey(key)
  }

  const handleDeleteSession = async (key, ev) => {
    ev.stopPropagation()
    if (!window.confirm('确定删除该会话？删除后无法恢复。')) return
    try {
      await botDeleteSession(apiBase, key)
      const list = await refreshSessions()
      setSelectedKey((prev) => {
        if (prev !== key) return prev
        return list[0]?.key ?? null
      })
    } catch (e) {
      window.alert(e instanceof Error ? e.message : '删除失败')
    }
  }

  /**
   * 发送一条消息。
   * - 不传参数：使用输入框 draft（兼容原有 Enter 发送 / 点击发送按钮路径）
   * - 传入 overrideText：用按钮等"快速回复"方式直接发送指定文本，不动 draft
   */
  const handleSend = async (overrideText) => {
    const sourceText = typeof overrideText === 'string' ? overrideText : draft
    const text = sourceText.trim()
    if (!text || !selectedKey || isStreaming) return

    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac

    const keySnapshot = selectedKey

    if (typeof overrideText !== 'string') {
      setDraft('')
    }
    setStreamError('')
    const assistantId = `asst-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', content: text, hasTool: false },
      { id: assistantId, role: 'assistant', content: '', hasTool: false },
    ])
    setIsStreaming(true)

    // 本轮是否触发了 ask_user：若触发，会话此刻在等用户回答，需要保留本地的临时
    // assistant 消息（带 askOptions）以便渲染按钮；不能用服务端历史覆盖，否则按钮会瞬间消失
    let askUserPending = false

    try {
      await streamBotChat(apiBase, keySnapshot, text, {
        signal: ac.signal,
        onDelta: (piece) => {
          setMessages((prev) => {
            const next = [...prev]
            const idx = next.findIndex((m) => m.id === assistantId)
            if (idx !== -1) {
              const row = next[idx]
              next[idx] = { ...row, content: row.content + piece }
            }
            return next
          })
        },
        onAskUser: (options) => {
          // 收到 ask_user 候选项：把选项挂到当前流式 assistant 消息上，UI 渲染为按钮
          askUserPending = true
          setMessages((prev) => {
            const next = [...prev]
            const idx = next.findIndex((m) => m.id === assistantId)
            if (idx !== -1) {
              const row = next[idx]
              next[idx] = { ...row, askOptions: options }
            }
            return next
          })
        },
      })
      await refreshSessions()
      // 仅在没有触发 ask_user 时同步服务端历史；ask_user 期间保留本地 askOptions 用于按钮渲染，
      // 等用户点击按钮发起下一轮（pending_ask_user_id 把它当作工具结果回填）后再同步
      if (!askUserPending) {
        await syncHistoryFromServer(keySnapshot)
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') {
        await syncHistoryFromServer(keySnapshot)
        return
      }
      setStreamError(e instanceof Error ? e.message : '发送失败')
      setMessages((prev) => prev.filter((m) => m.id !== assistantId))
    } finally {
      setIsStreaming(false)
    }
  }

  const sessionTitle = (s) => {
    const t = (s.title || '').trim()
    if (t) return t
    const k = s.key || ''
    return k.length > 28 ? `${k.slice(0, 14)}…${k.slice(-8)}` : k || '未命名'
  }

  return (
    <div className="invest-assistant">
      <aside className="invest-assistant__sidebar" aria-label="会话历史">
        <div className="invest-assistant__sidebar-head">
          <h2 className="invest-assistant__sidebar-title">会话</h2>
          <button type="button" className="invest-assistant__new-btn" onClick={handleNewChat}>
            新会话
          </button>
        </div>
        <button type="button" className="invest-assistant__refresh" onClick={() => void refreshSessions()} disabled={sessionsLoading}>
          {sessionsLoading ? '刷新中…' : '刷新列表'}
        </button>
        {sessionsError ? <p className="invest-assistant__side-error">{sessionsError}</p> : null}
        <ul className="invest-assistant__session-list">
          {displaySessions.map((s) => (
            <li key={s.key}>
              <div
                role="button"
                tabIndex={0}
                className={`invest-assistant__session-item ${selectedKey === s.key ? 'invest-assistant__session-item--active' : ''}`}
                onClick={() => handleSelectSession(s.key)}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault()
                    handleSelectSession(s.key)
                  }
                }}
              >
                <div className="invest-assistant__session-row">
                  <span className="invest-assistant__session-title">{sessionTitle(s)}</span>
                  <button
                    type="button"
                    className="invest-assistant__session-del"
                    title="删除会话"
                    aria-label="删除会话"
                    onClick={(ev) => void handleDeleteSession(s.key, ev)}
                  >
                    ×
                  </button>
                </div>
                {(s.updated_at || s.created_at) && (
                  <span className="invest-assistant__session-meta">{s.updated_at || s.created_at}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
        {!sessionsLoading && !displaySessions.length ? <p className="invest-assistant__empty-hint">暂无会话，点击「新会话」开始</p> : null}
      </aside>

      <section className="invest-assistant__main" aria-label="聊天">
        {!selectedKey ? (
          <div className="invest-assistant__placeholder">
            <p>请从左侧选择会话，或点击「新会话」。</p>
          </div>
        ) : (
          <>
            <header className="invest-assistant__chat-head">
              <span className="invest-assistant__chat-key" title={selectedKey}>
                {selectedKey}
              </span>
            </header>
            {historyLoading ? <p className="invest-assistant__status">加载消息…</p> : null}
            {historyError ? <p className="invest-assistant__status invest-assistant__status--error">{historyError}</p> : null}
            {streamError ? <p className="invest-assistant__status invest-assistant__status--error">{streamError}</p> : null}

            <div className="invest-assistant__messages">
              {displayMessages.map((m) => (
                <div key={m.id} className={`invest-assistant__bubble invest-assistant__bubble--${m.role}`}>
                  <div className="invest-assistant__bubble-role">{m.role}</div>
                  <div className="invest-assistant__bubble-content">
                    <MessageContent content={m.content} />
                  </div>
                  {m.role === 'assistant' && Array.isArray(m.askOptions) && m.askOptions.length > 0 ? (
                    <div
                      className="invest-assistant__ask-options"
                      style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}
                    >
                      {m.askOptions.map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          className="invest-assistant__ask-option"
                          disabled={isStreaming}
                          onClick={() => void handleSend(opt)}
                          style={{
                            padding: '4px 12px',
                            borderRadius: 16,
                            border: '1px solid #888',
                            background: isStreaming ? '#eee' : '#f7f7f7',
                            cursor: isStreaming ? 'not-allowed' : 'pointer',
                          }}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>

            <footer className="invest-assistant__composer">
              <textarea
                className="invest-assistant__textarea"
                rows={3}
                placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                value={draft}
                disabled={isStreaming}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void handleSend()
                  }
                }}
              />
              <div className="invest-assistant__composer-actions">
                <button type="button" className="invest-assistant__send" onClick={() => void handleSend()} disabled={isStreaming || !draft.trim()}>
                  {isStreaming ? '回复中…' : '发送'}
                </button>
              </div>
            </footer>
          </>
        )}
      </section>
    </div>
  )
}
