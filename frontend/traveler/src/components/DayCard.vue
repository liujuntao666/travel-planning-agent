<script setup lang="ts">
import { ref } from 'vue'
import type { TripDay, TripItem } from '../api/types'
import {
  durationLabel,
  itemTypeLabel,
  money,
  periodLabel,
  timeText,
  weekday,
} from '../utils/format'

const props = defineProps<{
  day: TripDay
  busy: boolean
}>()

const emit = defineEmits<{
  (e: 'update-item', itemId: number, payload: { start_time: string; end_time: string }): void
  (e: 'delete-item', itemId: number): void
  (e: 'move-item', itemId: number, direction: 'up' | 'down'): void
  (e: 'add-item', payload: { day_index: number; ref_name: string; start_time: string; end_time: string }): void
}>()

const editingId = ref<number | null>(null)
const editStart = ref('')
const editEnd = ref('')
const adding = ref(false)
const newName = ref('')
const newStart = ref('15:00')
const newEnd = ref('16:30')

function beginEdit(item: TripItem) {
  if (!item.id) return
  editingId.value = item.id
  editStart.value = timeText(item.start_time)
  editEnd.value = timeText(item.end_time)
}

function cancelEdit() {
  editingId.value = null
}

function saveEdit(item: TripItem) {
  if (!item.id) return
  emit('update-item', item.id, { start_time: editStart.value, end_time: editEnd.value })
  editingId.value = null
}

function submitAdd() {
  const name = newName.value.trim()
  if (!name) return
  emit('add-item', {
    day_index: props.day.day_index,
    ref_name: name,
    start_time: newStart.value,
    end_time: newEnd.value,
  })
  newName.value = ''
  adding.value = false
}

const poiCount = () => props.day.items.filter((i) => i.item_type === 'POI').length
</script>

<template>
  <article class="day-card">
    <header class="day-head">
      <div class="day-index">D{{ day.day_index }}</div>
      <div class="day-meta">
        <h3>{{ day.city }} · {{ day.theme }}</h3>
        <p class="muted">
          {{ day.day_date }} {{ weekday(day.day_date) }}
          <span v-if="day.weather" class="weather">
            · {{ day.weather.condition || '天气待确认' }}
            <template v-if="day.weather.high !== null && day.weather.high !== undefined">
              {{ day.weather.low }}~{{ day.weather.high }}℃
            </template>
          </span>
        </p>
      </div>
      <div class="day-tags">
        <span class="tag">{{ day.pace || '节奏适中' }}</span>
        <span class="tag">{{ poiCount() }} 个主点位</span>
      </div>
    </header>

    <p v-if="day.remark" class="day-remark">{{ day.remark }}</p>

    <ul class="timeline">
      <li v-for="item in day.items" :key="item.id || item.seq" class="timeline-item">
        <div class="time-col">
          <span class="time">{{ timeText(item.start_time) }}</span>
          <span class="time-sub">{{ timeText(item.end_time) }}</span>
        </div>
        <div class="dot" :class="item.item_type.toLowerCase()" />
        <div class="item-body">
          <div class="item-title">
            <strong>{{ item.ref_name }}</strong>
            <span class="badge" :class="item.item_type.toLowerCase()">{{ itemTypeLabel(item.item_type) }}</span>
            <span class="badge ghost">{{ periodLabel(item.period) }}</span>
            <span v-if="item.degrade_flag" class="badge warn">信息待确认</span>
            <span v-if="item.booking_required" class="badge info">
              需预约{{ item.booking_advance_days ? `（提前 ${item.booking_advance_days} 天）` : '' }}
            </span>
          </div>
          <p class="item-note">
            <span v-if="durationLabel(item.duration_min)">时长 {{ durationLabel(item.duration_min) }}</span>
            <span v-if="item.distance_km"> · 移动 {{ item.distance_km.toFixed(1) }} km</span>
            <span v-if="item.ticket_price"> · 门票 {{ money(item.ticket_price) }}</span>
            <span v-if="item.note"> · {{ item.note }}</span>
          </p>

          <div v-if="editingId === item.id" class="edit-row">
            <label>
              开始
              <input v-model="editStart" type="time" />
            </label>
            <label>
              结束
              <input v-model="editEnd" type="time" />
            </label>
            <button type="button" class="mini primary" :disabled="busy" @click="saveEdit(item)">保存</button>
            <button type="button" class="mini" @click="cancelEdit">取消</button>
          </div>
        </div>
        <div v-if="item.id" class="item-actions">
          <button type="button" class="mini" :disabled="busy" title="上移" @click="emit('move-item', item.id, 'up')">↑</button>
          <button type="button" class="mini" :disabled="busy" title="下移" @click="emit('move-item', item.id, 'down')">↓</button>
          <button type="button" class="mini" :disabled="busy" @click="beginEdit(item)">改时段</button>
          <button type="button" class="mini danger" :disabled="busy" @click="emit('delete-item', item.id)">删除</button>
        </div>
      </li>
    </ul>

    <div v-if="day.lodging" class="lodging">
      住宿：<strong>{{ day.lodging.hotel_name || '待确认' }}</strong>
      <span v-if="day.lodging.room_type"> · {{ day.lodging.room_type }}</span>
      <span v-if="day.lodging.price_per_night"> · {{ money(day.lodging.price_per_night) }}/晚</span>
      <span v-if="day.lodging.distance_to_scenic !== null && day.lodging.distance_to_scenic !== undefined">
        · 距景区 {{ day.lodging.distance_to_scenic }} km
      </span>
      <span v-if="day.lodging.degrade_flag" class="badge warn">待确认</span>
    </div>

    <div class="add-area">
      <button v-if="!adding" type="button" class="link-btn" :disabled="busy" @click="adding = true">
        + 添加条目
      </button>
      <div v-else class="edit-row">
        <label>
          名称
          <input v-model="newName" type="text" placeholder="如：古城自由活动" />
        </label>
        <label>
          开始
          <input v-model="newStart" type="time" />
        </label>
        <label>
          结束
          <input v-model="newEnd" type="time" />
        </label>
        <button type="button" class="mini primary" :disabled="busy || !newName.trim()" @click="submitAdd">添加</button>
        <button type="button" class="mini" @click="adding = false">取消</button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.day-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px;
  background: #fff;
}

