/** 定时任务 API（/api/v1/scheduled-tasks） */

async function parseError(res) {
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      return data.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
    }
  } catch {
    /* ignore */
  }
  return `请求失败: ${res.status}`
}

/** 从 api/tasks 扫描可用的 Celery 任务名 */
export async function fetchScheduledTaskKeys(apiBase) {
  const res = await fetch(`${apiBase}/scheduled-tasks/task-keys`)
  if (!res.ok) {
    throw new Error(await parseError(res))
  }
  const data = await res.json()
  return Array.isArray(data.items) ? data.items : []
}

/** 查询列表 */
export async function fetchScheduledTasks(apiBase) {
  const res = await fetch(`${apiBase}/scheduled-tasks`)
  if (!res.ok) {
    throw new Error(await parseError(res))
  }
  const data = await res.json()
  return Array.isArray(data.items) ? data.items : []
}

/** 批量新增 */
export async function addScheduledTasks(apiBase, rows) {
  const res = await fetch(`${apiBase}/scheduled-tasks/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rows),
  })
  if (!res.ok) {
    throw new Error(await parseError(res))
  }
  const data = await res.json()
  return Array.isArray(data.items) ? data.items : []
}

/** 批量修改 */
export async function modifyScheduledTasks(apiBase, rows) {
  const res = await fetch(`${apiBase}/scheduled-tasks/modify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rows),
  })
  if (!res.ok) {
    throw new Error(await parseError(res))
  }
  const data = await res.json()
  return Array.isArray(data.items) ? data.items : []
}
