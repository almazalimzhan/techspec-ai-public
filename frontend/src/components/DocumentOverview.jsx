import { useState } from 'react'
import s from './DocumentOverview.module.css'

const PREVIEW_LIMIT = 720

export default function DocumentOverview({ session, t }) {
  const [expanded, setExpanded] = useState(false)

  if (!session) return null

  const preview = typeof session.preview === 'string' ? session.preview.trim() : ''
  const canExpand = preview.length > PREVIEW_LIMIT
  const shownPreview = expanded || !canExpand
    ? preview
    : `${preview.slice(0, PREVIEW_LIMIT).trimEnd()}...`

  const fieldLabels = t.docFieldLabels || {}
  const fields = Object.entries(fieldLabels)
    .map(([key, label]) => ({ key, label, value: session.key_fields?.[key] }))
    .filter(({ value }) => value && value !== 'null')

  return (
    <section className={s.card}>
      <div className={s.head}>
        <div>
          <div className={s.title}>{t.docOverviewTitle}</div>
          <div className={s.hint}>{t.docOverviewHint}</div>
        </div>

        <div className={s.meta}>
          <div className={s.metaPill}>
            <span className={s.metaLabel}>{t.docLangLabel}</span>
            <span className={s.metaValue}>{session.language}</span>
          </div>
          <div className={s.metaPill}>
            <span className={s.metaLabel}>{t.docChunkLabel}</span>
            <span className={s.metaValue}>{session.chunk_count}</span>
          </div>
        </div>
      </div>

      <div className={s.grid}>
        <div className={s.panel}>
          <div className={s.panelTitle}>{t.docFieldsTitle}</div>
          {fields.length ? (
            <dl className={s.fields}>
              {fields.map(({ key, label, value }) => (
                <div key={key} className={s.fieldItem}>
                  <dt className={s.fieldLabel}>{label}</dt>
                  <dd className={s.fieldValue}>{value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className={s.empty}>{t.docFieldsEmpty}</div>
          )}
        </div>

        <div className={s.panel}>
          <div className={s.panelHead}>
            <div className={s.panelTitle}>{t.docPreviewTitle}</div>
            {canExpand && (
              <button className={s.toggleBtn} onClick={() => setExpanded(open => !open)}>
                {expanded ? t.docPreviewLess : t.docPreviewMore}
              </button>
            )}
          </div>

          {preview ? (
            <pre className={s.preview}>{shownPreview}</pre>
          ) : (
            <div className={s.empty}>{t.docPreviewEmpty}</div>
          )}
        </div>
      </div>
    </section>
  )
}
