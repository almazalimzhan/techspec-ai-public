import { useRef, useState } from 'react'
import { T } from './i18n.js'
import { uploadPdf, getSummary, getJsonFields, getRisks, askQuestion } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import ActionCards from './components/ActionCards.jsx'
import DocumentOverview from './components/DocumentOverview.jsx'
import ResultBlock from './components/ResultBlock.jsx'
import QABlock from './components/QABlock.jsx'
import s from './App.module.css'

export default function App() {
  const [lang, setLang]           = useState('Русский')
  const [bin, setBin]             = useState('')
  const [session, setSession]     = useState(null)   // { session_id, filename, chunk_count, preview, key_fields, language }
  const [uploading, setUploading] = useState(false)
  const [uploadErr, setUploadErr] = useState('')

  const [result, setResult]       = useState(null)   // { type, content, context }
  const [actionLoading, setActionLoading] = useState(null)
  const [qaLoading, setQaLoading] = useState(false)
  const [error, setError]         = useState('')
  const uploadRequestRef = useRef(0)

  const t = T[lang]
  const binValid = /^\d{12}$/.test(bin)
  const availability = { hasSession: !!session, hasBin: binValid }

  // ── Language change resets session ──────────────────────────────────────
  function handleSetLang(l) {
    if (l === lang) return
    uploadRequestRef.current += 1
    setLang(l)
    setUploading(false)
    setSession(null)
    setResult(null)
    setError('')
    setUploadErr('')
  }

  function handleBinChange(value) {
    setBin(value)
    if (error) setError('')
  }

  function handleUploadError(message) {
    setUploadErr(message)
    setError('')
  }

  // ── Upload ───────────────────────────────────────────────────────────────
  async function handleUpload(file) {
    const uploadLang = lang
    const requestId = uploadRequestRef.current + 1
    uploadRequestRef.current = requestId

    setUploading(true)
    setUploadErr('')
    setError('')

    try {
      const data = await uploadPdf(file, uploadLang)
      if (uploadRequestRef.current !== requestId) return false

      setSession({ ...data, language: uploadLang })
      setResult(null)
      return true
    } catch (e) {
      if (uploadRequestRef.current !== requestId) return false
      setUploadErr(e.message)
      return false
    } finally {
      if (uploadRequestRef.current === requestId) {
        setUploading(false)
      }
    }
  }

  // ── Guard helper ─────────────────────────────────────────────────────────
  function guard(needBin = false) {
    if (!session) { setError(t.needPdf); return false }
    if (needBin && !binValid) { setError(t.needBin); return false }
    setError('')
    return true
  }

  // ── Action buttons ───────────────────────────────────────────────────────
  async function handleAction(type) {
    const needBin = type !== 'risk'
    if (!guard(needBin)) return

    setActionLoading(type)
    setError('')
    try {
      let data
      if (type === 'summary') data = await getSummary(session.session_id, bin, lang)
      else if (type === 'json') data = await getJsonFields(session.session_id, bin, lang)
      else data = await getRisks(session.session_id, bin, lang)
      setResult({ type, content: data.result, context: null })
      return true
    } catch (e) {
      setError(e.message)
      return false
    } finally {
      setActionLoading(null)
    }
  }

  // ── Q&A ──────────────────────────────────────────────────────────────────
  async function handleAsk(question) {
    if (!guard(false)) return false
    setQaLoading(true)
    setError('')
    try {
      const data = await askQuestion(session.session_id, question, bin, lang)
      setResult({ type: 'answer', content: data.answer, context: data.context })
      return true
    } catch (e) {
      setError(e.message)
      return false
    } finally {
      setQaLoading(false)
    }
  }

  return (
    <div className={s.shell}>
      <Sidebar
        lang={lang}
        setLang={handleSetLang}
        session={session}
        onUpload={handleUpload}
        onUploadError={handleUploadError}
        uploading={uploading}
        bin={bin}
        setBin={handleBinChange}
        t={t}
      />

      <div className={s.main}>
        <header className={s.topbar}>
          <div>
            <div className={s.tbTitle}>{t.pageTitle}</div>
            <div className={s.tbSub}>{t.pageSubtitle}</div>
          </div>
          {session && (
            <div className={s.tbMeta}>{session.chunk_count} {t.chunks}</div>
          )}
        </header>

        <div className={s.scroll}>

          {/* Upload error */}
          {uploadErr && <div className={`${s.alert} ${s.alertErr}`}>{uploadErr}</div>}

          {/* Action error */}
          {error && <div className={`${s.alert} ${s.alertWarn}`}>{error}</div>}

          {session && (
            <DocumentOverview key={session.session_id} session={session} t={t} />
          )}

          {/* Action cards */}
          <section>
            <div className={s.sectionTitle}>{t.sectionAnalysis}</div>
            <ActionCards
              onAction={handleAction}
              loading={actionLoading}
              availability={availability}
              t={t}
            />
          </section>

          {/* Result */}
          {result && (
            <ResultBlock
              type={result.type}
              content={result.content}
              context={result.context}
              t={t}
            />
          )}

          <div className={s.divider} />

          {/* Q&A */}
          <section>
            <div className={s.sectionTitle}>{t.sectionQA}</div>
            <QABlock
              onAsk={handleAsk}
              loading={qaLoading}
              disabled={!session}
              disabledReason={!session ? t.qaDisabledHint : ''}
              t={t}
            />
          </section>

        </div>
      </div>
    </div>
  )
}
