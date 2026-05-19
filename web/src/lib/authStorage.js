/**
 * 浏览器端 access / refresh 存储（与 docs/api/auth-api.md 一致）
 * 键名带前缀，避免与其它站点扩展冲突。
 */

const KEY_ACCESS = 'invest_assistant_access_token'
const KEY_REFRESH = 'invest_assistant_refresh_token'

export function getAccessToken() {
  return localStorage.getItem(KEY_ACCESS) || ''
}

export function getRefreshToken() {
  return localStorage.getItem(KEY_REFRESH) || ''
}

export function setTokens(accessToken, refreshToken) {
  localStorage.setItem(KEY_ACCESS, accessToken)
  localStorage.setItem(KEY_REFRESH, refreshToken)
}

export function clearTokens() {
  localStorage.removeItem(KEY_ACCESS)
  localStorage.removeItem(KEY_REFRESH)
}
