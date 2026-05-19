import { useCallback, useState } from 'react'
import { authLogin, authRegister } from '../lib/authApi'
import { clearTokens, setTokens } from '../lib/authStorage'

/**
 * 全屏登录 / 注册（由父组件在接口 401 时展示）
 * @param {{ apiBase: string, onAuthSuccess: () => void, onCancel?: () => void, onTokensCleared?: () => void, intro?: string }} props
 */
export default function LoginLayout({ apiBase, onAuthSuccess, onCancel, onTokensCleared, intro }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const onSubmit = useCallback(
    async (e) => {
      e.preventDefault()
      setError('')
      setMessage('')
      setLoading(true)
      try {
        if (mode === 'login') {
          const data = await authLogin(apiBase, email.trim(), password, null)
          setTokens(data.access_token, data.refresh_token)
          setMessage('登录成功。')
          onAuthSuccess?.()
        } else {
          const data = await authRegister(apiBase, email.trim(), password, name.trim() || undefined)
          setTokens(data.access_token, data.refresh_token)
          setMessage('注册成功，已自动登录。')
          onAuthSuccess?.()
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '请求失败')
      } finally {
        setLoading(false)
      }
    },
    [apiBase, email, password, name, mode, onAuthSuccess],
  )

  const onLogoutLocal = useCallback(() => {
    clearTokens()
    setMessage('已清除本地保存的令牌。')
    setError('')
    onTokensCleared?.()
  }, [onTokensCleared])

  return (
    <div className="login-layout">
      <header className="login-layout__header">
        <h1 className="login-layout__title">登录</h1>
        <p className="login-layout__hint">
          {intro || '请使用已注册邮箱与密码登录。'}
        </p>
        <p className="login-layout__hint login-layout__hint--secondary">
          接口说明：<code>docs/api/auth-api.md</code>（<code>POST /api/v1/auth/login</code>、
          <code>POST /api/v1/auth/register</code>）。
        </p>
      </header>

      {typeof onCancel === 'function' ? (
        <div className="login-layout__toolbar">
          <button type="button" className="login-layout__linkish" onClick={onCancel}>
            暂不登录，返回应用
          </button>
        </div>
      ) : null}

      <div className="login-layout__tabs">
        <button
          type="button"
          className={`login-layout__tab ${mode === 'login' ? 'login-layout__tab--active' : ''}`}
          onClick={() => {
            setMode('login')
            setError('')
            setMessage('')
          }}
        >
          登录
        </button>
        <button
          type="button"
          className={`login-layout__tab ${mode === 'register' ? 'login-layout__tab--active' : ''}`}
          onClick={() => {
            setMode('register')
            setError('')
            setMessage('')
          }}
        >
          注册
        </button>
      </div>

      <form className="login-layout__form" onSubmit={onSubmit}>
        <label className="login-layout__field">
          <span>邮箱</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(ev) => setEmail(ev.target.value)}
            required
          />
        </label>
        {mode === 'register' ? (
          <label className="login-layout__field">
            <span>显示名（可选）</span>
            <input type="text" value={name} onChange={(ev) => setName(ev.target.value)} autoComplete="name" />
          </label>
        ) : null}
        <label className="login-layout__field">
          <span>密码</span>
          <input
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password}
            onChange={(ev) => setPassword(ev.target.value)}
            required
            minLength={1}
          />
        </label>
        <button type="submit" className="login-layout__submit" disabled={loading}>
          {loading ? '提交中…' : mode === 'login' ? '登录' : '注册'}
        </button>
      </form>

      <div className="login-layout__actions">
        <button type="button" className="login-layout__secondary" onClick={onLogoutLocal}>
          清除本地令牌
        </button>
      </div>

      {message ? <p className="login-layout__msg login-layout__msg--ok">{message}</p> : null}
      {error ? <p className="login-layout__msg login-layout__msg--err">{error}</p> : null}
    </div>
  )
}
