#!/usr/bin/env python3
"""
Generate AWS-style architecture diagram for Voyager Travel Agent (Optimized Layout).

Requirements:
    pip install diagrams
    brew install graphviz  # macOS
"""

import os

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import SimpleQueueServiceSqs
from diagrams.aws.network import ELB
from diagrams.onprem.aggregator import Fluentd
from diagrams.onprem.client import Users
from diagrams.onprem.compute import Server
from diagrams.onprem.network import Internet
from diagrams.programming.framework import React
from diagrams.saas.chat import Slack

# Set output directory
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, "..", "docs", "diagrams")
os.makedirs(output_dir, exist_ok=True)

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.6",
    "ranksep": "0.8",
    "compound": "true"
}

node_attr = {
    "fontsize": "11",
    "fontname": "Sans-Serif"
}

edge_attr = {
    "fontsize": "9"
}

with Diagram(
    "Voyager Travel Agent - System Architecture",
    filename=os.path.join(output_dir, "voyager_architecture_optimized"),
    show=False,
    direction="LR",  # Left to Right for more width, less height
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png"
):
    # Column 1: User & Frontend
    with Cluster("User Layer"):
        users = Users("Users\n(Browser)")
        react_ui = React("React UI\nTypeScript\nTailwind")

    # Column 2: AWS Infrastructure
    with Cluster("AWS Cloud"):
        with Cluster("API Layer"):
            alb = ELB("Load\nBalancer\nHTTPS+WS")
            fargate = ECS("ECS Fargate\nFastAPI")

        with Cluster("Data Storage"):
            dynamodb = Dynamodb("DynamoDB\nProfiles")
            sqs = SimpleQueueServiceSqs("SQS\nQueue")

    # Column 3: LangGraph Multi-Agent System (Reorganized)
    with Cluster("LangGraph Multi-Agent System"):
        # Entry pipeline on the left side
        with Cluster("Entry", graph_attr={"bgcolor": "#FFF3E0"}):
            personalisation = Fluentd("Personalisation")
            intent_parser = Fluentd("Intent Parser")

        # Research agents in the middle
        with Cluster("Research Agents (Parallel)", graph_attr={"bgcolor": "#E8F5E9"}):
            flight_agent = Server("✈️\nFlight")
            hotel_agent = Server("🏨\nHotel")
            experience_agent = Server("🎯\nExperience")
            weather_agent = Server("☁️\nWeather")
            visa_agent = Server("🛂\nVisa/Safety")

        # Budget guardrail (between research and coordination)
        budget_guardrail = Server("💰\nBudget\nGuardrail")

    # Column 4: Coordination & External (Right side)
    with Cluster("Coordination & External"):
        # Coordination layer above external APIs
        with Cluster("Coordination", graph_attr={"bgcolor": "#F3E5F5"}):
            collab_hub = Server("🤝\nCollaboration\nHub")
            option_generator = Server("📊\nOption\nGenerator")

        # External APIs below
        with Cluster("External APIs", graph_attr={"bgcolor": "#E0F2F1"}):
            claude_api = Slack("Claude\nAnthropic")
            amadeus_api = Internet("Amadeus\nFlights")
            booking_api = Internet("Booking\nHotels")
            weather_api = Internet("OpenWeather")
            duckduckgo = Internet("DuckDuckGo")

    # User flow
    users >> Edge(label="HTTPS", color="blue", style="bold") >> react_ui
    react_ui >> Edge(label="WebSocket", color="blue") >> alb
    alb >> fargate

    # Entry pipeline
    fargate >> Edge(label="Query", color="purple") >> personalisation
    personalisation >> intent_parser

    # Research round 1
    intent_parser >> Edge(label="Round 1", color="orange") >> [
        flight_agent,
        hotel_agent,
        experience_agent,
        weather_agent,
        visa_agent
    ]

    # Findings to collaboration hub
    flight_agent >> Edge(label="Findings", color="orange") >> collab_hub
    hotel_agent >> Edge(color="orange") >> collab_hub
    experience_agent >> Edge(color="orange") >> collab_hub
    weather_agent >> Edge(color="orange") >> collab_hub
    visa_agent >> Edge(color="orange") >> collab_hub

    # Refinement messages back (dashed red)
    collab_hub >> Edge(label="Refine", color="red", style="dashed") >> hotel_agent
    collab_hub >> Edge(label="Refine", color="red", style="dashed") >> experience_agent

    # After refinement
    collab_hub >> Edge(label="Validated", color="green") >> budget_guardrail
    budget_guardrail >> Edge(color="green") >> option_generator

    # Final output
    option_generator >> Edge(label="3 Options", color="green", style="bold") >> fargate

    # External API calls (dotted gray)
    flight_agent >> Edge(color="gray", style="dotted") >> amadeus_api
    hotel_agent >> Edge(color="gray", style="dotted") >> booking_api
    experience_agent >> Edge(color="gray", style="dotted") >> claude_api
    weather_agent >> Edge(color="gray", style="dotted") >> weather_api
    visa_agent >> Edge(color="gray", style="dotted") >> duckduckgo
    visa_agent >> Edge(color="gray", style="dotted") >> claude_api
    collab_hub >> Edge(color="gray", style="dotted") >> claude_api
    option_generator >> Edge(color="gray", style="dotted") >> claude_api

    # Data persistence
    fargate >> Edge(label="Store", color="brown") >> dynamodb
    fargate >> Edge(label="Publish", color="brown") >> sqs

print(f"✅ Optimized diagram generated: {output_dir}/voyager_architecture_optimized.png")
print("\nTo view:")
print(f"  open {output_dir}/voyager_architecture_optimized.png")
