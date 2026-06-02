import { useRef } from 'react'
import { LANGS } from '../i18n.js'
import s from './Sidebar.module.css'

export default function Sidebar({ lang, setLang, session, onUpload, onUploadError, uploading, bin, setBin, t }) {
  const inputRef = useRef()
  const binValid = /^\d{12}$/.test(bin)

  function handleFile(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      onUploadError?.(t.invalidPdf)
      return
    }

    onUpload(file)
  }

  function handleDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file) return

    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      onUploadError?.(t.invalidPdf)
      return
    }

    onUpload(file)
  }

  function openFilePicker() {
    if (uploading) return
    if (inputRef.current) {
      inputRef.current.value = ''
      inputRef.current.click()
    }
  }

  return (
    <aside className={s.sidebar}>
      <div className={s.head}>
        <div className={s.brand}>
          <div className={s.brandMark}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round">
              <path d="M2 3h12M2 6.5h8M2 10h5M2 13h7"/>
            </svg>
          </div>
          <div>
            <div className={s.brandName}>{t.brand}</div>
            <div className={s.brandSub}>{t.brandSub}</div>
          </div>
        </div>
      </div>

      <div className={s.body}>
        {/* Language */}
        <div className={s.field}>
          <div className={s.fieldLabel}>{t.langLabel}</div>
          <div className={s.langSwitch}>
            {LANGS.map(l => (
              <button
                key={l}
                className={`${s.langBtn} ${lang === l ? s.langBtnOn : ''}`}
                onClick={() => setLang(l)}
                disabled={uploading}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        {/* Upload */}
        <div className={s.field}>
          <div className={s.fieldLabel}>{t.docLabel}</div>
          {session ? (
            <div className={s.filePill}>
              <span className={s.fileIcon}>📄</span>
              <div className={s.fileMeta}>
                <div className={s.fileName}>{session.filename}</div>
                <div className={s.fileCount}>{session.chunk_count} {t.chunks}</div>
                {uploading && <div className={s.fileStatus}>{t.statusProcessing}</div>}
              </div>
              <button
                className={s.fileChange}
                onClick={openFilePicker}
                title={t.replaceFile}
                disabled={uploading}
              >
                {t.replaceFile}
              </button>
            </div>
          ) : (
            <div
              className={`${s.dropZone} ${uploading ? s.dropLoading : ''}`}
              onClick={openFilePicker}
              onDrop={handleDrop}
              onDragOver={e => e.preventDefault()}
            >
              {uploading ? (
                <>
                  <div className={s.spinner} />
                  <div className={s.dropTitle}>{t.statusProcessing}</div>
                </>
              ) : (
                <>
                  <div className={s.dropIco}>📄</div>
                  <div className={s.dropTitle}>{t.uploadTitle}</div>
                  <div className={s.dropHint}>{t.uploadHint}</div>
                </>
              )}
            </div>
          )}
          <input ref={inputRef} type="file" accept=".pdf" style={{ display: 'none' }} onChange={handleFile} />
        </div>

        {/* BIN */}
        <div className={s.field}>
          <div className={s.fieldLabel}>{t.binLabel}</div>
          <input
            className={`${s.binInput} ${binValid ? s.binValid : ''}`}
            value={bin}
            onChange={e => setBin(e.target.value.replace(/\D/g, '').slice(0, 12))}
            placeholder={t.binPlaceholder}
            maxLength={12}
          />
          <div className={s.binHint}>{t.binHint}</div>
        </div>
      </div>

      <div className={s.foot}>
        <div
          className={`${s.statusBadge} ${
            uploading ? s.statusProcessing : session ? s.statusReady : s.statusWait
          }`}
        >
          <div className={s.statusDot} />
          {uploading
            ? t.statusProcessing
            : session
              ? `${t.statusReady} · ${session.chunk_count} ${t.chunks}`
              : t.statusWait}
        </div>
      </div>
    </aside>
  )
}
