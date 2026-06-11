#!/usr/bin/env python3
"""
Generate AWS-style architecture diagram with custom layout structure.
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
    "nodesep": "0.5",
    "ranksep": "1.2",
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
    filename=os.path.join(output_dir, "voyager_architecture_custom"),
    show=False,
    direction="TB",  # Top to bottom to control layout
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png"
):

    # ROW 1: User Layer, AWS Cloud, External
    with Cluster("User Layer"):
        users = Users("Users")
        react = React("React UI\nTypeScript")

    with Cluster("AWS Cloud Infrastructure"):
        alb = ELB("Load Balancer\nHTTPS + WS")
        fargate = ECS("ECS Fargate\nFastAPI")

        with Cluster("Storage"):
            dynamodb = Dynamodb("DynamoDB")
            sqs = SimpleQueueServiceSqs("SQS")

    with Cluster("External APIs"):
        claude = Slack("Claude\nAnthropic")
        amadeus = Internet("Amadeus\nFlights")
        booking = Internet("Booking.com\nHotels")
        weather_api = Internet("OpenWeather")
        ddg = Internet("DuckDuckGo")

    # ROW 2: Research Agents (large), Coordination (vertical on right)
    with Cluster("LangGraph Multi-Agent System"):

        with Cluster("Research Agents", graph_attr={"bgcolor": "#E8F5E9"}):
            # Entry at top
            personalisation = Fluentd("Personalisation")
            intent = Fluentd("Intent Parser")

            # 5 research agents
            flight = Server("✈️ Flight Agent")
            hotel = Server("🏨 Hotel Agent")
            experience = Server("🎯 Experience Agent")
            weather = Server("☁️ Weather Agent")
            visa = Server("🛂 Visa/Safety Agent")

            # Budget at bottom
            budget = Server("💰 Budget Guardrail")

        with Cluster("Coordination", graph_attr={"bgcolor": "#F3E5F5"}):
            collab_hub = Server("🤝\nCollaboration\nHub")
            option_gen = Server("📊\nOption\nGenerator\n(3 Variants)")

    # Flow connections
    # User to AWS
    users >> Edge(color="blue", style="bold") >> react
    react >> Edge(label="WebSocket", color="blue") >> alb
    alb >> fargate

    # AWS to LangGraph entry
    fargate >> Edge(label="Query", color="purple") >> personalisation
    personalisation >> intent

    # Intent to research agents (Round 1)
    intent >> Edge(label="Round 1", color="orange") >> [flight, hotel, experience, weather, visa]

    # Research to Collaboration Hub
    flight >> Edge(color="orange") >> collab_hub
    hotel >> Edge(color="orange") >> collab_hub
    experience >> Edge(color="orange") >> collab_hub
    weather >> Edge(color="orange") >> collab_hub
    visa >> Edge(color="orange") >> collab_hub

    # Refinement (dashed back)
    collab_hub >> Edge(label="Refine", color="red", style="dashed") >> hotel
    collab_hub >> Edge(label="Refine", color="red", style="dashed") >> experience

    # Collaboration to Budget to Options
    collab_hub >> Edge(label="Validated", color="green") >> budget
    budget >> option_gen

    # Options back to API
    option_gen >> Edge(label="3 Options", color="green", style="bold") >> fargate

    # External API calls (dotted)
    flight >> Edge(color="gray", style="dotted") >> amadeus
    hotel >> Edge(color="gray", style="dotted") >> booking
    experience >> Edge(color="gray", style="dotted") >> claude
    weather >> Edge(color="gray", style="dotted") >> weather_api
    visa >> Edge(color="gray", style="dotted") >> ddg
    visa >> Edge(color="gray", style="dotted") >> claude
    collab_hub >> Edge(color="gray", style="dotted") >> claude
    option_gen >> Edge(color="gray", style="dotted") >> claude

    # Data storage
    fargate >> Edge(label="Store", color="brown") >> dynamodb
    fargate >> Edge(label="Events", color="brown") >> sqs

print(f"✅ Custom layout diagram generated: {output_dir}/voyager_architecture_custom.png")
print("\nTo view:")
print(f"  open {output_dir}/voyager_architecture_custom.png")
