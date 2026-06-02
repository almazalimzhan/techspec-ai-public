import { useState } from 'react'
import s from './ResultBlock.module.css'

function download(content, filename, mime) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default function ResultBlock({ type, content, context, t }) {
  const [ctxOpen, setCtxOpen] = useState(false)

  if (!content) return null

  const titles = { summary: t.resultSummary, json: t.resultJson, risk: t.resultRisks, answer: t.resultAnswer }
  const title = titles[type] || type
  const isJson = type === 'json'

  return (
    <div className={s.card}>
      <div className={s.head}>
        <div className={s.title}>
          <div className={s.bar} />
          {title}
        </div>
        <div className={s.actions}>
          {type === 'summary' && (
            <button className={s.dlBtn} onClick={() => download(content, 'summary.txt', 'text/plain')}>
              {t.downloadTxt}
            </button>
          )}
          {type === 'json' && (
            <button className={s.dlBtn} onClick={() => download(content, 'fields.json', 'application/json')}>
              {t.downloadJson}
            </button>
          )}
        </div>
      </div>

      <div className={s.body}>
        {isJson ? (
          <pre className={s.jsonPre}>{content}</pre>
        ) : (
          <div className={s.text}>{content}</div>
        )}
      </div>

      {context && (
        <div className={s.ctx}>
          <button className={s.ctxToggle} onClick={() => setCtxOpen(o => !o)}>
            {t.resultCtx} {ctxOpen ? '▲' : '▼'}
          </button>
          {ctxOpen && <pre className={s.ctxBody}>{context}</pre>}
        </div>
      )}
    </div>
  )
}
