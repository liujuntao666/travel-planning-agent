import { API_BASE } from './client'

export interface StoredFile {
  file_id: number
  file_no: string
  name: string
  size: number
  hash: string
  mime: string | null
  url: string
  created_at: string | null
}

interface InitResult {
  instant: boolean
  file_id?: number
  file_no?: string
  file_hash: string
  upload_id?: string
  chunk_size?: number
  total_chunks?: number
  uploaded?: number[]
}

interface UploadStatus {
  upload_id: string
  status: 'uploading' | 'merging' | 'done'
  file_name: string
  file_size: number
  chunk_size: number
  total_chunks: number
  uploaded: number[]
  missing_chunks: number[]
  file_id: number | null
}

const CHUNK_SIZE = 5 * 1024 * 1024
const PARALLEL = 3

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

async function sha256Hex(data: ArrayBuffer | string): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error('当前页面无法使用 Web Crypto，请用 http://127.0.0.1:5173 或 HTTPS 访问')
  }
  const input = typeof data === 'string' ? new TextEncoder().encode(data) : data
  return toHex(await crypto.subtle.digest('SHA-256', input))
}

export async function computeChunkHashes(
  file: File,
  chunkSize: number,
  onProgress?: (ratio: number) => void,
): Promise<{ hashes: string[]; fingerprint: string }> {
  const total = Math.ceil(file.size / chunkSize)
  const hashes: string[] = []
  for (let index = 0; index < total; index += 1) {
    const start = index * chunkSize
    const blob = file.slice(start, Math.min(file.size, start + chunkSize))
    hashes.push(await sha256Hex(await blob.arrayBuffer()))
    onProgress?.((index + 1) / total)
  }
  return { hashes, fingerprint: await sha256Hex(hashes.join('')) }
}

function chunkLength(index: number, size: number, chunkSize: number) {
  const start = index * chunkSize
  return Math.min(size, start + chunkSize) - start
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw { status: res.status, body }
  return body as T
}

function putChunk(
  uploadId: string,
  index: number,
  blob: Blob,
  hash: string,
  ownerId: number,
  onProgress: (loaded: number) => void,
): Promise<{ uploaded_count: number }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `${API_BASE}/files/uploads/${uploadId}/chunks/${index}?owner_id=${ownerId}`)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.setRequestHeader('X-Chunk-SHA256', hash)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded)
    }
    xhr.onload = () => {
      const body = (() => {
        try {
          return JSON.parse(xhr.responseText || '{}')
        } catch {
          return {}
        }
      })()
      if (xhr.status >= 200 && xhr.status < 300) resolve(body)
      else reject({ status: xhr.status, body })
    }
    xhr.onerror = () => reject({ status: 0, body: {} })
    xhr.send(blob)
  })
}

export interface LargeUploadHooks {
  onPhase?: (phase: string) => void
  onProgress?: (ratio: number) => void
}

export async function uploadLargeFile(
  file: File,
  ownerId: number,
  hooks: LargeUploadHooks = {},
): Promise<{ fileId: number }> {
  const chunkSize = CHUNK_SIZE
  hooks.onPhase?.('计算分片校验值…')
  const { hashes, fingerprint } = await computeChunkHashes(
    file,
    chunkSize,
    (ratio) => hooks.onPhase?.(`计算分片校验值… ${Math.round(ratio * 100)}%`),
  )

  hooks.onPhase?.('初始化上传会话…')
  const init = await requestJson<InitResult>('/files/uploads', {
    method: 'POST',
    body: JSON.stringify({
      file_name: file.name,
      file_size: file.size,
      file_hash: fingerprint,
      chunk_size: chunkSize,
      owner_id: ownerId,
    }),
  })
  if (init.instant && init.file_id) {
    hooks.onProgress?.(1)
    return { fileId: init.file_id }
  }

  const uploadId = init.upload_id!
  const totalChunks = init.total_chunks!
  const uploaded = new Set(init.uploaded || [])
  const loaded = new Map<number, number>()
  for (const index of uploaded) loaded.set(index, chunkLength(index, file.size, chunkSize))

  const render = () => {
    let bytes = 0
    for (const value of loaded.values()) bytes += value
    hooks.onProgress?.(Math.min(1, bytes / file.size))
  }
  render()

  const queue: number[] = []
  for (let index = 0; index < totalChunks; index += 1) {
    if (!uploaded.has(index)) queue.push(index)
  }

  async function uploadOne(index: number) {
    const start = index * chunkSize
    const blob = file.slice(start, Math.min(file.size, start + chunkSize))
    loaded.set(index, 0)
    render()

    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        await putChunk(uploadId, index, blob, hashes[index], ownerId, (sent) => {
          loaded.set(index, sent)
          render()
        })
        loaded.set(index, blob.size)
        render()
        return
      } catch (err) {
        loaded.set(index, 0)
        render()
        const body = (err as { body?: { code?: string } }).body
        if (body?.code === 'CHUNK_CHECKSUM_MISMATCH' && attempt < 2) continue
        if (attempt === 2) throw err
        await sleep(500 * 2 ** attempt)
      }
    }
  }

  hooks.onPhase?.('上传分片…')
  async function worker() {
    while (queue.length) await uploadOne(queue.shift()!)
  }
  await Promise.all(Array.from({ length: PARALLEL }, worker))

  hooks.onPhase?.('校验并合并文件…')
  for (let round = 0; round < 5; round += 1) {
    try {
      const result = await requestJson<{ file_id: number }>(
        `/files/uploads/${uploadId}/complete`,
        { method: 'POST', body: JSON.stringify({ file_hash: fingerprint, owner_id: ownerId }) },
      )
      hooks.onProgress?.(1)
      return { fileId: result.file_id }
    } catch (err) {
      const data = err as {
        status?: number
        body?: { code?: string; need_retry?: number[]; missing_chunks?: number[] }
      }
      if (data.status === 409 && data.body?.code === 'MERGING') {
        await sleep(800)
        continue
      }
      const retry = data.body?.need_retry || data.body?.missing_chunks
      if (retry?.length) {
        for (const index of retry) await uploadOne(index)
        continue
      }
      throw err
    }
  }
  throw new Error('多次补传后仍未通过文件校验')
}

