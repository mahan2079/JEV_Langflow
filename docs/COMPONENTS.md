# JEV / KEV Langflow Component Reference Guide

Comprehensive parameter specifications, input ports, output ports, and usage patterns for all components included in this library.

---

## 1. JEV System 1 Core Engine

- **Type**: Engine / Evaluator
- **Display Name**: `Kev System 1 Core Engine`
- **Class**: `KevSystemOneCoreEngine`
- **Icon**: `Cpu`

### Description
Central parallel evaluation engine for TypeSafe JEV and Local KEV System 1 models. Accepts multiple question specifications, packages them into a single `/v1/systemone` request, executes confidence analysis, and routes decisions.

### Inputs
| Input Name | Type | Default | Description |
|---|---|---|---|
| `base_url` | String | `http://kev-server:8009` | Endpoint URL. Default points to local self-hosted Kev. |
| `model_name` | Dropdown | `kev-latest` | Model version: `kev-latest`, `jev-latest`, `kev-4b`, `kev-9b`, `kev-27b`, `kev-0.8b`, `custom`. |
| `custom_model_name` | String | `kev-latest` | Custom model tag when `model_name` is set to `custom`. |
| `api_key` | SecretStr | `local-kev` | Bearer token for TypeSafe Cloud or protected endpoints. |
| `question_specs` | Data / Bundle | *Required* | Question specification bundle from upstream question nodes. |
| `state_text` | String | `""` | Primary input text or message to evaluate. |
| `state_data` | Data | `None` | Optional structured JSON / dictionary context. |
| `state_format_mode` | Dropdown | `auto` | Formatting mode: `auto`, `text_only`, `json_state`, `combined`. |
| `extra_state_fields` | Dict | `{}` | Key-value dictionary appended to state context. |
| `overall_route_mode` | Dropdown | `first_question_route` | Overall route output mode: `first_question_route`, `combined_key_value_routes`, `json_routes_map`. |
| `enable_long_context`| Boolean | `False` | Sends `X-System-One-Long-Context: true` header for large documents. |
| `mock_mode_if_unreachable` | Boolean | `False` | Fallback to deterministic mock simulator if server is offline. |
| `timeout_seconds` | Float | `15.0` | HTTP request timeout in seconds. |
| `max_retries` | Integer | `2` | Number of retry attempts on network failures. |

### Outputs
| Output Name | Type | Description |
|---|---|---|
| `overall_route` | Message | Primary route label string for direct wiring to Conditional Routers. |
| `all_decisions_data` | JSON / Data | Complete dictionary containing all question decisions and metadata. Connect to Extractors. |
| `decisions_table` | Table / DataFrame | Tabular view of every question, probability distribution, confidence, and route. |
| `agent_summary` | Message | Formatted human/agent-readable summary of evaluations. |

---

## 2. JEV Choice Question (GUI)

- **Type**: Question Spec Builder
- **Display Name**: `Kev Choice Question (GUI)`
- **Class**: `KevChoiceQuestionNode`
- **Icon**: `ListFilter`

### Description
Visual GUI builder for categorical selection questions (supporting between 2 and 255 mutually exclusive options). Allows configuring option keys, descriptive criteria, negative boundaries (`not_for`), and confidence gates.

### Inputs
| Input Name | Type | Default | Description |
|---|---|---|---|
| `question_id` | String | `department` | Unique identifier for this question (e.g. `intent`, `category`). |
| `instructions` | String | *Required* | Clear instruction prompt guiding the classification. |
| `choice_options_table` | Table | Table | Table with columns: `option_key`, `description`, `not_for`, `route_alias`. |
| `min_confidence` | Float | `0.65` | Minimum confidence threshold in $[0.0, 1.0]$. |
| `low_confidence_label` | String | `HUMAN_REVIEW` | Route label emitted if confidence is below threshold. |
| `upstream_questions` | Data | `None` | Connect an earlier question node to chain them into a single bundle. |

### Outputs
| Output Name | Type | Description |
|---|---|---|
| `question_spec_out` | JSON / Data | Emits the single question spec and cumulative bundle for downstream nodes or Core Engine. |

---

## 3. JEV Noul Question (Yes/No GUI)

- **Type**: Question Spec Builder
- **Display Name**: `Kev Noul Question (Yes/No GUI)`
- **Class**: `KevNoulQuestionNode`
- **Icon**: `CheckCircle2`

