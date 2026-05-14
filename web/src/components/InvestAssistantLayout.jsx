import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { botDeleteSession, botListSessions, botSessionHistoryMessages, botUpdateSessionTitle, streamBotChat } from '../lib/botApi'

/** 生成新会话 key（与文档示例 api:xxxx 一致） */
function newSessionKey() {
  return `api:${crypto.randomUUID()}`
}

/** 会话列表按创建时间倒序（新会话在上；ISO 字符串可字典序比较；无 created_at 时退化为 key） */
function sortSessionsDesc(rows) {
  return [...rows].sort((a, b) => {
    const ta = (a.created_at || '') + String(a.key)
    const tb = (b.created_at || '') + String(b.key)
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

/** 将模型输出中连续多行空行压成最多一行空行，减少 Markdown 分段后的大块留白 */
function normalizeChatMarkdownSource(raw) {
  if (typeof raw !== 'string') return ''
  return raw
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trimEnd()
}

/** 聊天内容统一走 Markdown 渲染，普通文本也可正常展示 */
function MessageContent({ content }) {
  const text = normalizeChatMarkdownSource(content)
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
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

  /** 删除确认：待删除的 session key；null 表示未打开对话框 */
  const [deleteConfirmKey, setDeleteConfirmKey] = useState(null)
  const [deleteError, setDeleteError] = useState('')
  const [deleteSubmitting, setDeleteSubmitting] = useState(false)

  const abortRef = useRef(null)
  /** 取消尚未完成的会话列表请求，避免后返回的旧响应覆盖新数据（如改名后标题被首问摘要顶回） */
  const listSessionsAbortRef = useRef(null)

  /** 刷新会话列表（按钮、删除后调用；不在 effect 中直接引用以避免 lint） */
  const refreshSessions = useCallback(async () => {
    listSessionsAbortRef.current?.abort()
    const ac = new AbortController()
    listSessionsAbortRef.current = ac
    setSessionsError('')
    setSessionsLoading(true)
    try {
      const list = await botListSessions(apiBase, { signal: ac.signal })
      const sorted = sortSessionsDesc(list)
      setSessions(sorted)
      return sorted
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') {
        return []
      }
      setSessionsError(e instanceof Error ? e.message : '加载会话失败')
      return []
    } finally {
      if (listSessionsAbortRef.current === ac) {
        listSessionsAbortRef.current = null
      }
      setSessionsLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const sorted = await refreshSessions()
      if (cancelled) return
      setSelectedKey((prev) => prev ?? sorted[0]?.key ?? null)
    })()
    return () => {
      cancelled = true
      listSessionsAbortRef.current?.abort()
    }
  }, [apiBase, refreshSessions])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    if (!deleteConfirmKey) return undefined
    const onKeyDown = (ev) => {
      if (ev.key === 'Escape') {
        if (deleteSubmitting) return
        ev.preventDefault()
        setDeleteConfirmKey(null)
        setDeleteError('')
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [deleteConfirmKey, deleteSubmitting])

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

  /** 侧栏：先按创建时间排序服务端列表；当前选中且未落库的会话固定置顶展示 */
  const displaySessions = useMemo(() => {
    const keys = new Set(sessions.map((s) => s.key))
    const sorted = sortSessionsDesc(sessions)
    if (selectedKey && !keys.has(selectedKey)) {
      return [
        {
          key: selectedKey,
          title: '新会话',
          created_at: null,
          updated_at: null,
          preview: '',
        },
        ...sorted,
      ]
    }
    return sorted
  }, [sessions, selectedKey])

  const displayMessages = useMemo(() => {
    return messages.filter(shouldRenderMessage)
  }, [messages])

  const sessionTitle = (s) => {
    const t = (s.title || '').trim()
    if (t) return t
    const k = s.key || ''
    return k.length > 28 ? `${k.slice(0, 14)}…${k.slice(-8)}` : k || '未命名'
  }

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

  const handleRenameSession = async (s, ev) => {
    ev.stopPropagation()
    const key = s.key
    const existsOnServer = sessions.some((row) => row.key === key)
    if (!existsOnServer) {
      window.alert('请先发一条消息保存会话后再修改标题')
      return
    }
    const current = sessionTitle(s)
    const input = window.prompt('修改会话标题', current)
    if (input == null) return
    const title = input.trim()
    if (!title) {
      window.alert('标题不能为空')
      return
    }
    try {
      const data = await botUpdateSessionTitle(apiBase, key, title)
      if (!data?.updated) {
        window.alert('修改失败：会话不存在或无权限')
        return
      }
      await refreshSessions()
    } catch (e) {
      window.alert(e instanceof Error ? e.message : '修改标题失败')
    }
  }

  const openDeleteConfirm = (key, ev) => {
    ev.stopPropagation()
    setDeleteError('')
    setDeleteSubmitting(false)
    setDeleteConfirmKey(key)
  }

  const closeDeleteConfirm = () => {
    if (deleteSubmitting) return
    setDeleteConfirmKey(null)
    setDeleteError('')
  }

  const confirmDeleteSession = async () => {
    const key = deleteConfirmKey
    if (!key || deleteSubmitting) return
    setDeleteError('')
    setDeleteSubmitting(true)
    try {
      await botDeleteSession(apiBase, key)
      setDeleteConfirmKey(null)
      setDeleteError('')
      const list = await refreshSessions()
      setSelectedKey((prev) => {
        if (prev !== key) return prev
        return list[0]?.key ?? null
      })
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : '删除失败')
    } finally {
      setDeleteSubmitting(false)
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
                  <div className="invest-assistant__session-actions">
                    <button
                      type="button"
                      className="invest-assistant__session-rename"
                      title="修改标题"
                      aria-label="修改标题"
                      onClick={(ev) => void handleRenameSession(s, ev)}
                    >
                      <svg
                        className="invest-assistant__session-rename-icon"
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M12 20h9" />
                        <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className="invest-assistant__session-del"
                      title="删除会话"
                      aria-label="删除会话"
                      onClick={(ev) => void openDeleteConfirm(s.key, ev)}
                    >
                      ×
                    </button>
                  </div>
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

      {deleteConfirmKey ? (
        <div
          className="invest-assistant__modal-backdrop"
          role="presentation"
          onClick={deleteSubmitting ? undefined : closeDeleteConfirm}
        >
          <div
            className="invest-assistant__modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="invest-assistant-delete-title"
            onClick={(ev) => ev.stopPropagation()}
          >
            <h3 id="invest-assistant-delete-title" className="invest-assistant__modal-title">
              删除会话
            </h3>
            <p className="invest-assistant__modal-text">确定删除该会话？删除后无法恢复。</p>
            {deleteError ? <p className="invest-assistant__modal-error">{deleteError}</p> : null}
            <div className="invest-assistant__modal-actions">
              <button type="button" className="invest-assistant__modal-btn" disabled={deleteSubmitting} onClick={closeDeleteConfirm}>
                取消
              </button>
              <button
                type="button"
                className="invest-assistant__modal-btn invest-assistant__modal-btn--danger"
                disabled={deleteSubmitting}
                onClick={() => void confirmDeleteSession()}
              >
                {deleteSubmitting ? '删除中…' : '删除'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
