const PERIOD_LABELS: Record<string, string> = {
  MORNING: '上午',
  AFTERNOON: '下午',
  EVENING: '晚间',
  MEAL: '用餐',
}

const ITEM_TYPE_LABELS: Record<string, string> = {
  POI: '景点',
  RESTAURANT: '餐饮',
  TRANSPORT: '交通',
  FREE: '自由活动',
}

const TRANSPORT_LABELS: Record<string, string> = {
  FLIGHT: '飞机',
  HIGHSPEED: '高铁',
  TRAIN: '火车',
  CAR_RENTAL: '自驾',
  BUS: '大巴',
  SHIP: '轮渡',
}

export function periodLabel(period?: string | null): string {
  return (period && PERIOD_LABELS[period]) || period || '其他'
}

export function itemTypeLabel(type?: string | null): string {
  return (type && ITEM_TYPE_LABELS[type]) || type || '条目'
}

export function transportLabel(type?: string | null): string {
  return (type && TRANSPORT_LABELS[type]) || type || '交通'
}

export function money(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return `¥${Math.round(value).toLocaleString('zh-CN')}`
}

export function durationLabel(minutes?: number | null): string {
  if (!minutes || minutes <= 0) return ''
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h && m) return `${h}小时${m}分`
  if (h) return `${h}小时`
  return `${m}分钟`
}

export function weekday(dateText?: string | null): string {
  if (!dateText) return ''
  const date = new Date(`${dateText}T00:00:00`)
  if (Number.isNaN(date.getTime())) return ''
  return `周${'日一二三四五六'[date.getDay()]}`
}

export function timeText(value?: string | null): string {
  if (!value) return '--:--'
  return value.length > 5 ? value.slice(0, 5) : value
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function renderMarkdownLite(text: string): string {
  const escaped = escapeHtml(text)
  return escaped
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .split(/\n{2,}/)
    .map((block) => `<p>${block.replace(/\n/g, '<br />')}</p>`)
    .join('')
}

export function formatDateTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
