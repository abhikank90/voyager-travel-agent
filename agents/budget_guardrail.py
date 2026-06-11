from dataclasses import dataclass

from .base_agent import BaseAgent


@dataclass
class BudgetBreakdown:
    flights: float
    hotel: float
    activities: float
    food: float
    misc: float
    total: float
    budget_usd: float
    is_within_budget: bool
    overage_usd: float
    savings_usd: float


class BudgetGuardrailAgent(BaseAgent):
    """Gate node: aggregates costs and decides whether to loop back or proceed."""

    name = "budget_guardrail"
    description = "Validates total trip cost against user budget; triggers retry loop if over budget"

    ACTIVITY_RATIO = 0.10
    FOOD_RATIO = 0.15
    MISC_RATIO = 0.05
    MAX_RETRIES = 2

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        budget = intent.get("budget_usd", 2000)

        flight_cost = state.get("flight_cost_usd", 0)
        hotel_cost = state.get("hotel_cost_usd", 0)

        activity_cost = budget * self.ACTIVITY_RATIO
        food_cost = budget * self.FOOD_RATIO
        misc_cost = budget * self.MISC_RATIO

        total = flight_cost + hotel_cost + activity_cost + food_cost + misc_cost
        overage = max(0.0, total - budget)
        savings = max(0.0, budget - total)
        retry_count = state.get("budget_retry_count", 0)

        breakdown = BudgetBreakdown(
            flights=flight_cost,
            hotel=hotel_cost,
            activities=activity_cost,
            food=food_cost,
            misc=misc_cost,
            total=round(total, 2),
            budget_usd=budget,
            is_within_budget=total <= budget,
            overage_usd=round(overage, 2),
            savings_usd=round(savings, 2),
        )

        result = {
            "budget_breakdown": {
                "flights_usd": breakdown.flights,
                "hotel_usd": breakdown.hotel,
                "activities_usd": breakdown.activities,
                "food_usd": breakdown.food,
                "misc_usd": breakdown.misc,
                "total_usd": breakdown.total,
                "budget_usd": breakdown.budget_usd,
                "is_within_budget": breakdown.is_within_budget,
                "overage_usd": breakdown.overage_usd,
                "savings_usd": breakdown.savings_usd,
            },
            "budget_ok": breakdown.is_within_budget,
            "budget_retry_count": retry_count,
        }

        if not breakdown.is_within_budget and retry_count < self.MAX_RETRIES:
            tighter = budget * (0.85 if retry_count == 0 else 0.75)
            result["tighter_budget"] = tighter
            result["budget_retry_count"] = retry_count + 1
            result["budget_loop_back"] = True
        else:
            result["budget_loop_back"] = False

        return result
