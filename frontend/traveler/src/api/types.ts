export interface User {
  id: number
  open_id: string
  nickname: string | null
  avatar_url?: string | null
  source?: string
  status?: number
}

export interface ConversationSummary {
  id: number
  title: string | null
  last_intent: string | null
  current_trip_id: number | null
  message_count: number | null
  last_message_at: string | null
}

export interface Message {
  id: number
  seq: number
  role: 'USER' | 'ASSISTANT' | string
  content: string
  content_type: string
  intent: string | null
  stream_flag: number
  created_at: string | null
}

export interface SlotInfo {
  value: string | null
  label: string
  required: boolean
  filled: boolean
  confidence: number | null
  ask_count: number
}

export interface ConversationDetail {
  id: number
  user_id: number
  title: string | null
  last_intent: string | null
  status: number
  current_trip_id: number | null
  message_count: number
  messages: Message[]
  slots: Record<string, SlotInfo>
  missing_slots: string[]
  trip: Trip | null
}

export type ItemType = 'POI' | 'RESTAURANT' | 'TRANSPORT' | 'FREE'
export type Period = 'MORNING' | 'AFTERNOON' | 'EVENING' | 'MEAL'

export interface TripItem {
  id?: number
  trip_day_id?: number
  seq: number
  period: Period | string
  item_type: ItemType | string
  ref_id?: number | null
  ref_name: string
  start_time?: string | null
  end_time?: string | null
  duration_min?: number | null
  distance_km?: number | null
  travel_min?: number | null
  ticket_price?: number | null
  booking_required?: number | null
  booking_advance_days?: number | null
  degrade_flag?: number | null
  note?: string | null
}

export interface Lodging {
  id?: number
  hotel_id?: number | null
  hotel_name?: string | null
  room_type?: string | null
  check_in?: string | null
  check_out?: string | null
  nights?: number | null
  price_per_night?: number | null
  total_price?: number | null
  rooms?: number | null
  distance_to_scenic?: number | null
  score?: number | null
  data_source?: string | null
  degrade_flag?: number | null
}

export interface WeatherDay {
  date?: string
  condition?: string
  high?: number | null
  low?: number | null
  wind?: string | null
  data_source?: string | null
  degrade_flag?: number | null
}

export interface TripDay {
  id?: number
  day_index: number
  day_date: string
  city: string
  theme: string
  pace?: string | null
  remark?: string | null
  weather?: WeatherDay | null
  items: TripItem[]
  lodging?: Lodging | null
}

export interface TransportLeg {
  id?: number
  leg_index: number
  transport_type: string
  carrier?: string | null
  trip_no?: string | null
  from_city?: string | null
  to_city?: string | null
  dep_station?: string | null
  arr_station?: string | null
  dep_time?: string | null
  arr_time?: string | null
  duration_min?: number | null
  price?: number | null
  transfer_desc?: string | null
  degrade_flag?: number | null
}

export interface Budget {
  total: number
  per_person: number
  transport: number
  lodging: number
  tickets: number
  meals: number
  budget_total?: number | null
  over_budget?: boolean
  over_amount?: number
  status?: string
  suggestions?: string[]
}

export interface Issue {
  level: 'ERROR' | 'WARN' | string
  day_index?: number | null
  type: string
  message: string
}

export interface VersionInfo {
  id: number
  version_no: number
  change_type: string
  change_summary: string
  total_cost: number | null
  current_flag: number
  valid_flag: number
  created_at: string | null
  base_version_id?: number | null
}

export interface TripOverview {
  title: string
  origin_city: string
  dest_cities: string
  day_count: number
  night_count: number
  people_count: number
  budget_total?: number | null
  budget_level?: string | null
  style_code: string
  style_name: string
  transport_mode?: string | null
  taboos?: string | null
  start_date: string
}

export interface Trip {
  id: number
  trip_no: string
  status?: number
  conversation_id?: number | null
  trip: TripOverview
  days: TripDay[]
  transports: TransportLeg[]
  budget: Budget
  issues: Issue[]
  valid_flag: boolean
  degrade_notes?: string[]
  version: VersionInfo
}

export interface VersionCompare {
  base: { id: number; version_no: number; total_cost: number }
  target: { id: number; version_no: number; total_cost: number }
  added: string[]
  removed: string[]
  cost_delta: number
  summary: string
}

export interface ToolCallInfo {
  call_id: string
  tool_type: string
  status: string
  degrade: boolean
  result_count: number
  cost_ms: number
  data_source?: string | null
  error_msg?: string | null
}

export interface ChatResult {
  conversation_id: number
  intent: string
  reply: string
  slots: Record<string, string>
  missing_slots: string[]
  trip: Trip | null
  tool_calls: ToolCallInfo[]
  degraded: string[]
  trace_id: string | null
  latency_ms: number
  user_message_id: number | null
  assistant_message_id: number | null
}

export interface ExportRecord {
  id: number
  export_no: string
  format: string
  format_label?: string
  file_url: string | null
  file_size?: number | null
  page_count?: number | null
  degrade_notice_count?: number | null
  status: number
  fail_reason?: string | null
  created_at?: string | null
}

export interface StyleOption {
  style_code: string
  style_name: string
  min_poi_per_day?: number
  max_poi_per_day?: number
  pace?: string
  description?: string | null
}

export interface PoiOption {
  id: number
  name: string
  city: string
  category?: string | null
  ticket_price?: number
  suggest_duration_min?: number | null
}

export type StreamHandler = (event: string, data: Record<string, unknown>) => void
