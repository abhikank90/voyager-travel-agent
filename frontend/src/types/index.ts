export interface TravelIntent {
  destination: string
  origin?: string
  budget_usd: number
  duration_days?: number
  travel_month?: string
  travel_year?: number
  interests: string[]
  group_size: number
  accommodation_preference?: string
  flexibility: string
  raw_query: string
}

export interface Flight {
  price_usd: number
  airline: string
  departure: string
  arrival: string
  stops: number
  duration: string
}

export interface Hotel {
  name: string
  price_per_night_usd: number
  total_usd: number
  rating: number
  amenities: string[]
  location: string
}

export interface Experience {
  name: string
  description: string
  cost_usd: number
  category: string
  best_time_of_day: string
}

export interface Weather {
  avg_temp_c: number
  avg_temp_f: number
  precipitation_mm?: number
  sunshine_hours?: number
  sea_temp_c?: number
  summary: string
  source: string
}

export interface BudgetBreakdown {
  flights_usd: number
  hotel_usd: number
  activities_usd: number
  food_usd: number
  misc_usd: number
  total_usd: number
  budget_usd: number
  is_within_budget: boolean
  overage_usd: number
  savings_usd: number
}

export interface ItineraryDay {
  day_number: number
  date: string
  theme: string
  morning: string
  afternoon: string
  evening: string
  meals: string[]
  estimated_cost_usd: number
  tips: string[]
}

export interface Itinerary {
  summary: string
  highlights: string[]
  days: ItineraryDay[]
  packing_list: string[]
  booking_checklist: string[]
  local_phrases: { phrase: string; pronunciation: string; meaning: string }[]
  total_cost_usd: number
}

export type AgentStatus = 'pending' | 'running' | 'done' | 'error'

export interface AgentUpdate {
  type: 'agent_update' | 'status' | 'complete' | 'error'
  agent: string
  message: string
  data?: Record<string, unknown>
}

export interface TravelState {
  intent?: TravelIntent
  flights?: Flight[]
  selected_flight?: Flight
  hotels?: Hotel[]
  selected_hotel?: Hotel
  experiences?: Experience[]
  weather?: Weather
  budget_breakdown?: BudgetBreakdown
  itinerary?: Itinerary
  status?: string
}

// ========== Collaborative Multi-Agent Types ==========

export type MessageType = 'insight' | 'constraint' | 'question' | 'proposal' | 'conflict'

export interface CollaborationMessage {
  from_agent: string
  to_agent: string
  message_type: MessageType
  content: string
  data?: Record<string, any>
  round: number
}

export interface Conflict {
  type: string
  agents: string[]
  description: string
  severity: 'low' | 'medium' | 'high'
}

export interface Synergy {
  type: string
  agents: string[]
  description: string
  benefit: string
}

export interface DayPlan {
  day: number
  date: string
  morning: string
  afternoon: string
  evening: string
  meals: {
    breakfast: string
    lunch: string
    dinner: string
  }
  notes?: string
}

export type TripStyle = 'budget' | 'balanced' | 'premium'

export interface TripOption {
  option_id: number
  style: TripStyle
  title: string
  description: string
  total_cost_usd: number

  // Selected items
  flight: Flight
  hotel: Hotel
  experiences: Experience[]

  // Itinerary
  itinerary: {
    num_days: number
    destination: string
    style: TripStyle
    total_cost: number
    breakdown: {
      flight: number
      hotel: number
      experiences: number
      food: number
      misc: number
    }
  }
  day_by_day: DayPlan[]

  // Booking URLs
  flight_booking_url?: string
  hotel_booking_url?: string
  experience_booking_urls: string[]

  // Analysis
  highlights: string[]
  trade_offs: string[]
}

export interface CollaborativeAgentUpdate extends Omit<AgentUpdate, 'type'> {
  type: 'agent_update' | 'collaboration' | 'options_ready' | 'status' | 'error'
  collaboration_messages?: CollaborationMessage[]
  trip_options?: TripOption[]
  session_id?: string
}

export interface CollaborativeTravelState extends TravelState {
  collaboration_round?: number
  agent_messages?: CollaborationMessage[]
  conflicts?: Conflict[]
  synergies?: Synergy[]
  trip_options?: TripOption[]
  selected_option_id?: number
  refinement_history?: Array<{
    base_option_id: number
    query: string
    timestamp: string
  }>
}
