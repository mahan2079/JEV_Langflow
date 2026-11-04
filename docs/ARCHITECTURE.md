# JEV & KEV System 1 Architecture for Langflow

This document details the architectural foundation, communication protocol, calibration mechanisms, and operational workflows behind the JEV/KEV System 1 Langflow components.

---

## 1. What is System 1 AI?

In cognitive psychology (Daniel Kahneman's *Thinking, Fast and Slow*), **System 1** represents fast, intuitive, automatic, and calibrated decision-making, whereas **System 2** represents slow, deliberative reasoning.

Traditional LLMs act primarily as uncalibrated generative engines:
- They generate open-ended text tokens sequentially.
- They exhibit confidence miscalibration and hallucination.
- Evaluating multiple dimensions requires multiple serialized prompts or massive prompt templates with fragile JSON schemas.

**TypeSafe JEV & Local KEV System 1** models are purpose-built classification, probability, and scoring models:
1. **Calibrated Probabilities**: Every categorical selection, binary proposition, or scoring rubric returns mathematically sound probabilities in $[0, 1]$.
2. **Deterministic Confidence & Entropy**: System 1 computes normalized Shannon entropy across candidate distributions to quantify model uncertainty before any downstream execution occurs.
3. **Single-Pass Parallelism**: The `/v1/systemone` endpoint accepts an arbitrary bundle of questions simultaneously, evaluating all questions against the state in one pass.

---

## 2. Global Pipeline Architecture

Below is the execution model within a Langflow canvas:

```
[ Canvas Input: Message / Data / Context ]
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 QUESTION SPECIFICATION NODES                │
│                                                             │
│   ┌──────────────────────────┐                              │
│   │ JEV Choice Question      │ (1 to 255 categorical items) │
│   └────────────┬─────────────┘                              │
│                ▼ upstream_questions                         │
│   ┌──────────────────────────┐                              │
│   │ JEV Noul Question        │ (Calibrated Yes/No P(yes))   │
│   └────────────┬─────────────┘                              │
│                ▼ upstream_questions                         │
│   ┌──────────────────────────┐                              │
│   │ JEV Score Question       │ (Manual weights sum to 1.0)  │
│   └────────────┬─────────────┘                              │
└────────────────┼────────────────────────────────────────────┘
                 │
                 ▼ question_specs (Bundled Payload)
┌─────────────────────────────────────────────────────────────┐
│               JEV SYSTEM 1 CORE ENGINE                      │
│                                                             │
│  1. Unpacks question bundle & validates constraints         │
│  2. Resolves state (text, JSON, structured context)         │
│  3. Submits POST /v1/systemone (or Mock Simulator)          │
│  4. Computes Shannon entropy & policy lane thresholds       │
│  5. Calculates manual weighted scores & winning items       │
└──────┬──────────────────────┬─────────────────────────┬─────┘
       │                      │                         │
       ▼                      ▼                         ▼
 [Primary Route]     [All Decisions Data]        [Decisions Table]
       │                      │
       │                      ├──────────────────────────┐
       │                      ▼                          ▼
       │         ┌────────────────────────┐  ┌────────────────────────┐
       │         │ Question Extractor #1  │  │ Question Extractor #2  │
       │         │ (target: 'department') │  │ (target: 'is_urgent')  │
       │         └───────────┬────────────┘  └───────────┬────────────┘
       │                     │                           │
       ▼                     ▼                           ▼
[Conditional Router] [Conditional Router]     [Conditional Router]
```

---

## 3. Question Spec Bundling Mechanism

To maintain clean wiring on Langflow canvas, question nodes do not require individual connections to the Core Engine:
- Node 1 (`JEV Choice Question`) outputs `question_spec_out`.
- Node 2 (`JEV Noul Question`) accepts Node 1 on `upstream_questions`.
- Node 2 merges Node 1's bundle with its own specification, emitting `kev_question_bundle`.
- Node 3 (`JEV Score Question`) chains Node 2, and outputs the entire chain directly to `question_specs` on the Core Engine!

The Core Engine automatically unpacks either a single question or an arbitrary array of bundled questions, de-duplicating by `question_id`.

---

## 4. Calibration & Confidence Evaluation

### 4.1 Categorical Choice Entropy
For a Choice question with $N$ options where option probabilities are $p_1, p_2, \dots, p_N$:
$$\text{Entropy } H = -\sum_{i=1}^N p_i \ln(p_i)$$
$$\text{Normalized Entropy } H_{\text{norm}} = \frac{H}{\ln(N)}$$
$$\text{Confidence } C = 1.0 - H_{\text{norm}}$$

If the highest option probability or overall confidence falls below `min_confidence` (default: 0.65), the route label automatically degrades to `low_confidence_label` (`HUMAN_REVIEW`), preventing uncalibrated automated routing.

### 4.2 Noul (Yes/No) Tri-Lane Boundaries
For binary propositions, Noul returns calibrated $P(\text{yes}) \in [0, 1]$:
- **YES Lane**: $P(\text{yes}) \ge \text{yes\_threshold}$ (e.g., $\ge 0.70$) $\rightarrow$ routes to `yes_route_label`.
- **NO Lane**: $P(\text{yes}) \le \text{no\_threshold}$ (e.g., $\le 0.30$) $\rightarrow$ routes to `no_route_label`.
- **Uncertain / Boundary Lane**: $\text{no\_threshold} < P(\text{yes}) < \text{yes\_threshold}$ $\rightarrow$ routes to `uncertain_route_label` (`HUMAN_REVIEW`).

### 4.3 Manual Value Score Questions
Unlike arbitrary integer rubrics, the Manual Values Score node lets domain engineers define custom decimal weights (e.g., `shipping: 0.25, packaging: 0.25, product: 0.30, billing: 0.20`) and enforces that:
$$\sum_{i=1}^K w_i = 1.0$$
The node calculates both:
1. **Weighted Sum**: $\sum (p_i \times w_i)$
2. **Winning Item**: $\arg\max_i (p_i)$ or highest contributing sub-score.

---

## 5. Offline Fallback & Mock Simulator

When testing flows locally or in CI environments without an active GPU cluster or local Kev endpoint, set `mock_mode_if_unreachable: True` on the Core Engine.

The built-in mock simulator:
- Inspects question schemas and incoming state keywords.
- Generates mathematically sound probability distributions satisfying $\sum p_i = 1.0$.
- Produces valid decision objects and table rows matching the live server output format.
