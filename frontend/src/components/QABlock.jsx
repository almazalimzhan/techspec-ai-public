import { useState } from 'react'
import s from './QABlock.module.css'

export default function QABlock({ onAsk, loading, disabled, disabledReason, t }) {
  const [q, setQ] = useState('')

  async function submit() {
    const trimmed = q.trim()
    if (!trimmed || disabled || loading) return
    const ok = await onAsk(trimmed)
    if (ok) setQ('')
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit() }
  }

  return (
    <div className={s.wrap}>
      <div className={s.inputRow}>
        <input
          className={s.input}
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={handleKey}
          placeholder={t.qaPlaceholder}
          disabled={loading || disabled}
        />
        <button className={s.askBtn} onClick={() => void submit()} disabled={loading || disabled || !q.trim()}>
          {loading ? <div className={s.spinner} /> : t.askBtn}
        </button>
      </div>

      {disabledReason && (
        <div className={s.helper}>{disabledReason}</div>
      )}

      <div className={s.demoGrid}>
        {t.demoQs.map(dq => (
          <button
            key={dq}
            className={s.demoChip}
            onClick={() => setQ(dq)}
            disabled={disabled || loading}
          >
            {dq}
          </button>
        ))}
      </div>
    </div>
  )
}
