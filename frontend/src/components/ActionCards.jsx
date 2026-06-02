import s from './ActionCards.module.css'

const CARDS = [
  { key: 'summary', ico: '📝', colorClass: 'blue', requiresBin: true },
  { key: 'json',    ico: '{ }', colorClass: 'green', mono: true, requiresBin: true },
  { key: 'risk',    ico: '⚠',  colorClass: 'amber', requiresBin: false },
]

export default function ActionCards({ onAction, loading, availability, t }) {
  return (
    <div className={s.grid}>
      {CARDS.map(({ key, ico, colorClass, mono, requiresBin }) => {
        const blockedByPdf = !availability?.hasSession
        const blockedByBin = requiresBin && !availability?.hasBin
        const disabled = !!loading || blockedByPdf || blockedByBin
        const helperText = blockedByPdf
          ? t.cardNeedPdf
          : blockedByBin
            ? t.cardNeedBin
            : t.cardReady

        return (
          <button
            key={key}
            className={`${s.card} ${loading === key ? s.cardLoading : ''} ${disabled && helperText !== t.cardReady ? s.cardBlocked : ''}`}
            onClick={() => onAction(key)}
            disabled={disabled}
          >
            <div className={`${s.ico} ${s['ico_' + colorClass]}`}>
              {loading === key
                ? <div className={s.spinner} />
                : <span style={mono ? { fontFamily: 'var(--font-mono)', fontSize: '13px' } : {}}>{ico}</span>
              }
            </div>
            <div className={s.text}>
              <div className={s.label}>
                {key === 'summary' ? t.summaryBtn : key === 'json' ? t.jsonBtn : t.riskBtn}
              </div>
              <div className={s.desc}>
                {key === 'summary' ? t.summaryDesc : key === 'json' ? t.jsonDesc : t.riskDesc}
              </div>
              <div className={`${s.meta} ${helperText === t.cardReady ? s.metaReady : s.metaMuted}`}>
                {loading === key ? t.loading : helperText}
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
