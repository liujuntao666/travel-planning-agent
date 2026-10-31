<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  clearDownloadBlobs,
  deleteFile,
  downloadFile,
  listFiles,
  uploadBatch,
  uploadLargeFile,
  type StoredFile,
} from '../api/files'

const props = defineProps<{ userId: number }>()
const emit = defineEmits<{ (event: 'close'): void }>()

const LARGE_THRESHOLD = 10 * 1024 * 1024

interface UploadTask {
  id: string
  title: string
  detail: string
  progress: number
  phase: string
  status: 'running' | 'done' | 'error'
  error: string
}

interface DownloadState {
  status: 'running' | 'paused' | 'done' | 'error'
  ratio: number | null
  received: number
  total: number
  error: string
}

const tasks = ref<UploadTask[]>([])
const files = ref<StoredFile[]>([])
const downloads = reactive<Record<number, DownloadState>>({})
const controllers = new Map<number, AbortController>()
const loading = ref(false)
const deleting = ref(0)
const notice = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)

let taskSeq = 0
function nextTaskId() {
  taskSeq += 1
  return `task-${Date.now()}-${taskSeq}`
}

function formatBytes(value: number) {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)))
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function formatTime(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

function errorText(err: unknown) {
  if (err && typeof err === 'object') {
    const body = (err as { body?: { message?: string } }).body
    if (body?.message) return body.message
    const message = (err as { message?: string }).message
    if (message) return message
  }
  return '操作失败'
}

async function refreshFiles() {
  loading.value = true
  try {
    files.value = await listFiles(props.userId)
  } catch (err) {
    notice.value = errorText(err)
  } finally {
    loading.value = false
  }
}

async function runLarge(file: File, task: UploadTask) {
  task.status = 'running'
  try {
    await uploadLargeFile(file, props.userId, {
      onPhase: (phase) => {
        task.phase = phase
      },
      onProgress: (ratio) => {
        task.progress = ratio
      },
    })
    task.status = 'done'
    task.progress = 1
    task.phase = '上传完成'
  } catch (err) {
    task.status = 'error'
    task.error = errorText(err)
  }
}

async function runBatch(batchFiles: File[], task: UploadTask) {
  task.status = 'running'
  task.phase = `批量上传 ${batchFiles.length} 个文件…`
  try {
    const result = await uploadBatch(batchFiles, props.userId, (ratio) => {
      task.progress = ratio
    })
    task.progress = 1
    task.status = result.failed ? 'error' : 'done'
    task.phase = `成功 ${result.success} 个，失败 ${result.failed} 个`
    const failedNames = result.items
      .filter((item) => !item.ok)
      .map((item) => `${item.name}（${item.error || '失败'}）`)
    if (failedNames.length) task.error = failedNames.join('；')
  } catch (err) {
    task.status = 'error'
    task.error = errorText(err)
  }
}

async function handleFiles(selected: FileList | File[]) {
  const list = Array.from(selected).filter((file) => file.size > 0)
  if (!list.length) return
  notice.value = ''

  const largeFiles = list.filter((file) => file.size >= LARGE_THRESHOLD)
  const smallFiles = list.filter((file) => file.size < LARGE_THRESHOLD)

  for (const file of largeFiles) {
    const task = reactive<UploadTask>({
      id: nextTaskId(),
      title: file.name,
      detail: `${formatBytes(file.size)} · 分片上传`,
      progress: 0,
      phase: '等待上传…',
      status: 'running',
      error: '',
    })
    tasks.value.unshift(task)
    void runLarge(file, task)
  }

  if (smallFiles.length) {
    const task = reactive<UploadTask>({
      id: nextTaskId(),
      title: smallFiles.length === 1 ? smallFiles[0].name : `${smallFiles.length} 个小文件`,
      detail: smallFiles.map((file) => file.name).join('、').slice(0, 80),
      progress: 0,
      phase: '等待上传…',
      status: 'running',
      error: '',
    })
    tasks.value.unshift(task)
    await runBatch(smallFiles, task)
  }

  await refreshFiles()
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files?.length) void handleFiles(input.files)
  input.value = ''
}

function onDrop(event: DragEvent) {
  dragActive.value = false
  if (event.dataTransfer?.files?.length) void handleFiles(event.dataTransfer.files)
}

