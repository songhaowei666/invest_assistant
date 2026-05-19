/**
 * 认证 HTTP 封装（与 docs/api/auth-api.md 一致）
 * @param {string} apiBase 例如 http://localhost:8000/api/v1
 */

async function readErrorMessage(res) {
  try {
    const j = await res.json()
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) {
      return j.detail.map((x) => (x && x.msg ? x.msg : JSON.stringify(x))).join('；')
    }
  } catch {
    // ignore
  }
  return `请求失败: ${res.status}`
}

/** @param {string} apiBase */
export async function authLogin(apiBase, email, password, inviteToken) {
  const body = { email, password }
  if (inviteToken) body.invite_token = inviteToken
  const res = await fetch(`${apiBase}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await readErrorMessage(res))
  return res.json()
}

/** @param {string} apiBase */
export async function authRegister(apiBase, email, password, name) {
  const res = await fetch(`${apiBase}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, ...(name ? { name } : {}) }),
  })
  if (!res.ok) throw new Error(await readErrorMessage(res))
  return res.json()
}

/** @param {string} apiBase */
export async function authMe(apiBase, accessToken) {
  const res = await fetch(`${apiBase}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!res.ok) throw new Error(await readErrorMessage(res))
  return res.json()
}

/** @param {string} apiBase */
export async function authRefresh(apiBase, refreshToken) {
  const res = await fetch(`${apiBase}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) throw new Error(await readErrorMessage(res))
  return res.json()
}

/** @param {string} apiBase */
export async function authLogout(apiBase, refreshToken) {
  const res = await fetch(`${apiBase}/auth/logout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!res.ok) throw new Error(await readErrorMessage(res))
}