.day-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.day-index {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--accent-soft);
  color: var(--accent-strong);
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.day-meta {
  flex: 1;
  min-width: 0;
}

.day-meta h3 {
  margin: 0;
  font-size: 15px;
  color: var(--ink);
}

.day-meta p {
  margin: 2px 0 0;
  font-size: 12px;
}

.day-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--panel-alt);
  color: var(--text-muted);
  border: 1px solid var(--line);
}

.day-remark {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  background: #faf9f6;
  border-radius: 8px;
  padding: 7px 10px;
}

.timeline {
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 0;
  border-top: 1px dashed var(--line);
}

.time-col {
  width: 44px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  font-variant-numeric: tabular-nums;
}

.time {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.time-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-top: 6px;
  background: var(--accent);
  flex-shrink: 0;
}

.dot.restaurant {
  background: #d97706;
}

.dot.transport {
  background: #2563eb;
}

.dot.free {
  background: #9ca3af;
}

.item-body {
  flex: 1;
  min-width: 0;
}

.item-title {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  font-size: 14px;
  color: var(--ink);
}

.badge {
  font-size: 10px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-strong);
  white-space: nowrap;
}

.badge.restaurant {
  background: #fef3c7;
  color: #92400e;
}

.badge.transport {
  background: #dbeafe;
  color: #1e40af;
}

.badge.free,
.badge.ghost {
  background: #f1f0ee;
  color: #6b7280;
}

.badge.warn {
  background: #ffedd5;
  color: #9a3412;
}

.badge.info {
  background: #e0f2fe;
  color: #075985;
}

.item-note {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0.55;
}

.timeline-item:hover .item-actions {
  opacity: 1;
}

.mini {
  font: inherit;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--text);
  cursor: pointer;
}

.mini:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}

.mini.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.mini.danger:hover:not(:disabled) {
  border-color: #dc2626;
  color: #dc2626;
}

.mini:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.edit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin-top: 8px;
}

.edit-row label {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
  color: var(--text-muted);
}

.edit-row input {
  font: inherit;
  font-size: 12px;
  padding: 4px 7px;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  width: 110px;
  color: var(--ink);
}

.lodging {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
  background: var(--panel-alt);
  border-radius: 8px;
  padding: 8px 10px;
}

.lodging strong {
  color: var(--ink);
}

.add-area {
  margin-top: 10px;
}

.link-btn {
  border: none;
  background: none;
  color: var(--accent-strong);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 0;
}
</style>
