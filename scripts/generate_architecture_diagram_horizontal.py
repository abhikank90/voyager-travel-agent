#!/usr/bin/env python3
"""
Generate AWS-style architecture diagram for Voyager Travel Agent (Horizontal Layout).

Requirements:
    pip install diagrams
    brew install graphviz  # macOS
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import ECS, Lambda
from diagrams.aws.network import ELB
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import SimpleQueueServiceSqs
from diagrams.onprem.client import Users
from diagrams.programming.framework import React
from diagrams.programming.flowchart import PredefinedProcess, Database
from diagrams.programming.language import Python
import os

# Set output directory
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, "..", "docs", "diagrams")
os.makedirs(output_dir, exist_ok=True)

graph_attr = {
    "fontsize": "14",
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.6",
    "ranksep": "1.5"
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
    filename=os.path.join(output_dir, "voyager_architecture_horizontal"),
    show=False,
    direction="LR",  # Left to Right
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png"
):
    # Column 1: User & Frontend
    with Cluster("User Interface"):
        users = Users("Users\n(Browser)")
        react_ui = React("React UI\nTypeScript")

    # Column 2: AWS Infrastructure
    with Cluster("AWS Cloud"):
        with Cluster("API Layer"):
            alb = ELB("Load\nBalancer")
            fargate = ECS("ECS\nFargate")

        with Cluster("Storage"):
            dynamodb = Dynamodb("DynamoDB")
            sqs = SimpleQueueServiceSqs("SQS")

    # Column 3: LangGraph Multi-Agent System
    with Cluster("LangGraph Multi-Agent System"):
        with Cluster("Entry"):
            intent = PredefinedProcess("Intent\nParser")

        with Cluster("Research Agents (Parallel)"):
            flight = PredefinedProcess("✈️ Flight")
            hotel = PredefinedProcess("🏨 Hotel")
            experience = PredefinedProcess("🎯 Experience")
            weather = PredefinedProcess("☁️ Weather")
            visa = PredefinedProcess("🛂 Visa/Safety")

        with Cluster("Coordination"):
            collab_hub = PredefinedProcess("🤝 Collab\nHub")
            budget = PredefinedProcess("💰 Budget")
            options = PredefinedProcess("📊 Options\n(3 Variants)")

    # Column 4: External Services
    with Cluster("External APIs"):
        from diagrams.saas.chat import Slack
        from diagrams.onprem.network import Internet

        claude = Slack("Claude API\n(Anthropic)")
        amadeus = Internet("Amadeus\n(Flights)")
        booking = Internet("Booking.com\n(Hotels)")
        openweather = Internet("OpenWeather")
        ddg = Internet("DuckDuckGo")

    # User flow (left to right)
    users >> Edge(color="blue", style="bold") >> react_ui
    react_ui >> Edge(label="WebSocket", color="blue") >> alb
    alb >> fargate

    # LangGraph flow
    fargate >> Edge(label="Query", color="purple") >> intent

    # Research round
    intent >> Edge(label="Round 1", color="orange") >> [flight, hotel, experience, weather, visa]

    # Collaboration
    flight >> Edge(color="orange") >> collab_hub
    hotel >> Edge(color="orange") >> collab_hub
    experience >> Edge(color="orange") >> collab_hub
    weather >> Edge(color="orange") >> collab_hub
    visa >> Edge(color="orange") >> collab_hub

    # Refinement (dashed back)
    collab_hub >> Edge(label="Refine", color="red", style="dashed") >> [hotel, experience]

    # Final flow
    collab_hub >> Edge(color="green") >> budget >> options

    # Back to API
    options >> Edge(label="3 Options", color="green") >> fargate

    # External API calls (dotted)
    flight >> Edge(color="gray", style="dotted") >> amadeus
    hotel >> Edge(color="gray", style="dotted") >> booking
    experience >> Edge(color="gray", style="dotted") >> claude
    weather >> Edge(color="gray", style="dotted") >> openweather
    visa >> Edge(color="gray", style="dotted") >> ddg
    visa >> Edge(color="gray", style="dotted") >> claude
    collab_hub >> Edge(color="gray", style="dotted") >> claude
    options >> Edge(color="gray", style="dotted") >> claude

    # Data persistence
    fargate >> Edge(label="Store", color="brown") >> dynamodb
    fargate >> Edge(color="brown") >> sqs

print(f"✅ Horizontal diagram generated: {output_dir}/voyager_architecture_horizontal.png")
print("\nTo view:")
print(f"  open {output_dir}/voyager_architecture_horizontal.png")
