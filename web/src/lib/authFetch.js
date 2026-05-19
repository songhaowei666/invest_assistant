/**
 * 带 Bearer 的 fetch：401 时用 refresh 重试一次；仍 401 则触发 onUnauthorized（用于跳转登录页）
 * @param {string} apiBase 如 http://localhost:8000/api/v1
 * @param {string} path 如 /positions 或 /positions/add
 * @param {RequestInit} init 传给 fetch 的选项（可含 method、body 等）
 * @param {() => void} [onUnauthorized] 最终仍为 401 时回调
 */
import { authRefresh } from './authApi'
import { getAccessToken, getRefreshToken, setTokens } from './authStorage'

export async function fetchWithBearer(apiBase, path, init = {}, onUnauthorized) {
  const url = `${apiBase}${path.startsWith('/') ? path : `/${path}`}`

  const buildHeaders = (access) => {
    const h = new Headers(init.headers ?? undefined)
    if (access) {
      h.set('Authorization', `Bearer ${access}`)
    }
    if (init.body != null && !h.has('Content-Type')) {
      h.set('Content-Type', 'application/json')
    }
    return h
  }

  let access = getAccessToken()
  let res = await fetch(url, { ...init, headers: buildHeaders(access) })

  if (res.status === 401) {
    const rt = getRefreshToken()
    if (rt) {
      try {
        const data = await authRefresh(apiBase, rt)
        setTokens(data.access_token, data.refresh_token)
        access = data.access_token
        res = await fetch(url, { ...init, headers: buildHeaders(access) })
      } catch {
        /* refresh 失败，保留首次 401 响应 */
      }
    }
  }

  if (res.status === 401 && typeof onUnauthorized === 'function') {
    onUnauthorized()
  }
  return res
}
