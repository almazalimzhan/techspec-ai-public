const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 300000)

const UI_MESSAGES = {
  'Русский': {
    timeout: 'Сервер слишком долго отвечает. Попробуйте еще раз.',
    uploadError: 'Ошибка загрузки PDF',
    requestError: 'Ошибка запроса',
  },
  'Қазақша': {
    timeout: 'Сервер тым ұзақ жауап беруде. Қайталап көріңіз.',
    uploadError: 'PDF жүктеу қатесі',
    requestError: 'Сұрау қатесі',
  },
}

const KZ_BACKEND_ERRORS = {
  'Поддерживаются только PDF-файлы.': 'Тек PDF-файлдар қолдау табады.',
  'Файл пустой.': 'Файл бос.',
  'Файл слишком большой. Лимит: 25 MB.': 'Файл тым үлкен. Лимит: 25 MB.',
  'Сессия не найдена. Загрузите PDF заново.': 'Сессия табылмады. PDF файлын қайта жүктеңіз.',
  'Требуется БИН из 12 цифр.': '12 таңбалы БСН қажет.',
  'БИН должен содержать ровно 12 цифр.': 'БСН дәл 12 саннан тұруы керек.',
  'Вопрос не должен быть пустым.': 'Сұрақ бос болмауы керек.',
  'Слишком много запросов. Попробуйте позже.': 'Сұраулар тым көп. Кейінірек қайталап көріңіз.',
  'Внутренняя ошибка сервиса.': 'Қызметтің ішкі қатесі.',
  'Unauthorized.': 'Рұқсат жоқ.',
}

function getUiMessages(language) {
  return UI_MESSAGES[language] || UI_MESSAGES['Русский']
}

function translateDetail(detail, language) {
  if (typeof detail !== 'string') return ''
  if (language !== 'Қазақша') return detail
  if (detail.startsWith('Файл слишком большой. Лимит: ')) {
    return detail.replace('Файл слишком большой. Лимит: ', 'Файл тым үлкен. Лимит: ')
  }
  return KZ_BACKEND_ERRORS[detail] || detail
}

async function request(path, options, fallbackMessage, language) {
  const messages = getUiMessages(language)
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const res = await fetch(`${BASE}${path}`, { ...options, signal: controller.signal })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const detail = typeof err?.detail === 'string' ? translateDetail(err.detail, language) : ''
      throw new Error(detail || fallbackMessage)
    }
    return res.json()
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(messages.timeout)
    }
    if (error instanceof Error) {
      throw error
    }
    throw new Error(fallbackMessage)
  } finally {
    clearTimeout(timeoutId)
  }
}

async function requestText(path, fallbackMessage) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const res = await fetch(`${BASE}${path}`, { signal: controller.signal })
    if (!res.ok) {
      throw new Error(fallbackMessage)
    }
    return res.text()
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(fallbackMessage)
    }
    if (error instanceof Error) {
      throw error
    }
    throw new Error(fallbackMessage)
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function uploadPdf(file, language) {
  const messages = getUiMessages(language)
  const form = new FormData()
  form.append('file', file)
  form.append('language', language)
  return request('/upload', { method: 'POST', body: form }, messages.uploadError, language)
}

async function post(path, body, language) {
  const messages = getUiMessages(language)
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, `${messages.requestError} ${path}`, language)
}

export const getSummary    = (sessionId, bin, lang) => post('/summary',     { session_id: sessionId, customer_bin: bin, language: lang }, lang)
export const getJsonFields = (sessionId, bin, lang) => post('/json-fields', { session_id: sessionId, customer_bin: bin, language: lang }, lang)
export const getRisks      = (sessionId, bin, lang) => post('/risks',       { session_id: sessionId, customer_bin: bin, language: lang }, lang)
export const askQuestion   = (sessionId, question, bin, lang) =>
  post('/ask', { session_id: sessionId, question, customer_bin: bin, language: lang }, lang)

export const getHealth = (lang) => request('/health', { method: 'GET' }, 'Health check failed', lang)
export const getReady = (lang) => request('/ready', { method: 'GET' }, 'Readiness check failed', lang)
export const getLatestEval = (lang) => request('/eval/latest', { method: 'GET' }, 'Evaluation report check failed', lang)
export const getMetricsText = () => requestText('/metrics', 'Metrics check failed')
