# 🚀 JEV & KEV System 1 for Langflow

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Langflow Ready](https://img.shields.io/badge/Langflow-1.1%2B-purple.svg)](https://github.com/langflow-ai/langflow)
[![Tests Passing](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-System%201-orange.svg)](docs/ARCHITECTURE.md)

Production-grade visual GUI components, parallel evaluation engines, and routing workflows for **TypeSafe JEV** and **Local KEV System 1** models inside **[Langflow](https://github.com/langflow-ai/langflow)**.

---

## ⚡ The Big Picture: Why System 1 in Langflow?

In modern agentic AI architectures, traditional Large Language Models (LLMs) operate as **System 2** reasoning engines: they are expressive and generative, but slow, non-deterministic, poorly calibrated in confidence, and token-expensive when evaluating multiple classification axes.

**TypeSafe JEV & Local KEV System 1** are specialized, high-throughput models engineered specifically for fast, calibrated classification, binary propositions, and multi-criteria scoring:

1. **Massive Parallelism in a Single Pass**: Evaluate tens or hundreds of distinct questions (categorical choices, Yes/No flags, and weighted scoring rubrics) simultaneously across input text or structured JSON in a single `/v1/systemone` request.
2. **Mathematically Calibrated Probabilities**: Every choice and proposition produces true probability distributions with normalized Shannon entropy confidence scores.
3. **Automated Confidence Gating**: Degrades uncertain decisions to configurable fallbacks (e.g. `HUMAN_REVIEW`) before triggering downstream tools or external workflows.
4. **Zero-Code Visual Canvas Experience**: Domain experts can define complex classification rules, exclusion constraints (`not_for`), and manual decimal weights via Langflow GUI tables—no prompt engineering required!

---

## 📦 What's Inside

This repository provides **5 core Langflow components** (as reusable Python classes and drop-in Flow JSONs), an **end-to-end example pipeline**, and complete testing/documentation:

```
JEV_Langflow/
├── components/                            # Production Python source modules
│   ├── engine/
│   │   └── core_engine.py                 # Central JEV/KEV System 1 execution engine
│   ├── questions/
│   │   ├── choice_question.py             # Visual GUI for 1 to 255 categorical choices
│   │   ├── noul_question.py               # Visual GUI for Yes/No (Noul) propositions
│   │   └── score_question.py              # Visual GUI for manual-value scores (sum to 1.0)
│   └── routing/
│       └── result_extractor.py            # Unbundles decisions for independent routers
├── flows/
│   ├── components/                        # Drop-in single-node Langflow exports
│   │   ├── JEV Choice Question (GUI).json
│   │   ├── JEV Noul Question (Yes_No GUI).json
│   │   ├── JEV Score Question (Manual Values GUI).json
│   │   ├── JEV System 1 Core Engine.json
│   │   └── JEV Question Result Extractor.json
│   └── examples/                          # Full multi-node pipeline flows
│       └── jev_multi_question_routing_pipeline.json
├── docs/                                  # Deep-dive architecture & references
│   ├── ARCHITECTURE.md                    # System 1 theory, entropy & calibration math
│   └── COMPONENTS.md                      # Comprehensive port & parameter reference
├── tests/                                 # Unit & pipeline test suites
│   ├── conftest.py                        # Standalone harness & lfx mock fixtures
│   └── test_components.py                 # Automated verification tests
├── pyproject.toml                         # Packaging & dependencies
├── requirements.txt                       # Python dependencies
├── CONTRIBUTING.md                        # Guide for adding new questions and flows
└── README.md                              # Main guide (this document)
```

---

## 🧩 Component Overview

| Component | Category | Description | Primary Outputs |
|---|---|---|---|
| **`Kev Choice Question (GUI)`** | Question Spec | Builds a categorical choice spec (2 to 255 options) with descriptions, negative criteria (`not_for`), and confidence gates. | `question_spec_out` |
| **`Kev Noul Question (Yes/No GUI)`** | Question Spec | Calibrated binary proposition returning $P(\text{yes}) \in [0, 1]$ with dedicated 3-lane probability thresholds. | `question_spec_out` |
| **`Kev Score Question (Manual Values GUI)`** | Question Spec | Multi-criteria scoring with user-defined manual weights strictly validated to accumulate to `1.0`. | `question_spec_out` |
| **`Kev System 1 Core Engine`** | Core Engine | Dispatches all chained questions to `/v1/systemone` in parallel. Features local defaults, confidence analysis, and offline mock simulator. | `overall_route`, `all_decisions_data`, `decisions_table`, `agent_summary` |
| **`Kev Question Result Extractor`** | Routing | Selects a single `question_id` and field from the engine output to wire directly into downstream Conditional Routers. | `question_route`, `question_details` |

---

## 🔄 How It Works: The Chaining Architecture

Rather than wiring a web of connections across the canvas, question nodes utilize an **upstream chaining pattern**:

```
[ Choice Question Node ]
          │  (emits question_spec_out)
          ▼
[ Noul (Yes/No) Question Node ]  ◄── upstream_questions
          │  (bundles both questions)
          ▼
[ Score Question Node ]          ◄── upstream_questions
          │  (bundles all three questions)
          ▼
[ JEV System 1 Core Engine ]     ◄── question_specs
          │
          ├──► Overall Route Message  ──────► [ Primary Conditional Router ]
          ├──► Agent Summary Text     ──────► [ Chat Output / Logger ]
          ├──► Decisions Table        ──────► [ Data Table / Inspector ]
          │
          └──► All Decisions Data
                     │
                     ├──► [ Extractor: 'department' ]    ──► [ Router: Dept ]
                     ├──► [ Extractor: 'requests_refund' ] ──► [ Router: Refund ]
                     └──► [ Extractor: 'weighted_score' ] ──► [ Router: Score ]
```

1. **Chain Question Nodes**: Connect `question_spec_out` into the next question's `upstream_questions`.
2. **Connect to Core Engine**: Connect the final question node into `question_specs` on the Core Engine.
3. **Single Parallel Call**: The Core Engine automatically unpacks the entire bundle and evaluates all questions simultaneously against the incoming state.
4. **Extract & Route**: Connect `all_decisions_data` to as many `Kev Question Result Extractor` nodes as you have questions!

---

## 🚀 Quick Start Guide

### Option 1: Drag & Drop into Langflow (Fastest)

1. Open your Langflow UI (`http://localhost:7860`).
2. Drag and drop any `.json` file from `flows/components/` directly onto the canvas to add that component.
3. Or open **Settings > Import Flow** and select `flows/examples/jev_multi_question_routing_pipeline.json` to load the full working pipeline!

### Option 2: Install as a Python Package

Install the dependencies:
```bash
pip install -r requirements.txt
```

You can import and use the components in custom Langflow scripts:
```python
from components.questions.choice_question import KevChoiceQuestionNode
from components.questions.noul_question import KevNoulQuestionNode
from components.engine.core_engine import KevSystemOneCoreEngine

# 1. Configure Choice Question
q_choice = KevChoiceQuestionNode()
q_choice.question_id = "department"
q_choice.instructions = "Which department handles this customer inquiry?"
q_choice.choice_options_table = [
    {"option_key": "billing", "description": "Payment issues, invoices, charges"},
    {"option_key": "support", "description": "Technical errors, crashes, bugs"},
]
choice_bundle = q_choice.build_choice_question()

# 2. Configure Noul Question and chain
q_noul = KevNoulQuestionNode()
q_noul.question_id = "is_urgent"
q_noul.instructions = "Is this issue mission-critical or urgent?"
q_noul.upstream_questions = choice_bundle
chained_bundle = q_noul.build_noul_question()

# 3. Evaluate with Core Engine
engine = KevSystemOneCoreEngine()
engine.question_specs = chained_bundle
engine.state_text = "Urgent: Our production server is down after the latest payment failed!"
engine.mock_mode_if_unreachable = True  # Allows offline evaluation

route = engine.build_overall_route()
print("Evaluated Route:", route.text)
```

---

## 🛠️ Configuration & Credentials

### Local Self-Hosted KEV
By default, the Core Engine connects to a local Kev daemon:
- **Base URL**: `http://kev-server:8009` (or `http://localhost:8009`)
- **Model**: `kev-latest` (or `kev-4b`, `kev-9b`, `kev-27b`)
- **API Key**: `local-kev` (no remote auth required)

### TypeSafe Cloud / Hosted JEV
To connect to TypeSafe Cloud:
- **Base URL**: `https://api.typesafe.ai`
- **Model**: `jev-latest`
- **API Key**: Your TypeSafe API Key

### Offline Testing (Mock Simulator)
Toggle `Fallback to Mock Simulator if Server Unreachable` (`mock_mode_if_unreachable: True`) on the Core Engine node. If the server is offline or unreachable, the engine will run internal keyword-heuristic simulations and emit schema-accurate decisions without crashing the flow.

---

## 🧪 Testing & Validation

Run the test suite using `pytest`:
```bash
pytest tests/ -v
```

The test suite validates:
- [x] Syntax and initialization of all component classes.
- [x] Schema compliance for Choice, Noul, and Score question specifications.
- [x] Upstream question bundling and chaining logic.
- [x] Strict validation of manual score values summing to $1.0$.
- [x] Offline mock engine evaluation and confidence scoring.
- [x] Multi-question result extraction.

---

## 📈 Scalability & Extending the Repository

This repository is structured for seamless scaling as you add new components and workflows:
- **New Question Types** (e.g., Ranking, Multi-Select): Add them to `components/questions/` and register them in `components/questions/__init__.py`.
- **New Flow Pipelines**: Export flows from Langflow and save them in `flows/examples/`.
- **Architecture Guidelines**: See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details on interface contracts and chaining conventions.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
