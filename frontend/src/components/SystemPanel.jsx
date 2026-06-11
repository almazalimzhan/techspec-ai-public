import { useCallback, useEffect, useMemo, useState } from 'react'
import { getHealth, getLatestEval, getMetricsText, getReady } from '../api.js'
import s from './SystemPanel.module.css'

function formatPercent(value) {
  if (typeof value !== 'number') return '—'
  return `${Math.round(value * 100)}%`
}

function formatSeconds(value) {
  if (typeof value !== 'number') return '—'
  if (value < 10) return `${value.toFixed(2)}s`
  return `${Math.round(value)}s`
}

function formatUptime(seconds) {
  if (typeof seconds !== 'number') return '—'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function parseMetrics(text) {
  const lines = text.split('\n')
  let uptimeSeconds = null
  let requestCount = 0

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue

    const [nameAndLabels, rawValue] = trimmed.split(/\s+/)
    const value = Number(rawValue)
    if (!Number.isFinite(value)) continue

    if (nameAndLabels === 'techspec_app_uptime_seconds') {
      uptimeSeconds = value
    }
    if (nameAndLabels.startsWith('techspec_http_requests_total')) {
      requestCount += value
    }
  }

  return { uptimeSeconds, requestCount }
}

function stateFromValue(value) {
  if (!value) return 'missing'
  return value === 'ok' ? 'ok' : 'warn'
}

function StatusItem({ label, value, state }) {
  return (
    <div className={`${s.statusItem} ${s[state] || s.missing}`}>
      <span className={s.statusDot} />
      <div>
        <div className={s.statusLabel}>{label}</div>
        <div className={s.statusValue}>{value || '—'}</div>
      </div>
    </div>
  )
}

function MetricItem({ label, value }) {
  return (
    <div className={s.metricItem}>
      <div className={s.metricLabel}>{label}</div>
      <div className={s.metricValue}>{value}</div>
    </div>
  )
}

export default function SystemPanel({ lang, t }) {
  const [health, setHealth] = useState(null)
  const [ready, setReady] = useState(null)
  const [evalReport, setEvalReport] = useState(null)
  const [metrics, setMetrics] = useState({ uptimeSeconds: null, requestCount: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const [healthData, readyData, evalData, metricsText] = await Promise.all([
        getHealth(lang),
        getReady(lang),
        getLatestEval(lang),
        getMetricsText(),
      ])

      setHealth(healthData)
      setReady(readyData)
      setEvalReport(evalData)
      setMetrics(parseMetrics(metricsText))
    } catch (err) {
      setError(err instanceof Error ? err.message : t.systemStatusError)
    } finally {
      setLoading(false)
    }
  }, [lang, t.systemStatusError])

  useEffect(() => {
    refresh()
  }, [refresh])

  const summary = evalReport?.status === 'ready' ? evalReport.report?.summary : null
  const evalStatus = evalReport?.status === 'ready'
    ? `${summary?.passed ?? 0}/${summary?.cases ?? 0}`
    : t.systemEvalMissing

  const statusItems = useMemo(() => [
    {
      label: t.systemBackend,
      value: health?.status === 'ok' ? t.systemStatusOk : health?.status,
      state: health?.status === 'ok' ? 'ok' : 'missing',
    },
    {
      label: t.systemLlm,
      value: ready?.llm === 'ok' ? t.systemStatusOk : ready?.llm,
      state: stateFromValue(ready?.llm),
    },
    {
      label: t.systemEmbeddings,
      value: ready?.embeddings === 'ok' ? t.systemStatusOk : ready?.embeddings,
      state: stateFromValue(ready?.embeddings),
    },
    {
      label: t.systemQdrant,
      value: ready?.qdrant === 'ok' ? t.systemStatusOk : ready?.qdrant,
      state: stateFromValue(ready?.qdrant),
    },
  ], [health, ready, t])

  return (
    <section className={s.card}>
      <div className={s.head}>
        <div>
          <div className={s.title}>{t.sectionSystem}</div>
          <div className={s.hint}>{t.systemHint}</div>
        </div>
        <button className={s.refreshBtn} onClick={refresh} disabled={loading}>
          {loading ? t.systemRefreshing : t.systemRefresh}
        </button>
      </div>

      {error && <div className={s.error}>{error}</div>}

      <div className={s.statusGrid}>
        {statusItems.map(item => (
          <StatusItem key={item.label} {...item} />
        ))}
      </div>

      <div className={s.metricGrid}>
        <MetricItem label={t.systemVector} value={ready?.vector_backend || '—'} />
        <MetricItem label={t.systemUptime} value={formatUptime(metrics.uptimeSeconds)} />
        <MetricItem label={t.systemRequests} value={String(metrics.requestCount || 0)} />
        <MetricItem label={t.systemEval} value={evalStatus} />
        <MetricItem label={t.systemPassRate} value={formatPercent(summary?.pass_rate)} />
        <MetricItem label={t.systemAnswerRecall} value={formatPercent(summary?.avg_answer_recall)} />
        <MetricItem label={t.systemContextRecall} value={formatPercent(summary?.avg_context_recall)} />
        <MetricItem label={t.systemLatency} value={formatSeconds(summary?.avg_latency_seconds)} />
      </div>

      <div className={s.links}>
        <span>{t.systemEndpoints}</span>
        <a href="/ready" target="_blank" rel="noreferrer">/ready</a>
        <a href="/metrics" target="_blank" rel="noreferrer">/metrics</a>
        <a href="/eval/latest" target="_blank" rel="noreferrer">/eval/latest</a>
      </div>
    </section>
  )
}
