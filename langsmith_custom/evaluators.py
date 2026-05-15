"""
LangSmith evaluation suite for Voyager Travel Agent.

Run with:
    python -m langsmith.evaluators
"""
from langsmith import Client
from langsmith.evaluation import evaluate, LangChainStringEvaluator
from langsmith.schemas import Run, Example

client = Client()

DATASET_NAME = "voyager-travel-queries"


def create_dataset():
    """Seed evaluation dataset — run once."""
    examples = [
        {
            "inputs": {"user_query": "I want a vacation in Greece under $2000 with good beaches and local food around summer 2026"},
            "outputs": {
                "destination": "Greece",
                "budget_usd": 2000,
                "interests": ["beaches", "local food"],
            },
        },
        {
            "inputs": {"user_query": "10-day Japan trip under $3500, temples and street food, March 2027"},
            "outputs": {
                "destination": "Japan",
                "budget_usd": 3500,
                "duration_days": 10,
                "interests": ["temples", "street food"],
            },
        },
        {
            "inputs": {"user_query": "Weekend in Paris under $1500, romantic, great restaurants"},
            "outputs": {
                "destination": "Paris",
                "budget_usd": 1500,
                "interests": ["romantic", "restaurants"],
            },
        },
    ]
    dataset = client.create_dataset(DATASET_NAME, description="Voyager travel planning eval set")
    client.create_examples(
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
        dataset_id=dataset.id,
    )
    return dataset


def intent_accuracy(run: Run, example: Example) -> dict:
    """Checks that intent parser extracted correct destination and budget."""
    output = run.outputs or {}
    intent = output.get("intent", {})
    expected = example.outputs or {}

    score = 0
    if intent.get("destination", "").lower() in expected.get("destination", "").lower():
        score += 0.5
    if abs(intent.get("budget_usd", 0) - expected.get("budget_usd", 0)) < 100:
        score += 0.5

    return {"key": "intent_accuracy", "score": score}


def budget_compliance(run: Run, example: Example) -> dict:
    """Checks that final itinerary is within budget."""
    output = run.outputs or {}
    breakdown = output.get("budget_breakdown", {})
    is_ok = breakdown.get("is_within_budget", False)
    return {"key": "budget_compliance", "score": 1.0 if is_ok else 0.0}


def itinerary_completeness(run: Run, example: Example) -> dict:
    """Checks that itinerary has required fields."""
    output = run.outputs or {}
    itinerary = output.get("itinerary", {})
    required = ["summary", "days", "highlights", "packing_list", "booking_checklist"]
    score = sum(1 for k in required if k in itinerary) / len(required)
    return {"key": "itinerary_completeness", "score": score}


def run_evaluation():
    from graph.travel_graph import run_travel_query

    async def target(inputs: dict) -> dict:
        return await run_travel_query(inputs["user_query"])

    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[intent_accuracy, budget_compliance, itinerary_completeness],
        experiment_prefix="voyager-eval",
        metadata={"version": "1.0.0"},
    )
    print(results.to_pandas())


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_evaluation())
