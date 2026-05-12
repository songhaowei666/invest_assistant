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

/**
 * 解析单个完整的 SSE 事件块（按 \n\n 切分得到，块内可能包含 event: 与 data: 多行）
 * - 默认 event 为 message：OpenAI 兼容的 chunk，取 choices[0].delta.content 作为增量
 * - event 为 ask_user：后端在 ask_user 工具触发时下发的候选项，data 形如 {"options": ["是","否"]}
 * 兼容性：未声明回调时直接忽略对应事件类型，向后兼容旧调用方
 */
function parseSseEventBlock(block, callbacks) {
  const { onDelta, onAskUser } = callbacks
  let eventName = 'message'
  const dataLines = []
  for (const rawLine of block.split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      const name = line.slice(6).trim()
      if (name) eventName = name
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  if (dataLines.length === 0) return
  const payload = dataLines.join('\n')
  if (payload === '[DONE]') return
  if (eventName === 'message') {
    try {
      const json = JSON.parse(payload)
      const piece = json?.choices?.[0]?.delta?.content
      if (typeof piece === 'string' && piece.length > 0) {
        onDelta?.(piece)
      }
    } catch {
      /* 非 JSON 行忽略 */
    }
  } else if (eventName === 'ask_user') {
    try {
      const json = JSON.parse(payload)
      const options = Array.isArray(json?.options)
        ? json.options.filter((o) => typeof o === 'string' && o.length > 0)
        : []
      if (options.length > 0) {
        onAskUser?.(options)
      }
    } catch {
      /* 非 JSON 行忽略 */
    }
  }
}

/**
 * 流式聊天：按 SSE 规范解析事件块
 * - onDelta(piece)：默认 message 事件下发的文本增量
 * - onAskUser(options)：ask_user 事件下发的候选项数组（可选）
 * - signal：AbortSignal，用于取消流
 */
export async function streamBotChat(apiBase, key, content, { onDelta, onAskUser, signal }) {
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
  const callbacks = { onDelta, onAskUser }
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 事件以空行（\n\n 或 \r\n\r\n）作为块分隔符；统一换行后再切分
    const normalized = buffer.replace(/\r\n/g, '\n')
    const blocks = normalized.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      if (block.trim()) parseSseEventBlock(block, callbacks)
    }
  }
  if (buffer.trim()) {
    parseSseEventBlock(buffer, callbacks)
  }
}
