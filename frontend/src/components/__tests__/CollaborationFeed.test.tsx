/**
 * Tests for CollaborationFeed component
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CollaborationFeed } from '../CollaborationFeed'
import { CollaborationMessage } from '../../types'

const mockMessages: CollaborationMessage[] = [
  {
    from_agent: 'collaboration_hub',
    to_agent: 'hotel',
    message_type: 'constraint',
    content: 'Activities are far from hotel. Find closer options.',
    round: 1
  },
  {
    from_agent: 'collaboration_hub',
    to_agent: 'experience',
    message_type: 'insight',
    content: 'User prefers beaches. Prioritize beach activities.',
    round: 1
  },
  {
    from_agent: 'collaboration_hub',
    to_agent: 'flight',
    message_type: 'conflict',
    content: 'Late arrival time wastes first day.',
    round: 1
  }
]

describe('CollaborationFeed', () => {
  it('renders collaboration messages', () => {
    render(<CollaborationFeed messages={mockMessages} round={1} />)

    expect(screen.getByText(/Activities are far from hotel/)).toBeInTheDocument()
    expect(screen.getByText(/User prefers beaches/)).toBeInTheDocument()
    expect(screen.getByText(/Late arrival time/)).toBeInTheDocument()
  })

  it('displays round number', () => {
    render(<CollaborationFeed messages={mockMessages} round={1} />)

    expect(screen.getByText(/Round 1/i)).toBeInTheDocument()
  })

  it('shows from_agent and to_agent', () => {
    render(<CollaborationFeed messages={mockMessages} round={1} />)

    expect(screen.getByText(/collaboration_hub/i)).toBeInTheDocument()
    expect(screen.getByText(/hotel/i)).toBeInTheDocument()
  })

  it('applies color coding for constraint messages', () => {
    render(<CollaborationFeed messages={mockMessages} round={1} />)

    const constraintMsg = screen.getByText(/Activities are far from hotel/).closest('div')
    expect(constraintMsg).toHaveClass(/orange|constraint/)
  })

  it('applies color coding for insight messages', () => {
    render(<CollaborationFeed messages={mockMessages} round={1} />)

    const insightMsg = screen.getByText(/User prefers beaches/).closest('div')
    expect(insightMsg).toHaveClass(/yellow|insight/)
  })

  it('applies color coding for conflict messages', () => {
    render(<CollaborationFeed messages={mockMessages} round={1} />)

    const conflictMsg = screen.getByText(/Late arrival time/).closest('div')
    expect(conflictMsg).toHaveClass(/red|conflict/)
  })

  it('renders empty state when no messages', () => {
    render(<CollaborationFeed messages={[]} round={1} />)

    expect(screen.queryByText(/Activities are far/)).not.toBeInTheDocument()
  })

  it('displays icons for different message types', () => {
    const { container } = render(<CollaborationFeed messages={mockMessages} round={1} />)

    // Should have icons (svg elements)
    const icons = container.querySelectorAll('svg')
    expect(icons.length).toBeGreaterThan(0)
  })

  it('handles round 2 messages', () => {
    const round2Messages: CollaborationMessage[] = [
      {
        from_agent: 'collaboration_hub',
        to_agent: 'hotel',
        message_type: 'proposal',
        content: 'Conflicts resolved. Proceeding to generation.',
        round: 2
      }
    ]

    render(<CollaborationFeed messages={round2Messages} round={2} />)

    expect(screen.getByText(/Round 2/i)).toBeInTheDocument()
    expect(screen.getByText(/Conflicts resolved/)).toBeInTheDocument()
  })

  it('displays all message types correctly', () => {
    const allTypesMessages: CollaborationMessage[] = [
      { from_agent: 'hub', to_agent: 'hotel', message_type: 'insight', content: 'Insight message', round: 1 },
      { from_agent: 'hub', to_agent: 'hotel', message_type: 'constraint', content: 'Constraint message', round: 1 },
      { from_agent: 'hub', to_agent: 'hotel', message_type: 'question', content: 'Question message', round: 1 },
      { from_agent: 'hub', to_agent: 'hotel', message_type: 'proposal', content: 'Proposal message', round: 1 },
      { from_agent: 'hub', to_agent: 'hotel', message_type: 'conflict', content: 'Conflict message', round: 1 }
    ]

    render(<CollaborationFeed messages={allTypesMessages} round={1} />)

    expect(screen.getByText('Insight message')).toBeInTheDocument()
    expect(screen.getByText('Constraint message')).toBeInTheDocument()
    expect(screen.getByText('Question message')).toBeInTheDocument()
    expect(screen.getByText('Proposal message')).toBeInTheDocument()
    expect(screen.getByText('Conflict message')).toBeInTheDocument()
  })
})
