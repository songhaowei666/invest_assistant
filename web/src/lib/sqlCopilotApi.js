/**
 * 投研数问 SQL Copilot HTTP 封装（与 docs/api/sql-copilot-api.md 一致）
 */
const DEFAULT_USER_ID = 'default_user'

/** 获取可查询范围 */
export async function sqlCopilotQueryScope(apiBase) {
  const res = await fetch(`${apiBase}/sql-copilot/query-scope`)
  if (!res.ok) {
    throw new Error(`query-scope 请求失败: ${res.status}`)
  }
  return res.json()
}

/** 获取会话列表 */
export async function sqlCopilotListSessions(apiBase, { userId = DEFAULT_USER_ID, limit = 100 } = {}) {
  const res = await fetch(`${apiBase}/sql-copilot/sessions/list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, limit }),
  })
  if (!res.ok) {
    throw new Error(`sessions/list 请求失败: ${res.status}`)
  }
  const data = await res.json()
  return Array.isArray(data.sessions) ? data.sessions : []
}

/** 删除会话 */
export async function sqlCopilotDeleteSession(apiBase, sessionId, userId = DEFAULT_USER_ID) {
  const res = await fetch(`${apiBase}/sql-copilot/sessions/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, user_id: userId }),
  })
  if (!res.ok) {
    throw new Error(`sessions/delete 请求失败: ${res.status}`)
  }
  return res.json()
}

/** 查询会话历史 */
export async function sqlCopilotSessionHistory(apiBase, { sessionId, userId = DEFAULT_USER_ID, limit = 100 }) {
  const res = await fetch(`${apiBase}/sql-copilot/sessions/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      user_id: userId,
      limit,
    }),
  })
  if (!res.ok) {
    throw new Error(`sessions/history 请求失败: ${res.status}`)
  }
  const data = await res.json()
  return Array.isArray(data.messages) ? data.messages : []
}

/** 发起问答 */
export async function sqlCopilotChat(apiBase, { sessionId, question, userId = DEFAULT_USER_ID }) {
  const payload = {
    question,
    user_id: userId,
  }
  if (sessionId) {
    payload.session_id = sessionId
  }
  const res = await fetch(`${apiBase}/sql-copilot/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    let msg = `chat 请求失败: ${res.status}`
    try {
      const text = await res.text()
      if (text) msg = text.slice(0, 200)
    } catch {
      /* 忽略 */
    }
    throw new Error(msg)
  }
  return res.json()
}