### Description
Visual builder for binary (Yes/No) propositions. Returns calibrated probability $P(\text{yes})$ with dedicated True/False boundary criteria and 3-lane threshold routing.

### Inputs
| Input Name | Type | Default | Description |
|---|---|---|---|
| `question_id` | String | `requests_refund` | Unique question identifier. |
| `instructions` | String | *Required* | Binary proposition (e.g. *Does the user report a security vulnerability?*). |
| `true_criteria` | Multiline | `""` | Specific boundary criteria that strictly qualify as YES. |
| `false_criteria` | Multiline | `""` | Specific boundary criteria that strictly qualify as NO. |
| `yes_threshold` | Float | `0.70` | Probability cutoff above which YES route is chosen ($P \ge \text{cutoff}$). |
| `no_threshold` | Float | `0.30` | Probability cutoff below which NO route is chosen ($P \le \text{cutoff}$). |
| `yes_route_label` | String | `YES` | Label emitted when $P(\text{yes}) \ge \text{yes_threshold}$. |
| `no_route_label` | String | `NO` | Label emitted when $P(\text{yes}) \le \text{no_threshold}$. |
| `uncertain_route_label` | String | `HUMAN_REVIEW` | Label emitted when probability falls between thresholds. |
| `upstream_questions` | Data | `None` | Optional chained question bundle input. |

### Outputs
| Output Name | Type | Description |
|---|---|---|
| `question_spec_out` | JSON / Data | Emits the Noul spec and cumulative bundle. |

---

## 4. JEV Score Question (Manual Values GUI)

- **Type**: Question Spec Builder
- **Display Name**: `Kev Score Question (Manual Values GUI)`
- **Class**: `KevScoreQuestionNode`
- **Icon**: `Sliders`

### Description
Visual builder for weighted multi-criteria scoring where custom numeric weights (e.g., `shipping: 0.25`, `quality: 0.50`) accumulate to `1.0`.

### Inputs
| Input Name | Type | Default | Description |
|---|---|---|---|
| `question_id` | String | `weighted_score` | Unique question identifier. |
| `instructions` | String | *Required* | Scoring instructions. |
| `manual_levels_table` | Table | Table | Table with columns: `item_name`, `manual_value`, `description`. |
| `strict_sum_to_one` | Boolean | `True` | Validates that $\sum \text{manual\_value} == 1.0$. |
| `score_calculation_mode` | Dropdown | `weighted_sum_probabilities` | Modes: `weighted_sum_probabilities`, `argmax_level_value`, `softmax_expectation`. |
| `routing_mode` | Dropdown | `winning_item_name` | Route mode: `winning_item_name`, `threshold_cutoff`, `level_bracket`. |
| `score_cutoff` | Float | `0.50` | Threshold used if `routing_mode` is `threshold_cutoff`. |
| `high_score_label` | String | `HIGH_SCORE` | Label emitted when score $\ge$ cutoff. |
| `low_score_label` | String | `LOW_SCORE` | Label emitted when score $<$ cutoff. |
| `min_confidence` | Float | `0.55` | Confidence threshold. |
| `low_confidence_label` | String | `HUMAN_REVIEW` | Fallback route label on low confidence. |
| `upstream_questions` | Data | `None` | Optional chained question bundle input. |

### Outputs
| Output Name | Type | Description |
|---|---|---|
| `question_spec_out` | JSON / Data | Emits the Score spec and cumulative bundle. |

---

## 5. JEV Question Result Extractor

- **Type**: Routing & Post-Processing
- **Display Name**: `Kev Question Result Extractor`
- **Class**: `KevQuestionResultExtractor`
- **Icon**: `Split`

### Description
Pulls individual question decisions out of the Core Engine's bundled results so each parallel question can be routed independently via downstream Conditional Routers.

### Inputs
| Input Name | Type | Default | Description |
|---|---|---|---|
| `decisions_data` | JSON / Data | *Required* | Connect to `All Decisions Data` output from the Core Engine. |
| `target_question_id` | String | `""` | The question ID to extract (e.g. `department`, `is_urgent`). |
| `extract_field` | Dropdown | `route_label` | Field to emit: `route_label`, `raw_decision`, `score_custom_scaled`, `score_native`, `nearest_level_tag`, `peak_level_tag`, `policy_lane`. |

### Outputs
| Output Name | Type | Description |
|---|---|---|
| `question_route` | Message | The extracted string value formatted as a Langflow `Message`. |
| `question_details` | JSON / Data | The complete decision dictionary for the target question. |
