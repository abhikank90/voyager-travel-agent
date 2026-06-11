#!/usr/bin/env python3
"""
Generate AWS-style architecture diagram for Voyager Travel Agent.

Requirements:
    pip install diagrams
    brew install graphviz  # macOS
    # or: apt-get install graphviz  # Linux
"""

import os

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import SimpleQueueServiceSqs
from diagrams.aws.network import ELB
from diagrams.onprem.client import Users
from diagrams.programming.framework import React

# Set output directory
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, "..", "docs", "diagrams")
os.makedirs(output_dir, exist_ok=True)

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.8",
    "ranksep": "1.0"
}

node_attr = {
    "fontsize": "12",
    "fontname": "Sans-Serif"
}

edge_attr = {
    "fontsize": "10"
}

with Diagram(
    "Voyager Travel Agent - System Architecture",
    filename=os.path.join(output_dir, "voyager_architecture"),
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png"
):
    # User layer
    users = Users("Users\n(Web Browser)")

    # Frontend
    with Cluster("Frontend Layer"):
        react_ui = React("React UI\nVite + TypeScript\nTailwind CSS")

    # AWS Cloud
    with Cluster("AWS Cloud Infrastructure"):
        # API Layer
        with Cluster("API Gateway & Compute"):
            alb = ELB("Application\nLoad Balancer\n(HTTPS + WS)")
            fargate = ECS("ECS Fargate\nFastAPI Server")

        # LangGraph State Machine
        with Cluster("LangGraph Multi-Agent System", graph_attr={"bgcolor": "#E3F2FD"}):

            # Entry agents
            with Cluster("Entry Pipeline"):
                from diagrams.onprem.aggregator import Fluentd
                personalisation = Fluentd("Personalisation\nAgent")
                intent_parser = Fluentd("Intent Parser\nAgent")

            # Research agents
            with Cluster("Research Agents (Parallel Execution)"):
                from diagrams.onprem.compute import Server
                flight_agent = Server("✈️\nFlight Agent")
                hotel_agent = Server("🏨\nHotel Agent")
                experience_agent = Server("🎯\nExperience Agent")
                weather_agent = Server("☁️\nWeather Agent")
                visa_agent = Server("🛂\nVisa/Safety Agent")

            # Collaboration agents
            with Cluster("Coordination Layer"):
                collab_hub = Server("🤝\nCollaboration Hub\n(Multi-Round)")
                budget_guardrail = Server("💰\nBudget Guardrail")
                option_generator = Server("📊\nOption Generator\n(3 Variants)")

        # Data storage
        with Cluster("Data & State Management"):
            dynamodb = Dynamodb("DynamoDB\nUser Profiles\nSession State")
            sqs = SimpleQueueServiceSqs("SQS\nEvent Queue")

    # External Services
    with Cluster("External APIs"):
        from diagrams.onprem.network import Internet
        from diagrams.saas.chat import Slack

        claude_api = Slack("Anthropic\nClaude API\n(Sonnet 4.5 & Haiku)")
        amadeus_api = Internet("Amadeus\nFlight API")
        booking_api = Internet("Booking.com\nHotel API")
        weather_api = Internet("OpenWeather\nAPI")
        duckduckgo = Internet("DuckDuckGo\nSearch")

    # User flow
    users >> Edge(label="HTTPS", color="blue") >> react_ui
    react_ui >> Edge(label="WebSocket\n(Real-time)", color="blue") >> alb

    # API layer
    alb >> Edge(label="HTTP/WS", color="darkgreen") >> fargate

    # LangGraph entry
    fargate >> Edge(label="Query", color="purple") >> personalisation
    personalisation >> intent_parser

    # Research round
    intent_parser >> Edge(label="Round 1", color="orange") >> [
        flight_agent,
        hotel_agent,
        experience_agent,
        weather_agent,
        visa_agent
    ]

    # Collaboration flow
    [flight_agent, hotel_agent, experience_agent, weather_agent, visa_agent] >> \
        Edge(label="Findings", color="orange") >> collab_hub

    collab_hub >> Edge(label="Refinement\nMessages", color="red", style="dashed") >> \
        [flight_agent, hotel_agent, experience_agent]

    # Final flow
    collab_hub >> Edge(label="Validated", color="green") >> budget_guardrail
    budget_guardrail >> option_generator
    option_generator >> Edge(label="3 Trip Options", color="green") >> fargate

    # External API connections
    flight_agent >> Edge(label="Search", color="gray", style="dotted") >> amadeus_api
    hotel_agent >> Edge(label="Search", color="gray", style="dotted") >> booking_api
    experience_agent >> Edge(label="AI", color="gray", style="dotted") >> claude_api
    weather_agent >> Edge(label="Forecast", color="gray", style="dotted") >> weather_api
    visa_agent >> Edge(label="Search", color="gray", style="dotted") >> duckduckgo
    visa_agent >> Edge(label="AI", color="gray", style="dotted") >> claude_api
    collab_hub >> Edge(label="AI Analysis", color="gray", style="dotted") >> claude_api
    option_generator >> Edge(label="AI", color="gray", style="dotted") >> claude_api

    # Data persistence
    fargate >> Edge(label="Read/Write", color="brown") >> dynamodb
    fargate >> Edge(label="Publish", color="brown") >> sqs

print(f"✅ Diagram generated: {output_dir}/voyager_architecture.png")
print("\nTo view the diagram:")
print(f"  open {output_dir}/voyager_architecture.png")
