---
title: 'Voyager: Typed conflict detection, targeted peer feedback, and reproducible replay for multi-agent LLM systems'
tags:
  - Python
  - large language models
  - multi-agent systems
  - conflict resolution
  - reproducibility
authors:
  - name: Abhishek Reddy Kankanala
    orcid: 0009-0007-1951-8431
    affiliation: 1
affiliations:
  - name: Independent Researcher, Los Angeles, California, United States
    index: 1
date: 16 November 2026
bibliography: paper.bib
---

# Summary

Voyager is an open-source research testbed for studying coordination among large language model (LLM) agents. When several specialized agents work in parallel on a shared task, their outputs can conflict, and most existing frameworks neither detect these conflicts nor route or measure them. Voyager adds a coordination layer that does all three, making conflict handling measurable. The testbed is implemented in Python and demonstrates end-to-end travel planning: five research agents look up flights, hotels, experiences, weather, and visa requirements in parallel. After each parallel round, a Collaboration Hub detects cross-agent conflicts using deterministic, typed rules, for example, a hotel booked far from the planned activities. For each conflict, the hub sends a structured constraint to the one agent responsible for resolving it, and only agents that receive a constraint are re-executed. From a single natural-language request, the system produces three complete trip variants with day-by-day itineraries.

Because LLM outputs are probabilistic, LLM systems are hard to reproduce. Voyager therefore records per-conflict lifecycle metrics and includes a three-mode fixture architecture (mock, capture, and replay) with hash-verified, sanitized data, pinned model settings, and a one-command reproduction script. Anyone can re-run the benchmark against real travel APIs from the captured fixtures and check every reported metric against committed expected values; only an Anthropic API key is needed.

Travel planning is the reference domain, and the package includes a working planner with a web front end, but the main research artifact is the coordination layer with its metrics and reproducibility tooling. Voyager is released under the MIT license, with full documentation, a continuous integration pipeline, and over two hundred automated tests.

# Statement of need

Multi-agent LLM frameworks provide orchestration, messaging, and role definitions [@wu2023autogen; @hong2023metagpt; @li2023camel; @langgraph]. However, they do not treat cross-agent consistency as a measurable property of a run. Recent failure analyses of multi-agent systems identify inter-agent misalignment and missing verification as major causes of task failure [@cemri2025why]. Practitioners who need a coherent combined output typically choose between serializing the agents and using critique loops. Serializing agents gives up the latency benefit of parallelism. In critique loops, agents debate or revise their answers over several rounds [@du2023debate; @liang2023encouraging; @madaan2023selfrefine; @shinn2023reflexion]. Critique loops are effective. However, their cost grows with the number of rounds and agents. Also, natural-language critique does not guarantee that a particular constraint reaches the agent able to act on it.

Voyager is a system for researchers studying multi-agent coordination and LLM-system evaluation. It is also for engineers who need measurable conflict handling. Voyager provides the following features.

* Typed, deterministic conflict detection: Each conflict carries machine-checkable evidence and a content-addressed fingerprint. This allows us to follow the same conflict across rounds and count its lifecycle states: introduced, resolved, persisting, or reopened.
* Targeted routing and selective re-execution: Each conflict type has exactly one resolving agent. Only agents that receive a constraint run again. They apply the constraint when choosing among their candidate results. If no candidate qualifies, the agent falls back explicitly.
* Lifecycle metrics per query and per round: resolution rate, convergence round, post-refinement introductions, and agent calls saved compared with re-running every agent.
* Three inventory modes, mock, capture and replay: Benchmarks against real flight, hotel and weather APIs can be captured once as hash-verified fixtures and re-run by anyone without API keys for those services.

# State of the field

General-purpose frameworks such as AutoGen [@wu2023autogen], MetaGPT [@hong2023metagpt], CAMEL [@li2023camel], and LangGraph [@langgraph] provide building blocks for multi-agent applications. These include agent roles, message passing, and control flow based on graphs or conversations. However, the application is responsible for maintaining consistency between agents. Some approaches such as multi-agent debate [@du2023debate; @liang2023encouraging] and single-agent self-refinement [@madaan2023selfrefine; @shinn2023reflexion] improve output quality by using iterative, natural-language feedback. They re-run every participant but do not guarantee which agent addresses which issue. Benchmarks such as TravelPlanner [@xie2024travelplanner] check whether a final plan satisfies constraints. They do not measure how a coordination mechanism resolves conflicts between agents during a run. A recent study found that agents acting for different users and sharing a resource performed worse when they messaged each other directly than when a single coordinator was used. The agents failed in part because they acted before reading pending messages and made unsupported claims about other users [@paliskara2026worse]. Voyager is designed for a single-user setting. However, its design addresses the same failure modes. Feedback is routed through a deterministic hub as typed data. An agent reads its constraints before it selects.

Voyager is complementary to these tools. It does not replace them; instead, it adds a narrow, deterministic coordination layer for systems that already use several parallel agents and need their outputs to agree. Its contribution is the combination of typed detection, single-agent routing, bounded selective re-execution, and lifecycle metrics. Voyager also provides replay tooling that makes those metrics reproducible.

