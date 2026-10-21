<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ExportRecord, Trip, VersionCompare, VersionInfo } from '../api/types'
import DayCard from './DayCard.vue'
import { formatDateTime, money, transportLabel } from '../utils/format'

const props = defineProps<{
  trip: Trip | null
  versions: VersionInfo[]
  exports: ExportRecord[]
  compare: VersionCompare | null
  busy: boolean
}>()

const emit = defineEmits<{
  (e: 'replan'): void
  (e: 'export', format: 'PDF' | 'LONG_IMAGE' | 'WECHAT_ARTICLE'): void
  (e: 'activate', versionId: number): void
  (e: 'compare', base: number, target: number): void
  (e: 'update-item', itemId: number, payload: { start_time: string; end_time: string }): void
  (e: 'delete-item', itemId: number): void
  (e: 'move-item', itemId: number, direction: 'up' | 'down'): void
  (
    e: 'add-item',
    payload: { day_index: number; ref_name: string; start_time: string; end_time: string },
  ): void
}>()

const baseId = ref<number | null>(null)
const targetId = ref<number | null>(null)

const budgetRows = computed(() => {
  const budget = props.trip?.budget
  if (!budget) return []
  return [
    { label: '交通', value: budget.transport },
    { label: '住宿', value: budget.lodging },
    { label: '门票', value: budget.tickets },
    { label: '餐饮', value: budget.meals },
  ]
})

const currentVersion = computed(() => props.trip?.version || null)
const errorIssues = computed(() => (props.trip?.issues || []).filter((i) => i.level === 'ERROR'))
const warnIssues = computed(() => (props.trip?.issues || []).filter((i) => i.level !== 'ERROR'))

const changeTypeLabels: Record<string, string> = {
  INIT: '首次生成',
  CHAT_ADJUST: '对话调整',
  MANUAL_EDIT: '手动编辑',
  AI_RERANK: 'AI 重排',
  ROLLBACK: '回退',
}

const formatLabels: Record<string, string> = {
  PDF: 'PDF 行程单',
  LONG_IMAGE: '长图',
  WECHAT_ARTICLE: '微信长文',
}

function runCompare() {
  if (baseId.value && targetId.value) emit('compare', baseId.value, targetId.value)
}

function exportStatus(record: ExportRecord): string {
  if (record.status === 2) return '成功'
  if (record.status === 3) return '失败'
  return '生成中'
}
</script>

