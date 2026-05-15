import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, MapPin, Plane, Sparkles } from 'lucide-react'
import {
  CollaborativeAgentUpdate,
  AgentStatus,
  TripOption,
  CollaborationMessage
} from '../types'
import { AgentStatusPanel } from './AgentStatusPanel'
import { CollaborationFeed } from './CollaborationFeed'
import { OptionSelector } from './OptionSelector'
import { DetailedItineraryView } from './DetailedItineraryView'

const COLLABORATIVE_AGENT_STEPS = [
  { id: 'personalisation', label: 'Loading your profile' },
  { id: 'intent_parser', label: 'Understanding your request' },
  { id: 'research_round_1', label: 'Round 1: Initial research' },
  { id: 'collaboration_hub_1', label: 'Agents collaborating' },
  { id: 'research_round_2', label: 'Round 2: Refining' },
  { id: 'collaboration_hub_2', label: 'Final coordination' },
  { id: 'budget_guardrail', label: 'Budget validation' },
  { id: 'option_generator', label: 'Creating 3 options' },
]

const EXAMPLE_QUERIES = [
  'Greece under $2000 with beaches and local food, summer 2026',
  'Japan under $3500 for 10 days in March, temples and street food',
  'Weekend Paris trip under $1500, romantic restaurants and art'
]

type ViewMode = 'input' | 'planning' | 'options' | 'details'

