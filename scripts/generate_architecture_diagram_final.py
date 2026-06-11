#!/usr/bin/env python3
"""
Generate AWS-style architecture diagram matching the custom layout.
Top row: User Layer | AWS Cloud | External
Bottom row: Research Agents (large) | Coordination
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
    "splines": "spline",
    "nodesep": "0.8",
    "ranksep": "1.0",
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
    filename=os.path.join(output_dir, "voyager_architecture_final"),
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png"
):

    # === TOP ROW ===
    with Cluster("User Layer", graph_attr={"rank": "same"}):
        users = Users("Users")
        react = React("React UI")

    with Cluster("AWS Cloud", graph_attr={"rank": "same"}):
        alb = ELB("Load Balancer")
        fargate = ECS("ECS Fargate")
        with Cluster("Data"):
            dynamodb = Dynamodb("DynamoDB")
            sqs = SimpleQueueServiceSqs("SQS")

    with Cluster("External APIs", graph_attr={"rank": "same"}):
        claude = Slack("Claude")
        amadeus = Internet("Amadeus")
        booking = Internet("Booking.com")
        weather_api = Internet("Weather")
        ddg = Internet("DuckDuckGo")

    # === BOTTOM ROW ===
    with Cluster("Research Agents", graph_attr={"bgcolor": "#E8F5E9"}):
        # Entry
        personalisation = Fluentd("Personalisation")
        intent = Fluentd("Intent Parser")

        # 5 Research agents in a row
        flight = Server("✈️ Flight")
        hotel = Server("🏨 Hotel")
        experience = Server("🎯 Experience")
        weather = Server("☁️ Weather")
        visa = Server("🛂 Visa/Safety")

        # Budget
        budget = Server("💰 Budget")

    with Cluster("Coordination", graph_attr={"bgcolor": "#F3E5F5"}):
        collab_hub = Server("🤝 Collab Hub")
        option_gen = Server("📊 Options (3x)")

    # === CONNECTIONS ===

    # User flow
    users >> Edge(color="blue") >> react >> Edge(label="WS", color="blue") >> alb >> fargate

    # Entry pipeline
    fargate >> Edge(label="Query", color="purple") >> personalisation >> intent

    # Round 1
    intent >> Edge(label="R1", color="orange") >> flight
    intent >> Edge(label="R1", color="orange") >> hotel
    intent >> Edge(label="R1", color="orange") >> experience
    intent >> Edge(label="R1", color="orange") >> weather
    intent >> Edge(label="R1", color="orange") >> visa

    # To collaboration
    flight >> Edge(color="orange") >> collab_hub
    hotel >> Edge(color="orange") >> collab_hub
    experience >> Edge(color="orange") >> collab_hub
    weather >> Edge(color="orange") >> collab_hub
    visa >> Edge(color="orange") >> collab_hub

    # Refinement
    collab_hub >> Edge(label="Refine", color="red", style="dashed") >> hotel
    collab_hub >> Edge(color="red", style="dashed") >> experience

    # Final flow
    collab_hub >> Edge(label="OK", color="green") >> budget >> option_gen
    option_gen >> Edge(label="3 Options", color="green") >> fargate

    # External APIs
    flight >> Edge(color="gray", style="dotted") >> amadeus
    hotel >> Edge(color="gray", style="dotted") >> booking
    experience >> Edge(color="gray", style="dotted") >> claude
    weather >> Edge(color="gray", style="dotted") >> weather_api
    visa >> Edge(color="gray", style="dotted") >> ddg
    visa >> Edge(color="gray", style="dotted") >> claude
    collab_hub >> Edge(color="gray", style="dotted") >> claude
    option_gen >> Edge(color="gray", style="dotted") >> claude

    # Storage
    fargate >> Edge(color="brown") >> dynamodb
    fargate >> Edge(color="brown") >> sqs

print(f"✅ Final diagram generated: {output_dir}/voyager_architecture_final.png")
print("\nTo view:")
print(f"  open {output_dir}/voyager_architecture_final.png")
