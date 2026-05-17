import { useCallback, useEffect, useState } from 'react'
import {
  addScheduledTasks,
  fetchBeatSchedule,
  fetchScheduledTaskKeys,
  fetchScheduledTasks,
  modifyScheduledTasks,
} from '../lib/scheduledTasksApi'

const emptyForm = () => ({
  name: '',
  cron_expr: '',
  task_key: '',
  enabled: true,
})

function formatDateTime(value) {
  if (!value) {
    return '—'
  }
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) {
    return '—'
  }
  return d.toLocaleString('zh-CN')
}

function truncateLog(log, maxLen = 80) {
  if (!log) {
    return '—'
  }
  if (log.length <= maxLen) {
    return log
  }
  return `${log.slice(0, maxLen)}…`
}

function buildTaskKeyOptions(taskKeyOptions, currentKey) {
  const keys = [...taskKeyOptions]
  if (currentKey && !keys.includes(currentKey)) {
    keys.unshift(currentKey)
  }
  return keys
}

function TaskEditorModal({
  editingId,
  form,
  formError,
  submitting,
  taskKeyOptions,
  onFieldChange,
  onSubmit,
  onClose,
}) {
  const selectableKeys = buildTaskKeyOptions(taskKeyOptions, form.task_key)
  return (
    <div
      className="ai-modal scheduled-tasks-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="scheduled-tasks-modal-title"
      onClick={(e) => e.stopPropagation()}
    >
      <h3 id="scheduled-tasks-modal-title">{editingId == null ? '新增定时任务' : '编辑定时任务'}</h3>
      <label className="scheduled-tasks-form__label">
        任务名称
        <input
          className="ai-modal__input"
          value={form.name}
          onChange={(e) => onFieldChange('name', e.target.value)}
          maxLength={128}
        />
      </label>
      <label className="scheduled-tasks-form__label">
        cron 表达式
        <input
          className="ai-modal__input"
          value={form.cron_expr}
          onChange={(e) => onFieldChange('cron_expr', e.target.value)}
          placeholder="0 9 * * *"
          maxLength={128}
        />
      </label>
      <label className="scheduled-tasks-form__label">
        Celery 任务名
        <select
          className="ai-modal__input scheduled-tasks-form__select"
          value={form.task_key}
          onChange={(e) => onFieldChange('task_key', e.target.value)}
        >
          <option value="">请选择（来自 api/tasks）</option>
          {selectableKeys.map((key) => (
            <option key={key} value={key}>
              {key}
            </option>
          ))}
        </select>
        {selectableKeys.length === 0 ? (
          <span className="scheduled-tasks-form__hint">未扫描到任务，请在 api/tasks 下添加 @shared_task</span>
        ) : null}
      </label>
      <label className="scheduled-tasks-form__checkbox">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => onFieldChange('enabled', e.target.checked)}
        />
        启用
      </label>
      {formError ? <p className="status-text status-text--error">{formError}</p> : null}
      <div className="ai-modal__actions">
        <button type="button" onClick={onClose} disabled={submitting}>
          取消
        </button>
        <button type="button" onClick={onSubmit} disabled={submitting}>
          {submitting ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  )
}