export function CollaborativeChatInterface() {
  const [query, setQuery] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('input')
  const [sessionId, setSessionId] = useState<string>('')

  const [agentSteps, setAgentSteps] = useState<
    { id: string; label: string; status: AgentStatus; message?: string }[]
  >(COLLABORATIVE_AGENT_STEPS.map((s) => ({ ...s, status: 'pending' })))

  const [collaborationMessages, setCollaborationMessages] = useState<CollaborationMessage[]>([])
  const [collaborationRound, setCollaborationRound] = useState(0)
  const [tripOptions, setTripOptions] = useState<TripOption[]>([])
  const [selectedOption, setSelectedOption] = useState<TripOption | null>(null)

  const [ws, setWs] = useState<WebSocket | null>(null)

  const handleSubmit = () => {
    if (!query.trim() || viewMode === 'planning') return

    setViewMode('planning')
    setTripOptions([])
    setCollaborationMessages([])
    setAgentSteps(COLLABORATIVE_AGENT_STEPS.map((s) => ({ ...s, status: 'pending' })))

    // Generate session ID
    const newSessionId = `session-${Date.now()}`
    setSessionId(newSessionId)

    // Connect to collaborative WebSocket
    const websocket = new WebSocket(
      `ws://localhost:8000/ws/travel/collaborative/${newSessionId}`
    )

    websocket.onopen = () => {
      websocket.send(JSON.stringify({ query: query.trim(), user_id: 'demo-user' }))
    }

    websocket.onmessage = (event) => {
      const data: CollaborativeAgentUpdate = JSON.parse(event.data)

      if (data.type === 'agent_update') {
        // Update agent status
        setAgentSteps((prev) =>
          prev.map((s) => {
            if (s.id === data.agent) {
              return { ...s, status: 'running', message: data.message }
            }
            return s
          })
        )
      } else if (data.type === 'collaboration') {
        // Add collaboration messages
        if (data.collaboration_messages) {
          setCollaborationMessages((prev) => [...prev, ...data.collaboration_messages!])
          // Extract round number from messages
          if (data.collaboration_messages.length > 0) {
            setCollaborationRound(data.collaboration_messages[0].round)
          }
        }
      } else if (data.type === 'options_ready') {
        // Show trip options
        if (data.trip_options) {
          setTripOptions(data.trip_options)
          setViewMode('options')
          setAgentSteps((prev) => prev.map((s) => ({ ...s, status: 'done' })))
        }
      } else if (data.type === 'error') {
        console.error('WebSocket error:', data.message)
        setViewMode('input')
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      setViewMode('input')
    }

    websocket.onclose = () => {
      console.log('WebSocket closed')
    }

    setWs(websocket)
  }

  const handleSelectOption = async (optionId: number) => {
    const option = tripOptions.find((o) => o.option_id === optionId)
    if (option) {
      setSelectedOption(option)

      // Call backend to save selection
      try {
        await fetch('http://localhost:8000/api/travel/select-option', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            option_id: optionId,
            user_id: 'demo-user'
          })
        })
      } catch (error) {
        console.error('Failed to save selection:', error)
      }
    }
  }

  const handleViewDetails = (optionId: number) => {
    const option = tripOptions.find((o) => o.option_id === optionId)
    if (option) {
      setSelectedOption(option)
      setViewMode('details')
    }
  }

  const handleBackToOptions = () => {
    setViewMode('options')
    setSelectedOption(null)
  }

  const handleRefinement = async (refinementQuery: string) => {
    if (!selectedOption) return

    try {
      const response = await fetch('http://localhost:8000/api/travel/refine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          selected_option_id: selectedOption.option_id,
          refinement_query: refinementQuery,
          user_id: 'demo-user'
        })
      })

      const data = await response.json()
      if (data.refined_option) {
        setSelectedOption(data.refined_option)
      }
    } catch (error) {
      console.error('Failed to refine:', error)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleNewSearch = () => {
    setViewMode('input')
    setQuery('')
    setTripOptions([])
    setSelectedOption(null)
    setCollaborationMessages([])
    if (ws) {
      ws.close()
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 via-purple-600 to-pink-500">
      {/* Hero */}
      <div className="text-center pt-16 pb-8 px-4">
        <div className="flex items-center justify-center gap-2 mb-3">
          <Plane className="w-8 h-8 text-white" />
          <h1 className="text-4xl font-bold text-white tracking-tight">Voyager</h1>
          <Sparkles className="w-6 h-6 text-yellow-300" />
        </div>
        <p className="text-white/90 text-lg font-medium">
          Collaborative AI Travel Planning — 3 Options, Perfectly Tailored
        </p>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 pb-16">
        {/* Search Bar */}
        {(viewMode === 'input' || viewMode === 'planning') && (
          <div className="max-w-2xl mx-auto mb-8">
            <div className="bg-white rounded-2xl shadow-2xl p-2">
              <div className="flex gap-2">
                <div className="flex-1 flex items-start gap-3 px-3 py-2">
                  <MapPin className="w-5 h-5 text-purple-600 mt-2 shrink-0" />
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe your dream trip... e.g. Greece under $2000 this summer"
                    rows={2}
                    className="flex-1 resize-none outline-none text-gray-800 placeholder-gray-400 text-base leading-relaxed"
                    disabled={viewMode === 'planning'}
                  />
                </div>
                <button
                  onClick={handleSubmit}
                  disabled={!query.trim() || viewMode === 'planning'}
                  className="bg-gradient-to-r from-purple-600 to-pink-600 text-white px-6 py-3 rounded-xl hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-semibold"
                >
                  <Send className="w-4 h-4" />
                  {viewMode === 'planning' ? 'Planning...' : 'Plan Trip'}
                </button>
              </div>
            </div>

            {/* Example Queries */}
            {viewMode === 'input' && (
              <div className="mt-4">
                <p className="text-white/70 text-sm mb-2">Try an example:</p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_QUERIES.map((ex, idx) => (
                    <button
                      key={idx}
                      onClick={() => setQuery(ex)}
                      className="text-sm bg-white/10 hover:bg-white/20 text-white px-3 py-1 rounded-full backdrop-blur-sm transition-colors"
                    >
                      {ex.slice(0, 40)}...
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Planning View */}
        {viewMode === 'planning' && (
          <div className="space-y-6">
            <AgentStatusPanel steps={agentSteps} />

            {collaborationMessages.length > 0 && (
              <CollaborationFeed messages={collaborationMessages} round={collaborationRound} />
            )}

            <div className="text-center">
              <div className="inline-block bg-white/10 backdrop-blur-sm text-white px-6 py-3 rounded-full">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                  <span>Agents are collaborating to create your perfect trip...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Options View */}
        {viewMode === 'options' && (
          <div>
            <button
              onClick={handleNewSearch}
              className="mb-4 text-white hover:text-white/80 transition-colors"
            >
              ← New Search
            </button>
            <OptionSelector
              options={tripOptions}
              onSelectOption={handleSelectOption}
              onViewDetails={handleViewDetails}
            />
          </div>
        )}

        {/* Details View */}
        {viewMode === 'details' && selectedOption && (
          <div>
            <DetailedItineraryView
              option={selectedOption}
              onBack={handleBackToOptions}
              onRequestRefinement={handleRefinement}
            />
          </div>
        )}
      </div>
    </div>
  )
}