<template>
  <section class="trip-panel">
    <div v-if="!trip" class="trip-empty">
      <div class="empty-illustration" />
      <h2>行程将在这里展开</h2>
      <p class="muted">
        生成后会显示每天的时间轴、住宿、交通与预算；
        <br />
        你可以直接修改时段、调整顺序、AI 重排或导出。
      </p>
    </div>

    <template v-else>
      <header class="trip-head">
        <div class="trip-title-row">
          <div>
            <h1>{{ trip.trip.title }}</h1>
            <p class="muted">
              {{ trip.trip.origin_city }} 出发 · {{ trip.trip.dest_cities }} ·
              {{ trip.trip.day_count }} 天 {{ trip.trip.night_count }} 晚 ·
              {{ trip.trip.people_count }} 人 · {{ trip.trip.style_name }}
            </p>
          </div>
          <div class="trip-actions">
            <button type="button" class="btn" :disabled="busy" @click="emit('replan')">AI 重排</button>
            <button type="button" class="btn primary" :disabled="busy" @click="emit('export', 'PDF')">导出 PDF</button>
            <button type="button" class="btn" :disabled="busy" @click="emit('export', 'LONG_IMAGE')">长图</button>
            <button type="button" class="btn" :disabled="busy" @click="emit('export', 'WECHAT_ARTICLE')">微信长文</button>
          </div>
        </div>
        <div class="trip-meta">
          <span class="meta-pill">{{ trip.trip_no }}</span>
          <span class="meta-pill" :class="{ good: trip.valid_flag, bad: !trip.valid_flag }">
            {{ trip.valid_flag ? '校验通过' : '存在排期问题' }}
          </span>
          <span class="meta-pill">当前 v{{ trip.version.version_no }} · {{ changeTypeLabels[trip.version.change_type] || trip.version.change_type }}</span>
          <span v-if="trip.version.change_summary" class="meta-pill subtle">{{ trip.version.change_summary }}</span>
        </div>
      </header>

      <div class="trip-scroll">
        <div
          v-if="trip.budget && trip.budget.over_budget"
          class="alert warn"
        >
          超出预算 {{ money(trip.budget.over_amount || 0) }}，
          {{ (trip.budget.suggestions || []).join('；') || '可尝试降低住宿档次或减少付费景点。' }}
        </div>

        <div v-if="errorIssues.length" class="alert error">
          {{ errorIssues.map((i) => i.message).join('；') }}
        </div>

        <section class="budget-card">
          <div class="budget-main">
            <span class="budget-label">预算合计</span>
            <strong class="budget-total">{{ money(trip.budget.total) }}</strong>
            <span class="muted">人均 {{ money(trip.budget.per_person) }}</span>
            <span v-if="trip.budget.budget_total" class="muted">
              · 目标 {{ money(trip.budget.budget_total) }}
            </span>
          </div>
          <div class="budget-grid">
            <div v-for="row in budgetRows" :key="row.label" class="budget-item">
              <span class="muted">{{ row.label }}</span>
              <strong>{{ money(row.value) }}</strong>
            </div>
          </div>
        </section>

        <section v-if="warnIssues.length" class="issue-list">
          <span v-for="(issue, idx) in warnIssues" :key="idx" class="issue-chip">
            D{{ issue.day_index || '-' }} · {{ issue.message }}
          </span>
        </section>

        <section v-if="trip.degrade_notes && trip.degrade_notes.length" class="degrade-box">
          <strong>信息待确认</strong>
          <ul>
            <li v-for="note in trip.degrade_notes" :key="note">{{ note }}</li>
          </ul>
        </section>

        <section v-if="trip.transports.length" class="transport-box">
          <h3>城际交通</h3>
          <div class="transport-list">
            <div v-for="leg in trip.transports" :key="leg.id || leg.leg_index" class="transport-item">
              <span class="badge">{{ transportLabel(leg.transport_type) }}</span>
              <span>{{ leg.from_city }} → {{ leg.to_city }}</span>
              <span class="muted">{{ leg.carrier || '' }} {{ leg.trip_no || '' }}</span>
              <span v-if="leg.dep_time" class="muted">
                {{ formatDateTime(leg.dep_time) }}
              </span>
              <span class="muted">{{ money(leg.price) }}</span>
            </div>
          </div>
        </section>

        <section class="days">
          <DayCard
            v-for="day in trip.days"
            :key="day.day_index"
            :day="day"
            :busy="busy"
            @update-item="(itemId, payload) => emit('update-item', itemId, payload)"
            @delete-item="(itemId) => emit('delete-item', itemId)"
            @move-item="(itemId, direction) => emit('move-item', itemId, direction)"
            @add-item="(payload) => emit('add-item', payload)"
          />
        </section>

        <section class="version-box">
          <div class="section-head">
            <h3>版本记录</h3>
            <div class="compare-controls">
              <select v-model.number="baseId" aria-label="基准版本">
                <option :value="null" disabled>基准版本</option>
                <option v-for="version in versions" :key="version.id" :value="version.id">
                  v{{ version.version_no }}
                </option>
              </select>
              <select v-model.number="targetId" aria-label="对比版本">
                <option :value="null" disabled>对比版本</option>
                <option v-for="version in versions" :key="version.id" :value="version.id">
                  v{{ version.version_no }}
                </option>
              </select>
              <button type="button" class="btn small" :disabled="!baseId || !targetId" @click="runCompare">
                对比
              </button>
            </div>
          </div>

          <div v-if="compare" class="compare-result">
            <p>
              v{{ compare.base.version_no }} → v{{ compare.target.version_no }}：
              费用变化 <strong>{{ compare.cost_delta >= 0 ? '+' : '' }}{{ money(compare.cost_delta) }}</strong>
            </p>
            <p v-if="compare.added.length" class="muted">新增：{{ compare.added.join('、') }}</p>
            <p v-if="compare.removed.length" class="muted">移除：{{ compare.removed.join('、') }}</p>
            <p v-if="!compare.added.length && !compare.removed.length" class="muted">条目一致，仅时段或费用调整。</p>
          </div>

          <ul class="version-list">
            <li
              v-for="version in versions"
              :key="version.id"
              class="version-item"
              :class="{ current: version.current_flag }"
            >
              <div class="version-main">
                <strong>v{{ version.version_no }}</strong>
                <span class="badge ghost">{{ changeTypeLabels[version.change_type] || version.change_type }}</span>
                <span class="version-summary">{{ version.change_summary }}</span>
              </div>
              <div class="version-side">
                <span class="muted">{{ money(version.total_cost) }}</span>
                <span v-if="version.current_flag && currentVersion" class="badge">当前</span>
                <button
                  v-else
                  type="button"
                  class="btn small"
                  :disabled="busy"
                  @click="emit('activate', version.id)"
                >
                  回退到此版本
                </button>
              </div>
            </li>
          </ul>
        </section>

        <section v-if="exports.length" class="export-box">
          <h3>导出记录</h3>
          <ul>
            <li v-for="record in exports" :key="record.id">
              <span>{{ formatLabels[record.format] || record.format }}</span>
              <span class="muted">{{ formatDateTime(record.created_at || null) }}</span>
              <span class="badge" :class="{ warn: record.status === 3 }">{{ exportStatus(record) }}</span>
              <span v-if="record.file_size" class="muted">{{ Math.round(record.file_size / 1024) }} KB</span>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.trip-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: var(--panel);
}

