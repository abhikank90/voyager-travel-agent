import React from 'react'
import { CollaborationMessage } from '../types'
import { MessageSquare, AlertCircle, HelpCircle, Lightbulb, Flag } from 'lucide-react'

interface CollaborationFeedProps {
  messages: CollaborationMessage[]
  round: number
}

export const CollaborationFeed: React.FC<CollaborationFeedProps> = ({ messages, round }) => {
  const getMessageIcon = (messageType: string) => {
    switch (messageType) {
      case 'insight':
        return <Lightbulb className="w-4 h-4 text-yellow-600" />
      case 'constraint':
        return <AlertCircle className="w-4 h-4 text-orange-600" />
      case 'question':
        return <HelpCircle className="w-4 h-4 text-blue-600" />
      case 'proposal':
        return <MessageSquare className="w-4 h-4 text-green-600" />
      case 'conflict':
        return <Flag className="w-4 h-4 text-red-600" />
      default:
        return <MessageSquare className="w-4 h-4 text-gray-600" />
    }
  }

  const getMessageColor = (messageType: string) => {
    switch (messageType) {
      case 'insight':
        return 'bg-yellow-50 border-yellow-200'
      case 'constraint':
        return 'bg-orange-50 border-orange-200'
      case 'question':
        return 'bg-blue-50 border-blue-200'
      case 'proposal':
        return 'bg-green-50 border-green-200'
      case 'conflict':
        return 'bg-red-50 border-red-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  const getAgentName = (agentId: string) => {
    const names: Record<string, string> = {
      collaboration_hub: '🤝 Collaboration Hub',
      flight: '✈️ Flight Agent',
      hotel: '🏨 Hotel Agent',
      experience: '🎯 Experience Agent',
      weather: '☁️ Weather Agent',
      visa_safety: '🛂 Visa/Safety Agent'
    }
    return names[agentId] || agentId
  }

  if (messages.length === 0) {
    return null
  }

  return (
    <div className="w-full max-w-4xl mx-auto mb-6">
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center mb-3">
          <MessageSquare className="w-5 h-5 text-blue-600 mr-2" />
          <h3 className="font-semibold text-gray-900">
            Agent Collaboration (Round {round})
          </h3>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          Agents are discussing and refining their recommendations...
        </p>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`p-3 rounded-lg border ${getMessageColor(msg.message_type)}`}
            >
              <div className="flex items-start">
                <div className="flex-shrink-0 mt-0.5">{getMessageIcon(msg.message_type)}</div>
                <div className="ml-3 flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-xs font-semibold text-gray-700">
                      {getAgentName(msg.from_agent)} → {getAgentName(msg.to_agent)}
                    </div>
                    <span className="text-xs text-gray-500 capitalize">
                      {msg.message_type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-800">{msg.content}</p>
                  {msg.data && Object.keys(msg.data).length > 0 && (
                    <div className="mt-2 text-xs text-gray-600">
                      {msg.data.suggested_areas && (
                        <div>
                          <strong>Suggestions:</strong> {msg.data.suggested_areas.join(', ')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
