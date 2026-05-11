/**
 * 投资助手 Bot HTTP 封装（与 docs/bot--api.md 一致）
 */

/** 拉取会话列表 */
export async function botListSessions(apiBase) {
  const res = await fetch(`${apiBase}/bot/sessions/list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  })
  if (!res.ok) {
    throw new Error(`sessions/list 请求失败: ${res.status}`)
  }
  const data = await res.json()
  return Array.isArray(data.sessions) ? data.sessions : []
}

/** 删除会话 */
export async function botDeleteSession(apiBase, key) {
  const res = await fetch(`${apiBase}/bot/sessions/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key }),
  })
  if (!res.ok) {
    throw new Error(`sessions/delete 请求失败: ${res.status}`)
  }
  return res.json()
}

/** 查询会话历史 */
export async function botSessionHistory(apiBase, key, limit = 80) {
  const res = await fetch(`${apiBase}/bot/sessions/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, limit }),
  })
  if (!res.ok) {
    throw new Error(`sessions/history 请求失败: ${res.status}`)
  }
  return res.json()
}

/** 拉取会话历史的 messages 数组（原始项，供界面映射） */
export async function botSessionHistoryMessages(apiBase, key, limit = 100) {
  const data = await botSessionHistory(apiBase, key, limit)
  return Array.isArray(data.messages) ? data.messages : []
}

/** 解析单行 SSE data: 负载 */
function parseSseDataLine(trimmedLine, onDelta) {
  if (!trimmedLine.startsWith('data:')) return
  const payload = trimmedLine.slice(5).trimStart()
  if (payload === '[DONE]') return
  try {
    const json = JSON.parse(payload)
    const piece = json?.choices?.[0]?.delta?.content
    if (typeof piece === 'string' && piece.length > 0) {
      onDelta(piece)
    }
  } catch {
    /* 非 JSON 行忽略 */
  }
}

/**
 * 流式聊天：解析 data: JSON 行，将增量文本交给 onDelta
 * @param {AbortSignal} [options.signal]
 */
export async function streamBotChat(apiBase, key, content, { onDelta, signal }) {
  const res = await fetch(`${apiBase}/bot/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, content }),
    signal,
  })
  if (!res.ok) {
    let msg = `chat 请求失败: ${res.status}`
    try {
      const t = await res.text()
      if (t) msg = t.slice(0, 200)
    } catch {
      /* 忽略 */
    }
    throw new Error(msg)
  }
  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('响应无 body')
  }
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n')
    buffer = parts.pop() ?? ''
    for (const line of parts) {
      parseSseDataLine(line.trim(), onDelta)
    }
  }
  if (buffer.trim()) {
    parseSseDataLine(buffer.trim(), onDelta)
  }
}
