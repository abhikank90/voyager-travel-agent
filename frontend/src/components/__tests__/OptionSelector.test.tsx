/**
 * Tests for OptionSelector component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OptionSelector } from '../OptionSelector'
import { TripOption } from '../../types'

const mockOptions: TripOption[] = [
  {
    option_id: 0,
    style: 'budget',
    title: 'Budget Explorer',
    total_cost_usd: 1500,
    flight: { airline: 'Budget Air', price: 450, stops: 2, duration: '18h', departure_time: '22:00', arrival_time: '04:00' },
    hotel: { name: 'Budget Inn', price_per_night: 60, rating: 3.5, location: 'Athens', amenities: [] },
    experiences: [],
    day_by_day: [],
    highlights: ['Save $500'],
    trade_offs: ['2 stops']
  },
  {
    option_id: 1,
    style: 'balanced',
    title: 'Balanced',
    total_cost_usd: 2000,
    flight: { airline: 'United', price: 650, stops: 1, duration: '14h', departure_time: '10:00', arrival_time: '14:00' },
    hotel: { name: 'Comfort Hotel', price_per_night: 120, rating: 4.2, location: 'Santorini', amenities: [] },
    experiences: [],
    day_by_day: [],
    highlights: ['Best value'],
    trade_offs: []
  },
  {
    option_id: 2,
    style: 'premium',
    title: 'Premium Luxury',
    total_cost_usd: 2300,
    flight: { airline: 'Delta', price: 850, stops: 0, duration: '10h 30m', departure_time: '08:00', arrival_time: '10:00' },
    hotel: { name: 'Luxury Resort', price_per_night: 250, rating: 4.9, location: 'Santorini', amenities: [] },
    experiences: [],
    day_by_day: [],
    highlights: ['Direct flight'],
    trade_offs: ['$300 over budget']
  }
]

describe('OptionSelector', () => {
  it('renders all three option cards', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <OptionSelector
        options={mockOptions}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText('Budget Explorer')).toBeInTheDocument()
    expect(screen.getByText('Balanced')).toBeInTheDocument()
    expect(screen.getByText('Premium Luxury')).toBeInTheDocument()
  })

  it('displays all three costs', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <OptionSelector
        options={mockOptions}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/\$1,500/)).toBeInTheDocument()
    expect(screen.getByText(/\$2,000/)).toBeInTheDocument()
    expect(screen.getByText(/\$2,300/)).toBeInTheDocument()
  })

  it('renders comparison table', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <OptionSelector
        options={mockOptions}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    // Should have a comparison section
    expect(screen.getByText(/compare|comparison/i)).toBeInTheDocument()
  })

  it('shows budget option as green', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    const { container } = render(
      <OptionSelector
        options={mockOptions}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    // Budget card should have green styling
    const budgetCard = screen.getByText('Budget Explorer').closest('div')
    expect(budgetCard).toHaveClass(/green/i)
  })

  it('forwards onSelectOption to cards', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <OptionSelector
        options={mockOptions}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    // Should render select buttons
    const selectButtons = screen.getAllByRole('button', { name: /select/i })
    expect(selectButtons).toHaveLength(3)
  })

  it('forwards onViewDetails to cards', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <OptionSelector
        options={mockOptions}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    // Should render view details buttons
    const viewButtons = screen.getAllByRole('button', { name: /view.*details/i })
    expect(viewButtons).toHaveLength(3)
  })

  it('renders empty state when no options provided', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <OptionSelector
        options={[]}
        onSelectOption={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    // Should show empty or loading state
    expect(screen.queryByText('Budget Explorer')).not.toBeInTheDocument()
  })
})