async function toggleDownload(file: StoredFile) {
  const state = downloads[file.file_id]
  const running = controllers.get(file.file_id)

  if (state?.status === 'running' && running) {
    running.abort()
    return
  }

  const controller = new AbortController()
  controllers.set(file.file_id, controller)
  downloads[file.file_id] = {
    status: 'running',
    ratio: 0,
    received: 0,
    total: file.size,
    error: '',
  }
  const current = downloads[file.file_id]

  try {
    await downloadFile(file, {
      signal: controller.signal,
      onProgress: (ratio, received, total) => {
        current.ratio = ratio
        current.received = received
        current.total = total || file.size
      },
    })
    current.status = 'done'
    current.ratio = 1
    current.received = file.size
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === 'AbortError'
    current.status = aborted ? 'paused' : 'error'
    current.error = aborted ? '' : errorText(err)
  } finally {
    controllers.delete(file.file_id)
  }
}

async function removeFile(file: StoredFile) {
  if (!window.confirm(`确定删除「${file.name}」？删除后不可恢复。`)) return
  controllers.get(file.file_id)?.abort()
  deleting.value = file.file_id
  try {
    await deleteFile(file.file_id, props.userId)
    await clearDownloadBlobs(file.file_id)
    delete downloads[file.file_id]
    notice.value = `已删除「${file.name}」`
    await refreshFiles()
  } catch (err) {
    notice.value = errorText(err)
  } finally {
    deleting.value = 0
  }
}

function downloadLabel(file: StoredFile) {
  const state = downloads[file.file_id]
  if (!state) return '下载'
  if (state.status === 'running') return '暂停'
  if (state.status === 'paused') return '继续'
  if (state.status === 'error') return '重试'
  return '重新下载'
}

function downloadPercent(file: StoredFile) {
  const state = downloads[file.file_id]
  if (!state || state.ratio === null) return null
  return Math.round(state.ratio * 100)
}

function clearTasks() {
  tasks.value = []
}

onMounted(refreshFiles)
</script>

<template>
  <Teleport to="body">
    <div class="file-overlay" @click.self="emit('close')">
      <section class="file-drawer">
        <header class="drawer-head">
          <div>
            <h2>文件空间</h2>
            <p class="muted">大文件分片上传 · 小文件批量上传 · 断点续传下载</p>
          </div>
          <button type="button" class="icon-btn" aria-label="关闭" @click="emit('close')">×</button>
        </header>

        <div
          class="drop-zone"
          :class="{ active: dragActive }"
          @dragover.prevent="dragActive = true"
          @dragleave.prevent="dragActive = false"
          @drop.prevent="onDrop"
          @click="fileInput?.click()"
        >
          <strong>拖拽文件到这里，或点击选择</strong>
          <span class="muted">≥ 10MB 走分片上传，其余走批量上传</span>
          <input ref="fileInput" type="file" multiple hidden @change="onPick" />
        </div>

        <p v-if="notice" class="notice">{{ notice }}</p>

        <section v-if="tasks.length" class="block">
          <div class="block-head">
            <h3>上传任务</h3>
            <button type="button" class="text-btn" @click="clearTasks">清空</button>
          </div>
          <ul class="task-list">
            <li v-for="task in tasks" :key="task.id" class="task-item">
              <div class="task-top">
                <span class="task-name">{{ task.title }}</span>
                <span class="task-status" :class="task.status">
                  {{ task.status === 'done' ? '完成' : task.status === 'error' ? '失败' : `${Math.round(task.progress * 100)}%` }}
                </span>
              </div>
              <p class="task-detail muted">{{ task.detail }}</p>
              <div class="progress">
                <span :style="{ width: `${Math.min(100, task.progress * 100)}%` }" />
              </div>
              <p class="task-phase" :class="{ error: task.status === 'error' }">
                {{ task.status === 'error' ? task.error : task.phase }}
              </p>
            </li>
          </ul>
        </section>

        <section class="block">
          <div class="block-head">
            <h3>我的文件</h3>
            <button type="button" class="text-btn" :disabled="loading" @click="refreshFiles">
              {{ loading ? '刷新中…' : '刷新' }}
            </button>
          </div>
          <p v-if="!files.length && !loading" class="empty muted">还没有文件，上传后会出现在这里。</p>
          <ul class="file-list">
            <li v-for="file in files" :key="file.file_id" class="file-item">
              <div class="file-main">
                <span class="file-name" :title="file.name">{{ file.name }}</span>
                <span class="file-meta muted">
                  {{ formatBytes(file.size) }} · {{ formatTime(file.created_at) }}
                </span>
                <div v-if="downloads[file.file_id]" class="progress slim">
                  <span :style="{ width: `${downloadPercent(file) ?? 0}%` }" />
                </div>
                <span v-if="downloads[file.file_id]" class="file-meta muted">
                  <template v-if="downloads[file.file_id].status === 'running'">
                    {{ formatBytes(downloads[file.file_id].received) }} /
                    {{ formatBytes(downloads[file.file_id].total) }}
                    <template v-if="downloadPercent(file) !== null">· {{ downloadPercent(file) }}%</template>
                  </template>
                  <template v-else-if="downloads[file.file_id].status === 'paused'">已暂停，可继续</template>
                  <template v-else-if="downloads[file.file_id].status === 'error'">
                    {{ downloads[file.file_id].error }}
                  </template>
                  <template v-else>下载完成</template>
                </span>
              </div>
              <div class="file-actions">
                <button type="button" class="download-btn" @click="toggleDownload(file)">
                  {{ downloadLabel(file) }}
                </button>
                <button
                  type="button"
                  class="download-btn danger"
                  :disabled="deleting === file.file_id"
                  @click="removeFile(file)"
                >
                  {{ deleting === file.file_id ? '删除中…' : '删除' }}
                </button>
              </div>
            </li>
          </ul>
        </section>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.file-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(12, 24, 24, 0.42);
  display: flex;
  justify-content: flex-end;
  backdrop-filter: blur(2px);
}