# Software design

Voyager is a Python (>=3.11) FastAPI service with a React/TypeScript front end that streams the collaboration feed to the user via WebSocket. The coordination logic is a LangGraph state machine [@langgraph; @langchain] over a typed shared state, with Anthropic Claude models assigned by tier (a more capable model for synthesis and coordination, a cheaper one for the retrieval-style agents) and per-model token and cost tracking all built in.

The architecture has five properties that distinguish it from a conventional pipeline. We describe each property below.

(1) Parallel research and deterministic detection: The system uses five domain agents that run concurrently; these agents are flight, hotel, experience, weather, and visa or safety. A Collaboration Hub coordinates between rounds. The hub applies deterministic, typed conflict rules such as location mismatch, timing inefficiency, and weather or activity mismatch. The system does not use an LLM to check if outputs are consistent.

(2) Targeted, structured feedback: When the hub finds a conflict, it sends a typed message to the agent responsible for the conflict. For example, it may send the geocoded centroid of planned activities. Only the involved agent re-runs with the new constraint. Other agents do not re-execute. This approach saved 30 percent of agent calls on synthetic inventory and 45 percent on real inventory, compared with re-running every agent.

(3) Content-addressed conflict identity: The system fingerprints each conflict using a hash of its type, participants, and normalized evidence. The system does not include prose or round numbers in the hash. This method lets the system classify conflicts as new, persisting, resolved, or reopened in each round. At the end, the system reports any conflicts it failed to resolve. It does not drop unresolved conflicts.

(4) Structural round bounds: The architecture limits the number of coordination rounds by the structure of the graph. It does not use a counter to track rounds. Each conflict type has one resolution direction. This design removed an oscillation failure mode that appeared in earlier versions.

(5) Evidence-gated use of LLMs in detection: The system has an optional hybrid mode which is off by default. In this mode, a large language model (LLM) can propose conflict candidates and the rule layer must validate these candidates. In the bundled evaluation, the LLM found all three conflict classes that the rules do not cover, but none of its ten candidates passed validation, because validators for those classes do not exist yet. We publish this negative result alongside the mechanism.

Reproducibility is a core part of the design: All external calls, such as flight and hotel inventories, weather, and geocoding, run in one of three modes. The modes are deterministic mocks for development, capture of live API responses into hash-verified and privacy-sanitized fixtures, and replay of those fixtures with a date-anchored manifest. Since version 1.4, the LLM outputs that feed conflict detection (the parsed request and the experience list) are recorded and replayed as well. The system sets model sampling temperature in one place and a single script (scripts/reproduce.sh) replays the benchmark suite and compares the output.

The script compares the output to committed expected results with documented tolerances. The repository includes over two hundred unit and integration tests. It also includes front-end component tests. The repository provides a GitHub Actions pipeline for linting, tests with coverage, front-end build, and container build. It provides Docker images and Terraform templates for AWS deployment. A benchmark harness measures coordination mechanics on 25 queries over synthetic inventory and 12 queries over captured real inventory. For example, it measures conflicts raised, resolved, and reopened, agent calls, and dollar cost in both full-coordination and baseline configurations.

# Research impact statement

Voyager is a testbed for empirical study of multi-agent coordination mechanisms. It produces result artifacts as evidence for its design goals. We use synthetic inventory, constructed so that every query starts in conflict, to show that rule-based coordination resolves all detected conflicts by the second round. On real travel inventory captured from SerpApi, Nuitee, and OpenWeather, the hub resolved 10% of conflicts. In 8 of the 12 queries (67%), an agent that received a constraint found no qualifying option and kept its original choice. This is a property of the data, not the detector. The system reports unresolved conflicts explicitly and does not hide them.

We use a hybrid LLM-detector evaluation to measure where language-model judgment helps and where it fails. For example, LLMs help with semantic conflict classes that rules cannot detect. However, in the routing test, none of the LLM’s candidates passed rule validation, because validators for those classes do not yet exist. This provides concrete evidence for the ‘LLM proposes, rules validate’ design pattern. The reproducibility architecture allows independent third parties to replay the benchmark suite and verify all reported checks. Two consecutive replay runs of the 12-query benchmark produce identical results on all 24 query and mode pairs. An independent contributor filed confirmed bug reports and reproduced the benchmark on their own machine: before version 1.4, two quick-benchmark runs each failed 2 of 12 checks; after the fix, both runs passed all 12. We expect the testbed to help researchers who study coordination protocols, agent evaluation methodology, and reproducibility of LLM systems. Practitioners can also use it as a reference implementation for measurable conflict handling in production agentic pipelines.

# AI usage disclosure

Anthropic’s Claude Code was used to help write and refactor parts of the code, to draft unit tests and documentation. Grammarly was used for grammar and tone. 

# Acknowledgements

The author thanks Kalyan Matta for independent reproduction runs, for reporting the replay variance and environment issues that led to the version 1.4 fixes, and for the refactor that unified the conflict-routing maps. 

# References

