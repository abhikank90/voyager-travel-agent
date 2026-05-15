import { useState, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, MapPin, Plane } from 'lucide-react'
import { AgentUpdate, AgentStatus, BudgetBreakdown, Itinerary } from '../types'
import { useWebSocket } from '../hooks/useWebSocket'
import { AgentStatusPanel } from './AgentStatusPanel'
import { BudgetTracker } from './BudgetTracker'
import { ItineraryCard } from './ItineraryCard'

const AGENT_STEPS = [
  { id: 'personalisation', label: 'Loading your profile' },
  { id: 'intent_parser', label: 'Understanding your request' },
  { id: 'research_fan_out', label: 'Researching flights & hotels' },
  { id: 'budget_guardrail', label: 'Checking budget' },
  { id: 'itinerary_builder', label: 'Building itinerary' },
]

const EXAMPLE_QUERIES = [
  "I want a vacation in Greece under $2000 with good beaches and local food around summer 2026",
  "Plan a 10-day trip to Japan under $3500 in March 2027, interested in temples and street food",
  "Weekend trip to Paris under $1500, romantic, great restaurants, art museums",
]

export function ChatInterface() {
  const [query, setQuery] = useState('')
  const [planning, setPlanning] = useState(false)
  const [agentSteps, setAgentSteps] = useState<
    { id: string; label: string; status: AgentStatus; message?: string }[]
  >(AGENT_STEPS.map((s) => ({ ...s, status: 'pending' })))
  const [budget, setBudget] = useState<BudgetBreakdown | null>(null)
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const onMessage = useCallback((msg: AgentUpdate) => {
    setAgentSteps((prev) =>
      prev.map((s) => {
        if (s.id === msg.agent || (msg.agent === 'research_fan_out' && ['flight_agent', 'hotel_agent', 'experience_agent', 'weather_agent', 'visa_safety_agent'].includes(s.id))) {
          return { ...s, status: 'running', message: msg.message }
        }
        return s
      }),
    )
  }, [])

  const onComplete = useCallback((data: Record<string, unknown>) => {
    setAgentSteps((prev) => prev.map((s) => ({ ...s, status: 'done' })))
    if (data.budget_breakdown) setBudget(data.budget_breakdown as BudgetBreakdown)
    if (data.itinerary) setItinerary(data.itinerary as Itinerary)
    setPlanning(false)
  }, [])

  const onError = useCallback((error: string) => {
    console.error('WS error:', error)
    setPlanning(false)
  }, [])

  const { connect } = useWebSocket({ onMessage, onComplete, onError })

  const handleSubmit = () => {
    if (!query.trim() || planning) return
    setPlanning(true)
    setBudget(null)
    setItinerary(null)
    setAgentSteps(AGENT_STEPS.map((s) => ({ ...s, status: 'pending' })))
    connect(query.trim())
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-voyager-ocean via-voyager-blue to-voyager-teal">
      {/* Hero */}
      <div className="text-center pt-16 pb-8 px-4">
        <div className="flex items-center justify-center gap-2 mb-3">
          <Plane className="w-8 h-8 text-white" />
          <h1 className="text-4xl font-bold text-white tracking-tight">Voyager</h1>
        </div>
        <p className="text-white/70 text-lg">Your AI travel planning team — all working at once</p>
      </div>

      {/* Search bar */}
      <div className="max-w-2xl mx-auto px-4 mb-8">
        <div className="bg-white rounded-2xl shadow-2xl p-2 flex gap-2">
          <div className="flex-1 flex items-start gap-3 px-3 py-2">
            <MapPin className="w-5 h-5 text-voyager-teal mt-2 shrink-0" />
            <textarea
              ref={textareaRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your dream trip... e.g. Greece under $2000 this summer"
              rows={2}
              className="flex-1 resize-none outline-none text-gray-800 placeholder-gray-400 text-base leading-relaxed"
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={planning || !query.trim()}
            className="bg-voyager-teal hover:bg-teal-600 disabled:opacity-50 text-white rounded-xl px-5 py-3 flex items-center gap-2 font-medium transition-colors"
          >
            <Send className="w-4 h-4" />
            Plan
          </button>
        </div>

        {/* Example queries */}
        {!planning && !itinerary && (
          <div className="mt-4 flex flex-wrap gap-2 justify-center">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => setQuery(q)}
                className="text-xs bg-white/20 hover:bg-white/30 text-white rounded-full px-3 py-1.5 transition-colors"
              >
                {q.slice(0, 45)}...
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Planning state */}
      <AnimatePresence>
        {planning && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="max-w-5xl mx-auto px-4 flex justify-center"
          >
            <AgentStatusPanel steps={agentSteps} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      {(budget || itinerary) && (
        <div className="max-w-5xl mx-auto px-4 pb-16">
          <div className="grid lg:grid-cols-[1fr_320px] gap-6">
            {/* Itinerary */}
            <div>
              {itinerary?.summary && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="bg-white rounded-2xl shadow-lg p-6 mb-6"
                >
                  <h2 className="text-xl font-bold text-voyager-ocean mb-2">Your Trip</h2>
                  <p className="text-gray-600">{itinerary.summary}</p>
                  {itinerary.highlights && (
                    <ul className="mt-4 space-y-1">
                      {itinerary.highlights.map((h, i) => (
                        <li key={i} className="flex gap-2 text-sm text-gray-700">
                          <span className="text-voyager-teal font-bold">✓</span> {h}
                        </li>
                      ))}
                    </ul>
                  )}
                </motion.div>
              )}

              {itinerary?.days && (
                <div className="space-y-4">
                  {itinerary.days.map((day, i) => (
                    <ItineraryCard key={day.day_number} day={day} index={i} />
                  ))}
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              {budget && <BudgetTracker breakdown={budget} />}

              {itinerary?.booking_checklist && (
                <div className="bg-white rounded-2xl shadow-lg p-6">
                  <h3 className="font-semibold text-gray-800 mb-3">Booking Checklist</h3>
                  <ul className="space-y-2">
                    {itinerary.booking_checklist.map((item, i) => (
                      <li key={i} className="flex gap-2 text-sm text-gray-600">
                        <input type="checkbox" className="mt-0.5 accent-voyager-teal" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {itinerary?.local_phrases && (
                <div className="bg-white rounded-2xl shadow-lg p-6">
                  <h3 className="font-semibold text-gray-800 mb-3">Useful Phrases</h3>
                  <div className="space-y-2">
                    {itinerary.local_phrases.map((p, i) => (
                      <div key={i} className="text-sm">
                        <p className="font-medium text-voyager-ocean">{p.phrase}</p>
                        <p className="text-gray-500 text-xs">{p.pronunciation} — {p.meaning}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