export interface BatchResult {
  total: number
  success: number
  failed: number
  items: Array<{ name: string; ok: boolean; file_id?: number; error?: string }>
}

export function uploadBatch(
  files: File[],
  ownerId: number,
  onProgress: (ratio: number) => void,
): Promise<BatchResult> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('owner_id', String(ownerId))
    for (const file of files) form.append('files', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/files/batch`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      const body = (() => {
        try {
          return JSON.parse(xhr.responseText || '{}')
        } catch {
          return {}
        }
      })()
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as BatchResult)
      else reject({ status: xhr.status, body })
    }
    xhr.onerror = () => reject({ status: 0, body: {} })
    xhr.send(form)
  })
}

export function listFiles(ownerId: number): Promise<StoredFile[]> {
  return requestJson<StoredFile[]>(`/files?owner_id=${ownerId}`)
}

export function deleteFile(fileId: number, ownerId: number): Promise<{ file_id: number; deleted: boolean }> {
  return requestJson(`/files/${fileId}?owner_id=${ownerId}`, { method: 'DELETE' })
}

export async function uploadStatus(uploadId: string, ownerId: number): Promise<UploadStatus> {
  return requestJson<UploadStatus>(`/files/uploads/${uploadId}?owner_id=${ownerId}`)
}

/* ---------------------------------------------------------------- 下载断点续传 */

const DB_NAME = 'traveler-file-downloads'
const STORE = 'chunks'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function idbRequest<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function saveDownloadBlob(fileId: number, seq: number, blob: Blob) {
  const db = await openDb()
  try {
    const tx = db.transaction(STORE, 'readwrite')
    await idbRequest(tx.objectStore(STORE).put(blob, `${fileId}:${seq}`))
  } finally {
    db.close()
  }
}

async function loadDownloadBlobs(fileId: number): Promise<Blob[]> {
  const db = await openDb()
  try {
    const tx = db.transaction(STORE, 'readonly')
    const store = tx.objectStore(STORE)
    const [keys, values] = await Promise.all([
      idbRequest(store.getAllKeys()) as Promise<string[]>,
      idbRequest(store.getAll()) as Promise<Blob[]>,
    ])
    return keys
      .map((key, index) => ({ key, blob: values[index] }))
      .filter((item) => item.key.startsWith(`${fileId}:`))
      .sort((a, b) => Number(a.key.split(':')[1]) - Number(b.key.split(':')[1]))
      .map((item) => item.blob)
  } finally {
    db.close()
  }
}

export async function clearDownloadBlobs(fileId: number) {
  const db = await openDb()
  try {
    const keys = await idbRequest(
      db.transaction(STORE, 'readonly').objectStore(STORE).getAllKeys(),
    ) as string[]
    const mine = keys.filter((key) => key.startsWith(`${fileId}:`))
    if (!mine.length) return
    const tx = db.transaction(STORE, 'readwrite')
    const store = tx.objectStore(STORE)
    for (const key of mine) store.delete(key)
    await idbRequest(tx.objectStore(STORE).count())
  } finally {
    db.close()
  }
}

export interface DownloadHooks {
  onProgress?: (ratio: number | null, received: number, total: number) => void
  signal?: AbortSignal
}

export async function downloadFile(
  file: StoredFile,
  hooks: DownloadHooks = {},
): Promise<void> {
  let existing = await loadDownloadBlobs(file.file_id)
  let offset = existing.reduce((sum, blob) => sum + blob.size, 0)

  if (existing.length && offset >= file.size) {
    await clearDownloadBlobs(file.file_id)
    existing = []
    offset = 0
  }

  const headers: Record<string, string> = {}
  if (offset > 0) {
    headers.Range = `bytes=${offset}-`
    headers['If-Range'] = `"${file.hash}"`
  }

  const res = await fetch(`${API_BASE}/files/${file.file_id}`, { headers, signal: hooks.signal })

  if (res.status === 416) {
    await clearDownloadBlobs(file.file_id)
    return downloadFile(file, hooks)
  }
  if (res.status === 304) return

  let total = file.size
  if (res.status === 200 && offset > 0) {
    // 文件已变化，服务端返回全量，必须丢弃旧的续传数据
    await clearDownloadBlobs(file.file_id)
    existing = []
    offset = 0
  }

  const length = Number(res.headers.get('Content-Length') || 0)
  if (length) total = offset + length

  const reader = res.body?.getReader()
  if (!reader) throw new Error('浏览器不支持流式下载')

  let received = offset
  let seq = existing.length
  hooks.onProgress?.(total ? received / total : null, received, total)

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    if (!value) continue
    const blob = new Blob([value])
    await saveDownloadBlob(file.file_id, seq, blob)
    seq += 1
    existing.push(blob)
    received += blob.size
    hooks.onProgress?.(total ? received / total : null, received, total)
  }

  const merged = new Blob(existing, { type: file.mime || 'application/octet-stream' })
  const url = URL.createObjectURL(merged)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = file.name
  anchor.click()
  URL.revokeObjectURL(url)
  await clearDownloadBlobs(file.file_id)
}