.file-drawer {
  width: min(480px, 100%);
  height: 100%;
  background: var(--panel);
  border-left: 1px solid var(--line);
  box-shadow: -18px 0 40px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  overflow-y: auto;
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.drawer-head h2 {
  margin: 0 0 4px;
  font-size: 17px;
  color: var(--ink);
}

.drawer-head p {
  margin: 0;
  font-size: 12px;
}

.icon-btn {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--text-muted);
  width: 30px;
  height: 30px;
  border-radius: 9px;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 22px 16px;
  border: 1.5px dashed var(--line-strong);
  border-radius: 14px;
  background: #f8faf9;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.drop-zone.active {
  border-color: var(--accent);
  background: var(--accent-soft, #e9f7f3);
}

.drop-zone strong {
  font-size: 13.5px;
  color: var(--ink);
}

.drop-zone span {
  font-size: 12px;
}

.notice {
  margin: 0;
  padding: 8px 10px;
  border-radius: 9px;
  background: #fef3f2;
  color: #b42318;
  font-size: 12.5px;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.block-head h3 {
  margin: 0;
  font-size: 13px;
  color: var(--ink);
}

.text-btn {
  border: none;
  background: transparent;
  color: var(--accent-strong);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.task-list,
.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item,
.file-item {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  background: #fff;
}

.task-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.task-name,
.file-name {
  font-size: 13px;
  color: var(--ink);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-status {
  font-size: 11.5px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.task-status.done {
  color: #067647;
}

.task-status.error {
  color: #b42318;
}

.task-detail,
.task-phase {
  margin: 4px 0 0;
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-phase.error {
  color: #b42318;
}

.progress {
  margin-top: 8px;
  height: 6px;
  border-radius: 999px;
  background: #e5eeeb;
  overflow: hidden;
}

.progress.slim {
  height: 4px;
  margin-top: 6px;
}

.progress span {
  display: block;
  height: 100%;
  width: 0;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), #5eead4);
  transition: width 0.18s ease;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.file-meta {
  font-size: 11.5px;
}

.file-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.download-btn {
  flex-shrink: 0;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--ink);
  border-radius: 9px;
  padding: 6px 10px;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.download-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}

.download-btn.danger {
  color: #b42318;
  border-color: #fecdca;
}

.download-btn.danger:hover {
  background: #fef3f2;
  border-color: #f04438;
  color: #b42318;
}

.download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.empty {
  margin: 0;
  font-size: 12px;
}
</style>