.trip-empty {
  margin: auto;
  text-align: center;
  padding: 40px 24px;
  max-width: 360px;
}

.empty-illustration {
  width: 96px;
  height: 96px;
  margin: 0 auto 18px;
  border-radius: 28px;
  background:
    radial-gradient(circle at 30% 30%, #99f6e4 0, transparent 55%),
    radial-gradient(circle at 72% 70%, #fde68a 0, transparent 50%),
    #eef7f5;
  border: 1px solid var(--line);
}

.trip-empty h2 {
  margin: 0 0 8px;
  font-size: 17px;
}

.trip-empty p {
  font-size: 13px;
  line-height: 1.7;
}

.trip-head {
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--line);
}

.trip-title-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
}

.trip-head h1 {
  margin: 0;
  font-size: 20px;
  color: var(--ink);
}

.trip-head p {
  margin: 5px 0 0;
  font-size: 12.5px;
}

.trip-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.btn {
  font: inherit;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--text);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}

.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.btn.primary:hover:not(:disabled) {
  background: var(--accent-strong);
  color: #fff;
}

.btn.small {
  font-size: 11px;
  padding: 4px 9px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trip-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.meta-pill {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--panel-alt);
  color: var(--text-muted);
  border: 1px solid var(--line);
}

.meta-pill.good {
  background: #ecfdf5;
  color: #047857;
  border-color: #a7f3d0;
}

.meta-pill.bad {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}

.meta-pill.subtle {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trip-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 22px 27px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.alert {
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12.5px;
  line-height: 1.6;
}

.alert.warn {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
}

.alert.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

.budget-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #f0fdfa, #ffffff 60%);
  display: flex;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
}

.budget-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 150px;
}

.budget-label {
  font-size: 11px;
  color: var(--text-muted);
}

.budget-total {
  font-size: 24px;
  color: var(--accent-strong);
  font-variant-numeric: tabular-nums;
}

.budget-main .muted {
  font-size: 11.5px;
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(64px, 1fr));
  gap: 12px;
  flex: 1;
}

.budget-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.budget-item strong {
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.issue-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.issue-chip {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
}

.degrade-box {
  font-size: 12px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  padding: 10px 14px;
  color: #9a3412;
}

.degrade-box ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.transport-box,
.version-box,
.export-box {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 16px;
  background: #fff;
}

.transport-box h3,
.version-box h3,
.export-box h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--ink);
}

.transport-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.transport-item {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}

.badge {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.badge.ghost {
  background: #f1f0ee;
  color: #6b7280;
}

.badge.warn {
  background: #fee2e2;
  color: #b91c1c;
}

.days {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.compare-controls {
  display: flex;
  gap: 6px;
  align-items: center;
}

.compare-controls select {
  font: inherit;
  font-size: 11px;
  padding: 3px 6px;
  border-radius: 6px;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--text);
}

.compare-result {
  font-size: 12px;
  background: var(--panel-alt);
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
}

.compare-result p {
  margin: 0 0 4px;
}

.version-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.version-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 8px 0;
  border-top: 1px dashed var(--line);
  font-size: 12px;
}

.version-item.current .version-main strong {
  color: var(--accent-strong);
}

.version-main {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
  flex-wrap: wrap;
}

.version-summary {
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}

.version-side {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.export-box ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.export-box li {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  padding: 6px 0;
  border-top: 1px dashed var(--line);
  flex-wrap: wrap;
}
</style>