function BeatScheduleModal({ loading, errorMsg, brokerConfigured, items, onClose, onRetry }) {
  return (
    <div
      className="ai-modal scheduled-tasks-modal scheduled-tasks-beat-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="beat-schedule-modal-title"
      onClick={(e) => e.stopPropagation()}
    >
      <h3 id="beat-schedule-modal-title">Beat 调度列表</h3>
      <p className="scheduled-tasks-beat-modal__subtitle">
        来自已启用的定时任务配置，与 Beat 进程 DatabaseBeatScheduler 加载逻辑一致。
      </p>
      {!brokerConfigured ? (
        <p className="scheduled-tasks-beat-modal__warn">未配置 CELERY_BROKER_URL，Beat 无法调度任务。</p>
      ) : null}
      {loading ? <p className="status-text">加载中...</p> : null}
      {!loading && errorMsg ? (
        <p className="status-text status-text--error">
          {errorMsg}
          <button type="button" className="earnings-lens__retry" onClick={onRetry}>
            重试
          </button>
        </p>
      ) : null}
      {!loading && !errorMsg && items.length === 0 ? (
        <p className="scheduled-tasks__empty">当前没有已启用且将进入 Beat 调度的任务。</p>
      ) : null}
      {!loading && !errorMsg && items.length > 0 ? (
        <div className="scheduled-tasks-beat-modal__table-wrap stock-table-wrapper">
          <table className="scheduled-tasks-table stock-table">
            <thead>
              <tr>
                <th>Beat 键名</th>
                <th>任务名称</th>
                <th>cron</th>
                <th>Beat 任务</th>
                <th>实际 Celery 任务</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.beatKey}>
                  <td>
                    <code className="scheduled-tasks__code">{row.beatKey}</code>
                  </td>
                  <td>{row.name}</td>
                  <td>
                    <code className="scheduled-tasks__code">{row.cronExpr}</code>
                  </td>
                  <td>
                    <code className="scheduled-tasks__code">{row.beatTask}</code>
                  </td>
                  <td>
                    <code className="scheduled-tasks__code">{row.targetTaskKey}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="ai-modal__actions">
        <button type="button" onClick={onClose}>
          关闭
        </button>
      </div>
    </div>
  )
}

function TaskTable({ items, onEdit }) {
  if (items.length === 0) {
    return <p className="scheduled-tasks__empty">暂无定时任务，点击「新增任务」创建。</p>
  }
  return (
    <div className="scheduled-tasks-table-wrapper stock-table-wrapper">
      <table className="scheduled-tasks-table stock-table">
        <thead>
          <tr>
            <th>任务名称</th>
            <th>cron</th>
            <th>Celery 任务名</th>
            <th>启用</th>
            <th>执行开始</th>
            <th>执行完成</th>
            <th>日志</th>
            <th className="stock-table__col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id}>
              <td>{row.name}</td>
              <td>
                <code className="scheduled-tasks__code">{row.cronExpr}</code>
              </td>
              <td>
                <code className="scheduled-tasks__code">{row.taskKey}</code>
              </td>
              <td>{row.enabled ? '是' : '否'}</td>
              <td>{formatDateTime(row.startedAt)}</td>
              <td>{formatDateTime(row.finishedAt)}</td>
              <td className="scheduled-tasks__log" title={row.log || ''}>
                {truncateLog(row.log)}
              </td>
              <td className="stock-table__col-actions">
                <button
                  type="button"
                  className="scheduled-tasks__edit-btn"
                  onClick={() => onEdit(row)}
                >
                  编辑
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 定时任务管理：列表展示与新增、修改 */
export default function ScheduledTasksLayout({ apiBase }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState('')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [taskKeyOptions, setTaskKeyOptions] = useState([])
  const [beatModalOpen, setBeatModalOpen] = useState(false)
  const [beatItems, setBeatItems] = useState([])
  const [beatLoading, setBeatLoading] = useState(false)
  const [beatError, setBeatError] = useState('')
  const [beatBrokerConfigured, setBeatBrokerConfigured] = useState(false)

  const loadList = useCallback(async () => {
    setErrorMsg('')
    const list = await fetchScheduledTasks(apiBase)
    setItems(list)
  }, [apiBase])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const list = await fetchScheduledTasks(apiBase)
        if (!cancelled) {
          setItems(list)
        }
      } catch (e) {
        if (!cancelled) {
          setErrorMsg(e instanceof Error ? e.message : '加载定时任务失败')
          setItems([])
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [apiBase])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const keys = await fetchScheduledTaskKeys(apiBase)
        if (!cancelled) {
          setTaskKeyOptions(keys)
        }
      } catch {
        if (!cancelled) {
          setTaskKeyOptions([])
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [apiBase])

  const openAdd = () => {
    setEditingId(null)
    setForm(emptyForm())
    setFormError('')
    setEditorOpen(true)
  }

  const openEdit = (row) => {
    setEditingId(row.id)
    setForm({
      name: row.name,
      cron_expr: row.cronExpr,
      task_key: row.taskKey,
      enabled: row.enabled,
    })
    setFormError('')
    setEditorOpen(true)
  }

  const closeEditor = () => {
    if (submitting) {
      return
    }
    setEditorOpen(false)
    setFormError('')
  }

  const onFieldChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async () => {
    const name = form.name.trim()
    const cron_expr = form.cron_expr.trim()
    const task_key = form.task_key.trim()
    if (!name || !cron_expr || !task_key) {
      setFormError('请填写任务名称、cron 表达式与 Celery 任务名')
      return
    }
    setSubmitting(true)
    setFormError('')
    try {
      const payload = {
        name,
        cron_expr,
        task_key,
        enabled: Boolean(form.enabled),
      }
      if (editingId == null) {
        const next = await addScheduledTasks(apiBase, [payload])
        setItems(next)
      } else {
        const next = await modifyScheduledTasks(apiBase, [{ id: editingId, ...payload }])
        setItems(next)
      }
      setEditorOpen(false)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSubmitting(false)
    }
  }

  const retry = () => {
    setLoading(true)
    void loadList()
      .catch((e) => {
        setErrorMsg(e instanceof Error ? e.message : '加载定时任务失败')
      })
      .finally(() => setLoading(false))
  }

  const loadBeatSchedule = useCallback(async () => {
    setBeatError('')
    setBeatLoading(true)
    try {
      const data = await fetchBeatSchedule(apiBase)
      setBeatBrokerConfigured(data.brokerConfigured)
      setBeatItems(data.items)
    } catch (e) {
      setBeatError(e instanceof Error ? e.message : '加载 Beat 调度失败')
      setBeatItems([])
      setBeatBrokerConfigured(false)
    } finally {
      setBeatLoading(false)
    }
  }, [apiBase])

  const openBeatSchedule = () => {
    setBeatModalOpen(true)
    void loadBeatSchedule()
  }

  const closeBeatSchedule = () => {
    setBeatModalOpen(false)
    setBeatError('')
  }

  return (
    <div className="scheduled-tasks">
      <header className="scheduled-tasks__header">
        <h1 className="scheduled-tasks__title">定时任务</h1>
        <p className="scheduled-tasks__subtitle">
          管理 Celery 定时任务配置；列表展示最近一次执行的日志与时间。
        </p>
      </header>

      <div className="scheduled-tasks__toolbar">
        <button type="button" className="stock-toolbar-add" onClick={openAdd}>
          新增任务
        </button>
        <button type="button" className="scheduled-tasks__query-btn" onClick={openBeatSchedule}>
          查看 Beat 调度
        </button>
      </div>

      {loading ? <p className="scheduled-tasks__status status-text">加载中...</p> : null}
      {!loading && errorMsg ? (
        <p className="scheduled-tasks__status status-text status-text--error">
          {errorMsg}
          <button type="button" className="earnings-lens__retry" onClick={retry}>
            重试
          </button>
        </p>
      ) : null}

      {!loading && !errorMsg ? <TaskTable items={items} onEdit={openEdit} /> : null}

      {editorOpen ? (
        <div className="ai-modal-mask" role="presentation" onClick={closeEditor}>
          <TaskEditorModal
            editingId={editingId}
            form={form}
            formError={formError}
            submitting={submitting}
            taskKeyOptions={taskKeyOptions}
            onFieldChange={onFieldChange}
            onSubmit={() => void handleSubmit()}
            onClose={closeEditor}
          />
        </div>
      ) : null}

      {beatModalOpen ? (
        <div className="ai-modal-mask" role="presentation" onClick={closeBeatSchedule}>
          <BeatScheduleModal
            loading={beatLoading}
            errorMsg={beatError}
            brokerConfigured={beatBrokerConfigured}
            items={beatItems}
            onClose={closeBeatSchedule}
            onRetry={() => void loadBeatSchedule()}
          />
        </div>
      ) : null}
    </div>
  )
}
