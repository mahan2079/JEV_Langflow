import json
import math
import os
import time
from typing import Any

import httpx
import pandas as pd
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    NestedDictInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class KevSystemOneCoreEngine(Component):
    """Central parallel execution engine for Local Kev and TypeSafe Jev System 1 models.

    Supports manual-value Score questions (where item weights accumulate to 1.0),
    Choice questions, and Noul (Yes/No) questions in a single parallel /v1/systemone call.
    """

    display_name: str = "Kev System 1 Core Engine"
    description: str = (
        "Evaluates all connected Choice, Manual-Value Score, and Noul GUI Question nodes "
        "in parallel in a single /v1/systemone pass. Configured with Local Kev defaults."
    )
    documentation: str = "https://docs.typesafe.ai/concepts/system-one"
    icon: str = "Cpu"
    name: str = "KevSystemOneCoreEngine"
    priority: int = 1

    inputs = [
        # --- 1. Local Kev Default Endpoint, Model & Auth (Visible on Canvas) ---
        StrInput(
            name="base_url",
            display_name="API Base URL",
            value="http://kev-server:8009",
            info=(
                "Base URL for the System 1 API endpoint. Default is local Kev at "
                "'http://kev-server:8009'. Calls POST {base_url}/v1/systemone."
            ),
            advanced=False,
            required=False,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Version / Alias",
            options=[
                "kev-latest",
                "jev-latest",
                "kev-4b",
                "kev-9b",
                "kev-27b",
                "kev-0.8b",
                "custom",
            ],
            value="kev-latest",
            info="Target model identifier. Default is 'kev-latest' for the local Kev server.",
            real_time_refresh=True,
        ),
        StrInput(
            name="custom_model_name",
            display_name="Custom Model ID",
            value="kev-latest",
            info="Specify a custom model tag when 'Model Version / Alias' is set to 'custom'.",
            show=False,
            advanced=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="TypeSafe / Jev API Key",
            value="local-kev",
            info=(
                "Bearer token. Defaults to 'local-kev' for self-hosted instances (no auth needed). "
                "Required for TypeSafe Cloud."
            ),
            required=False,
            advanced=False,
        ),

        # --- 2. Visual Question Nodes Input ---
        DataInput(
            name="question_specs",
            display_name="Question Specs (Connect GUI Nodes)",
            info=(
                "Connect one or more 'Kev Choice Question', 'Kev Score Question (Manual Values GUI)', "
                "or 'Kev Noul Question' nodes here."
            ),
            is_list=True,
            required=True,
        ),

        # --- 3. Shared State Inputs ---
        MessageTextInput(
            name="state_text",
            display_name="State Text / Message",
            info="Primary text or message to evaluate against all connected questions.",
            tool_mode=True,
            required=False,
        ),
        DataInput(
            name="state_data",
            display_name="State Data / Structured Context",
            info="Optional Data object or list[Data] merged with State Text.",
            required=False,
        ),
        DropdownInput(
            name="state_format_mode",
            display_name="State Format Mode",
            options=[
                "auto",
                "string",
                "json_object",
                "text_array",
            ],
            value="auto",
            info="Controls how 'state' is formatted in the POST /v1/systemone request.",
            advanced=True,
        ),
        NestedDictInput(
            name="extra_state_fields",
            display_name="Additional State Metadata (JSON)",
            info="Optional key-value facts merged into the state JSON object.",
            required=False,
            advanced=True,
        ),

        # --- 4. Primary Route Port Behavior ---
        DropdownInput(
            name="overall_route_mode",
            display_name="Overall Route Output Mode",
            options=[
                "first_question_route",
                "all_clear_or_review",
                "combined_key_value_routes",
                "json_routes_map",
            ],
            value="first_question_route",
            info="Controls what 'Primary / Overall Route' emits for downstream Conditional Routers.",
            advanced=False,
        ),

        # --- 5. Resilience & Offline Testing ---
        FloatInput(
            name="timeout_seconds",
            display_name="Request Timeout (Seconds)",
            value=15.0,
            info="HTTP timeout in seconds for the /v1/systemone call.",
            advanced=True,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            value=2,
            info="Automatic retries on HTTP 429/502/503/504/529 or transient network errors.",
            advanced=True,
        ),
        BoolInput(
            name="enable_long_context",
            display_name="Enable Long Context Header",
            value=False,
            info="Sends 'TypeSafe-Danger-Zone-Long-Context: true' header.",
            advanced=True,
        ),
        BoolInput(
            name="mock_mode_if_unreachable",
            display_name="Fallback to Mock Simulator if Server Unreachable",
            value=False,
            info="If enabled, simulates calibrated responses locally when the Kev server is offline.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Primary / Overall Route",
            name="overall_route",
            method="build_overall_route",
            group_outputs=True,
        ),
        Output(
            display_name="All Decisions Data",
            name="all_decisions_data",
            method="build_all_decisions_data",
            group_outputs=True,
        ),
        Output(
            display_name="Decisions Table",
            name="decisions_table",
            method="build_decisions_table",
            group_outputs=True,
        ),
        Output(
            display_name="Agent Summary",
            name="agent_summary",
            method="build_agent_summary",
            group_outputs=True,
        ),
    ]

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        if field_name == "model_name" and "custom_model_name" in build_config:
            build_config["custom_model_name"]["show"] = field_value == "custom"
        return build_config

    def _resolve_api_key(self) -> str:
        """Resolves the API key with automatic fallback for local Kev instances."""
        key = (self.api_key or "").strip()
        if key:
            return key

        for env_name in ("KEV_API_KEY", "TYPESAFE_API_KEY", "JEV_API_KEY"):
            env_val = os.getenv(env_name, "").strip()
            if env_val:
                return env_val

        base = (self.base_url or "").strip().lower()
        if not base or any(h in base for h in ("kev-server", "localhost", "127.0.0.1", "0.0.0.0")):
            return "local-kev"

        return ""

    def _resolve_model_name(self) -> str:
        """Returns the target model name, defaulting to kev-latest."""
        if self.model_name == "custom":
            custom = (self.custom_model_name or "").strip()
            if not custom:
                raise ValueError("Custom Model ID cannot be empty when set to 'custom'.")
            return custom
        return self.model_name or "kev-latest"

    def _build_state_payload(self) -> Any:
        """Constructs the shared 'state' payload as a string, JSON object, or string array."""
        mode = getattr(self, "state_format_mode", "auto") or "auto"
        raw_text = (self.state_text or "").strip()
        raw_data = self.state_data
        extra_fields = self.extra_state_fields if isinstance(self.extra_state_fields, dict) else {}

        extracted_data: Any = None
        if raw_data is not None:
            if isinstance(raw_data, list):
                extracted_data = [
                    item.data if hasattr(item, "data") else (item.text if hasattr(item, "text") else item)
                    for item in raw_data
                ]
            elif hasattr(raw_data, "data") and isinstance(raw_data.data, dict):
                extracted_data = dict(raw_data.data)
            elif hasattr(raw_data, "text"):
                extracted_data = str(raw_data.text)
            elif isinstance(raw_data, dict):
                extracted_data = dict(raw_data)
            else:
                extracted_data = str(raw_data)

        parsed_text_json: Any = None
        if raw_text and raw_text.startswith(("{", "[")):
            try:
                parsed_text_json = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed_text_json = None

        if mode == "string":
            parts: list[str] = []
            if raw_text:
                parts.append(raw_text)
            if extracted_data is not None:
                parts.append(
                    json.dumps(extracted_data, ensure_ascii=False)
                    if isinstance(extracted_data, (dict, list))
                    else str(extracted_data)
                )
            if extra_fields:
                parts.append(json.dumps(extra_fields, ensure_ascii=False))
            state_str = "\n\n".join(parts).strip()
            if not state_str:
                raise ValueError("State cannot be empty. Connect State Text or State Data.")
            return state_str

        if mode == "text_array":
            arr: list[str] = []
            if raw_text:
                if isinstance(parsed_text_json, list):
                    arr.extend(str(x) for x in parsed_text_json)
                else:
                    arr.append(raw_text)
            if isinstance(extracted_data, list):
                for item in extracted_data:
                    arr.append(
                        json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
                    )
            elif extracted_data is not None:
                arr.append(
                    json.dumps(extracted_data, ensure_ascii=False)
                    if isinstance(extracted_data, dict)
                    else str(extracted_data)
                )
            if extra_fields:
                arr.append(json.dumps(extra_fields, ensure_ascii=False))
            if not arr:
                raise ValueError("State text array cannot be empty.")
            return arr

        if mode == "json_object":
            obj: dict[str, Any] = {}
            if isinstance(extracted_data, dict):
                obj.update(extracted_data)
            elif extracted_data is not None:
                obj["context"] = extracted_data
            if isinstance(parsed_text_json, dict):
                obj.update(parsed_text_json)
            elif raw_text:
                obj["message"] = raw_text
            if extra_fields:
                obj.update(extra_fields)
            if not obj:
                raise ValueError("State JSON object cannot be empty.")
            return obj

        if extra_fields or isinstance(extracted_data, dict) or isinstance(parsed_text_json, dict):
            auto_obj: dict[str, Any] = {}
            if isinstance(extracted_data, dict):
                auto_obj.update(extracted_data)
            elif extracted_data is not None:
                auto_obj["data"] = extracted_data
            if isinstance(parsed_text_json, dict):
                auto_obj.update(parsed_text_json)
            elif raw_text:
                auto_obj["message"] = raw_text
            if extra_fields:
                auto_obj.update(extra_fields)
            return auto_obj

        if isinstance(extracted_data, list):
            auto_list: list[str] = []
            if raw_text:
                auto_list.append(raw_text)
            for item in extracted_data:
                if isinstance(item, dict) and "text" in item and len(item) == 1:
                    auto_list.append(str(item["text"]))
                elif isinstance(item, (dict, list)):
                    auto_list.append(json.dumps(item, ensure_ascii=False))
                else:
                    auto_list.append(str(item))
            return auto_list

        if isinstance(parsed_text_json, list):
            return [str(x) for x in parsed_text_json]

        combined_str = raw_text or (str(extracted_data) if extracted_data is not None else "")
        if not combined_str:
            raise ValueError("State is empty. Connect a Message or Data input to evaluate.")
        return combined_str

    def _collect_question_entries(self) -> list[dict[str, Any]]:
        """Collects all connected GUI Question nodes."""
        raw_inputs = self.question_specs
        if raw_inputs is None:
            raise ValueError(
                "No Question nodes connected! Connect at least one Kev Choice, Kev Score, "
                "or Kev Noul Question node to 'Question Specs'."
            )

        items = raw_inputs if isinstance(raw_inputs, list) else [raw_inputs]
        collected: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for item in items:
            payload = item.data if hasattr(item, "data") and isinstance(item.data, dict) else item
            if not isinstance(payload, dict):
                continue

            if "kev_question_bundle" in payload and isinstance(payload["kev_question_bundle"], list):
                for entry in payload["kev_question_bundle"]:
                    if isinstance(entry, dict) and "question_id" in entry and "api_spec" in entry:
                        q_id = str(entry["question_id"])
                        if q_id in seen_ids:
                            collected = [c for c in collected if c["question_id"] != q_id]
                        seen_ids.add(q_id)
                        collected.append(entry)
            elif "question_id" in payload and "api_spec" in payload:
                q_id = str(payload["question_id"])
                if q_id in seen_ids:
                    collected = [c for c in collected if c["question_id"] != q_id]
                seen_ids.add(q_id)
                collected.append(payload)

        if not collected:
            raise ValueError(
                "Connected input on 'Question Specs' did not contain valid Kev Question specifications."
            )
        return collected

    def _simulate_mock_response(
        self,
        model: str,
        state: Any,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Generates schema-accurate mock responses for offline flow testing."""
        state_text_lower = json.dumps(state, ensure_ascii=False).lower()
        answers: dict[str, Any] = {}

        for q_id, q_spec in questions.items():
            q_type = q_spec["type"]
            if q_type == "choice":
                options = list(q_spec["criteria"].keys())
                weights = []
                for opt in options:
                    desc = json.dumps(q_spec["criteria"].get(opt) or "").lower()
                    hits = sum(
                        1
                        for tok in (opt.lower(), *desc.split()[:10])
                        if len(tok) > 3 and tok.strip('"{}[],.:') in state_text_lower
                    )
                    weights.append(1.0 + hits * 3.5)
                total_w = sum(weights)
                probs = {opt: round(w / total_w, 4) for opt, w in zip(options, weights)}
                top_opt = max(probs, key=lambda k: probs[k])
                probs[top_opt] = round(max(0.0, min(1.0, probs[top_opt] + (1.0 - sum(probs.values())))), 4)
                n_opts = len(options)
                entropy = -sum(p * math.log(p) for p in probs.values() if p > 0)
                max_ent = math.log(n_opts) if n_opts > 1 else 1.0
                conf = round(max(0.0, min(1.0, 1.0 - (entropy / max_ent))), 4)
                answers[q_id] = {
                    "type": "choice",
                    "choice": top_opt,
                    "probabilities": probs,
                    "confidence": conf,
                }
            elif q_type == "score":
                levels = q_spec["criteria"]
                weights = []
                for idx, lvl in enumerate(levels):
                    lvl_str = json.dumps(lvl).lower() if isinstance(lvl, (dict, list)) else str(lvl).lower()
                    hits = sum(
                        1 for tok in lvl_str.split() if len(tok) > 3 and tok.strip('"{}[],.:()') in state_text_lower
                    )
                    weights.append(1.0 + hits * 3.0)
                total_w = sum(weights)
                probs = {str(i): round(w / total_w, 4) for i, w in enumerate(weights)}
                top_idx = max(probs, key=lambda k: probs[k])
                probs[top_idx] = round(max(0.0, min(1.0, probs[top_idx] + (1.0 - sum(probs.values())))), 4)
                weighted_score = round(sum(int(i) * p for i, p in probs.items()), 4)
                n_lvls = len(levels)
                entropy = -sum(p * math.log(p) for p in probs.values() if p > 0)
                max_ent = math.log(n_lvls) if n_lvls > 1 else 1.0
                conf = round(max(0.0, min(1.0, 1.0 - (entropy / max_ent))), 4)
                answers[q_id] = {
                    "type": "score",
                    "score": weighted_score,
                    "legend": {str(i): lvl for i, lvl in enumerate(levels)},
                    "probabilities": probs,
                    "confidence": conf,
                }
            elif q_type == "noul":
                instr_tokens = [
                    t.strip(".,?!`\"'") for t in str(q_spec.get("instructions", "")).lower().split() if len(t) > 3
                ]
                hits = sum(1 for t in instr_tokens if t in state_text_lower)
                p_yes = round(min(0.96, 0.20 + (hits * 0.22)), 4)
                answers[q_id] = {
                    "type": "noul",
                    "noul": p_yes,
                }

        return {
            "model": f"{model} (mock)",
            "answers": answers,
            "usage": {"input_tokens": 64, "output_tokens": len(questions) * 4},
        }

    def _call_jev_api(
        self,
        model: str,
        state: Any,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Calls POST {base_url}/v1/systemone with Local Kev defaults."""
        api_key = self._resolve_api_key()
        if not api_key:
            raise ValueError(
                "Missing API Key for external endpoint. Provide a TypeSafe/Jev API key or point "
                "API Base URL to your local Kev server (http://kev-server:8009 or http://localhost:8009)."
            )

        base = (self.base_url or "http://kev-server:8009").strip().rstrip("/")
        endpoint = base if base.endswith("/v1/systemone") else f"{base}/v1/systemone"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if getattr(self, "enable_long_context", False):
            headers["TypeSafe-Danger-Zone-Long-Context"] = "true"

        payload = {
            "model": model,
            "state": state,
            "questions": questions,
        }

        timeout = float(getattr(self, "timeout_seconds", 15.0) or 15.0)
        max_retries = max(0, int(getattr(self, "max_retries", 2) or 0))

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(endpoint, headers=headers, json=payload)

                if response.status_code == 200:
                    body = response.json()
                    if isinstance(body, dict) and "answers" not in body and isinstance(body.get("data"), dict):
                        return dict(body["data"])
                    return body

                if response.status_code in (429, 502, 503, 504, 529) and attempt < max_retries:
                    time.sleep(min(0.3 * (2**attempt), 4.0))
                    continue

                try:
                    err_detail = response.json()
                except Exception:
                    err_detail = response.text
                raise RuntimeError(
                    f"System 1 API Error (HTTP {response.status_code} at {endpoint}): {err_detail}"
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(0.3 * (2**attempt))
                    continue
                if getattr(self, "mock_mode_if_unreachable", False):
                    return self._simulate_mock_response(model, state, questions)
                raise RuntimeError(
                    f"Could not reach Kev/Jev endpoint at '{endpoint}' after {attempt + 1} attempts: {exc}."
                ) from exc

        raise RuntimeError(f"Request failed: {last_error}")

    def _compute_entropy_confidence(self, prob_list: list[float]) -> float:
        """Fallback normalized Shannon entropy confidence when a local checkpoint omits confidence."""
        n = len(prob_list)
        if n <= 1:
            return 1.0
        total = sum(prob_list)
        if total <= 0:
            return 0.0
        normed = [p / total for p in prob_list if p > 0]
        entropy = -sum(p * math.log(p) for p in normed)
        max_entropy = math.log(n)
        return round(max(0.0, min(1.0, 1.0 - (entropy / max_entropy))), 4)

    def _evaluate_entry(
        self,
        entry: dict[str, Any],
        answers_map: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluates Choice, Manual-Value Score (sum=1.0), and Noul questions."""
        q_id = str(entry["question_id"])
        api_spec = entry["api_spec"]
        policy = entry.get("policy") or {}
        q_type = api_spec["type"]
        raw_ans = answers_map.get(q_id) or {}

        if q_type == "choice":
            criteria_map: dict[str, Any] = api_spec.get("criteria") or {}
            raw_probs: dict[str, Any] = raw_ans.get("probabilities") or {}
            probs: dict[str, float] = {str(k): float(v) for k, v in raw_probs.items()}

            selected_choice = str(raw_ans.get("choice") or "")
            if not selected_choice and probs:
                selected_choice = max(probs, key=lambda k: probs[k])

            raw_conf = raw_ans.get("confidence")
            confidence = (
                float(raw_conf)
                if raw_conf is not None
                else self._compute_entropy_confidence(list(probs.values()))
            )

            top_prob = float(probs.get(selected_choice, 0.0))
            sorted_probs = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
            runner_up = sorted_probs[1][0] if len(sorted_probs) > 1 else None
            margin = round(top_prob - float(sorted_probs[1][1]), 4) if len(sorted_probs) > 1 else 1.0

            min_conf = float(policy.get("min_confidence", 0.65))
            fallback_label = str(policy.get("low_confidence_label", "HUMAN_REVIEW"))
            route_aliases: dict[str, str] = policy.get("route_aliases") or {}

            meets_conf = confidence >= min_conf
            mapped_choice_route = route_aliases.get(selected_choice, selected_choice)
            route_label = mapped_choice_route if meets_conf else fallback_label
            lane = "AUTO_ACT" if meets_conf else "HUMAN_REVIEW"

            return {
                "question_id": q_id,
                "type": "choice",
                "raw_decision": selected_choice,
                "route_label": route_label,
                "lane": lane,
                "primary_metric": round(top_prob, 4),
                "confidence": round(confidence, 4),
                "meets_threshold": meets_conf,
                "manual_score": None,
                "winning_item_name": selected_choice,
                "winning_item_manual_value": None,
                "cumulative_manual_score": None,
                "item_contributions": {},
                "probabilities": probs,
                "matched_description": str(criteria_map.get(selected_choice) or selected_choice),
            }

        if q_type == "score":
            criteria_list: list[Any] = api_spec.get("criteria") or []
            n_levels = len(criteria_list)
            level_tags: list[str] = policy.get("level_tags") or [f"item_{i}" for i in range(n_levels)]
            calc_mode = str(policy.get("score_calculation_mode", "weighted_sum_probabilities"))

            # Retrieve manual values (summing to 1.0); if not provided, distribute evenly so sum == 1.0
            raw_manual_vals = policy.get("manual_values")
            if isinstance(raw_manual_vals, list) and len(raw_manual_vals) == n_levels:
                manual_values = [float(v) for v in raw_manual_vals]
            else:
                manual_values = [round(1.0 / max(1, n_levels), 6) for _ in range(n_levels)]

            if calc_mode == "independent_criteria_accumulation":
                # Each row was evaluated as its own sub-question __sub_{i} in parallel
                prob_vector: list[float] = []
                for idx in range(n_levels):
                    sub_key = f"{q_id}__item_{idx}"
                    sub_ans = answers_map.get(sub_key) or {}
                    p_yes = float(sub_ans.get("noul", 0.0))
                    prob_vector.append(p_yes)

                contributions = {
                    level_tags[i]: round(manual_values[i] * prob_vector[i], 4)
                    for i in range(n_levels)
                }
                labeled_probs = {
                    f"{level_tags[i]} (val={manual_values[i]:.2f})": round(prob_vector[i], 4)
                    for i in range(n_levels)
                }
                accumulated_score = round(sum(contributions.values()), 4)
                peak_idx = max(range(n_levels), key=lambda i: contributions[level_tags[i]])
                winning_tag = level_tags[peak_idx]
                winning_manual_val = round(manual_values[peak_idx], 4)
                cumulative_val = accumulated_score
                # Average directional certainty across the sub-questions
                confidence = round(
                    sum(abs(2.0 * p - 1.0) for p in prob_vector) / max(1, n_levels),
                    4,
                )
                final_manual_score = accumulated_score
            else:
                # Single Kev 'score' primitive call with manual level values
                raw_probs_dict = raw_ans.get("probabilities") or {}
                prob_vector = []
                for idx in range(n_levels):
                    val = raw_probs_dict.get(str(idx))
                    if val is None:
                        val = raw_probs_dict.get(idx)
                    if val is None and idx < len(criteria_list):
                        val = raw_probs_dict.get(str(criteria_list[idx]))
                    prob_vector.append(float(val) if val is not None else 0.0)

                prob_sum = sum(prob_vector)
                if prob_sum > 0:
                    prob_vector = [p / prob_sum for p in prob_vector]

                contributions = {
                    level_tags[i]: round(manual_values[i] * prob_vector[i], 4)
                    for i in range(n_levels)
                }
                labeled_probs = {
                    f"{level_tags[i]} (val={manual_values[i]:.2f})": round(prob_vector[i], 4)
                    for i in range(n_levels)
                }

                weighted_manual_score = round(sum(manual_values[i] * prob_vector[i] for i in range(n_levels)), 4)
                peak_idx = (
                    max(range(n_levels), key=lambda i: prob_vector[i])
                    if prob_sum > 0
                    else 0
                )
                winning_tag = level_tags[peak_idx]
                winning_manual_val = round(manual_values[peak_idx], 4)
                cumulative_val = round(sum(manual_values[: peak_idx + 1]), 4)

                if calc_mode == "winning_item_value":
                    final_manual_score = winning_manual_val
                elif calc_mode == "cumulative_up_to_winner":
                    final_manual_score = cumulative_val
                else:
                    final_manual_score = weighted_manual_score

                raw_conf = raw_ans.get("confidence")
                confidence = (
                    float(raw_conf)
                    if raw_conf is not None
                    else self._compute_entropy_confidence(prob_vector)
                )

            min_conf = float(policy.get("min_confidence", 0.55))
            fallback_label = str(policy.get("low_confidence_label", "HUMAN_REVIEW"))
            routing_mode = str(policy.get("routing_mode", "winning_item_name"))
            score_cutoff = float(policy.get("score_cutoff", 0.50))
            high_label = str(policy.get("high_score_label", "HIGH_SCORE"))
            low_label = str(policy.get("low_score_label", "LOW_SCORE"))

            meets_conf = confidence >= min_conf
            if not meets_conf:
                lane = "HUMAN_REVIEW"
                route_label = fallback_label
            elif routing_mode == "threshold_pass_fail":
                if final_manual_score >= score_cutoff:
                    lane = "AUTO_ACT"
                    route_label = high_label
                else:
                    lane = "BELOW_SCORE_THRESHOLD"
                    route_label = low_label
            elif routing_mode == "manual_score_value":
                lane = "AUTO_ACT"
                route_label = f"{final_manual_score:.4f}".rstrip("0").rstrip(".")
            else:
                lane = "AUTO_ACT"
                route_label = winning_tag

            matched_desc = str(criteria_list[peak_idx]) if peak_idx < len(criteria_list) else ""

            return {
                "question_id": q_id,
                "type": "score",
                "raw_decision": final_manual_score,
                "route_label": route_label,
                "lane": lane,
                "primary_metric": final_manual_score,
                "confidence": round(confidence, 4),
                "meets_threshold": meets_conf,
                "manual_score": final_manual_score,
                "winning_item_name": winning_tag,
                "winning_item_manual_value": winning_manual_val,
                "cumulative_manual_score": cumulative_val,
                "manual_values_map": {level_tags[i]: manual_values[i] for i in range(n_levels)},
                "item_contributions": contributions,
                "probabilities": labeled_probs,
                "matched_description": matched_desc,
                # Backward-compatible keys for KevQuestionResultExtractor
                "score_custom_scaled": final_manual_score,
                "score_normalized_pct": round(final_manual_score * 100.0, 2),
                "score_native": final_manual_score,
                "nearest_level_tag": winning_tag,
                "peak_level_tag": winning_tag,
            }

        if q_type == "noul":
            noul_prob = float(raw_ans.get("noul", 0.0))
            yes_thresh = float(policy.get("yes_threshold", 0.70))
            no_thresh = float(policy.get("no_threshold", 0.30))
            yes_label = str(policy.get("yes_route_label", "YES"))
            no_label = str(policy.get("no_route_label", "NO"))
            uncertain_label = str(policy.get("uncertain_route_label", "HUMAN_REVIEW"))

            directional_certainty = round(abs(2.0 * noul_prob - 1.0), 4)

            if noul_prob >= yes_thresh:
                raw_decision = "YES"
                route_label = yes_label
                lane = "AUTO_ACT"
                meets = True
            elif noul_prob <= no_thresh:
                raw_decision = "NO"
                route_label = no_label
                lane = "REJECT_OR_NO"
                meets = True
            else:
                raw_decision = "UNCERTAIN"
                route_label = uncertain_label
                lane = "HUMAN_REVIEW"
                meets = False

            return {
                "question_id": q_id,
                "type": "noul",
                "raw_decision": raw_decision,
                "route_label": route_label,
                "lane": lane,
                "primary_metric": round(noul_prob, 4),
                "confidence": directional_certainty,
                "meets_threshold": meets,
                "manual_score": round(noul_prob, 4),
                "winning_item_name": raw_decision,
                "winning_item_manual_value": None,
                "cumulative_manual_score": None,
                "item_contributions": {},
                "probabilities": {"true": round(noul_prob, 4), "false": round(1.0 - noul_prob, 4)},
                "matched_description": f"P(yes)={noul_prob:.2f} [YES>={yes_thresh}, NO<={no_thresh}]",
            }

        raise ValueError(f"Unsupported question type: {q_type}")

    def _execute_once(self) -> dict[str, Any]:
        """Executes the batched parallel /v1/systemone request once and caches the result."""
        cache_key = "_kev_core_engine_result"
        if hasattr(self, "ctx") and isinstance(self.ctx, dict) and cache_key in self.ctx:
            return self.ctx[cache_key]
        if hasattr(self, "_cached_result") and self._cached_result is not None:
            return self._cached_result

        model = self._resolve_model_name()
        state = self._build_state_payload()
        entries = self._collect_question_entries()

        questions_payload: dict[str, dict[str, Any]] = {}
        for entry in entries:
            q_id = str(entry["question_id"])
            api_spec = entry["api_spec"]
            policy = entry.get("policy") or {}

            # If a Score node is set to 'independent_criteria_accumulation', expand each item
            # into a parallel Noul check so each item's manual_value * P(item) accumulates to 1.0
            if (
                api_spec.get("type") == "score"
                and policy.get("score_calculation_mode") == "independent_criteria_accumulation"
            ):
                base_instr = str(api_spec.get("instructions") or "")
                descriptions = api_spec.get("criteria") or []
                tags = policy.get("level_tags") or []
                for idx, desc in enumerate(descriptions):
                    tag_name = tags[idx] if idx < len(tags) else f"item_{idx}"
                    questions_payload[f"{q_id}__item_{idx}"] = {
                        "type": "noul",
                        "instructions": f"{base_instr} — Specifically regarding '{tag_name}': {desc}",
                    }
            else:
                questions_payload[q_id] = api_spec

        raw_response = self._call_jev_api(model=model, state=state, questions=questions_payload)
        answers_map: dict[str, Any] = raw_response.get("answers") or {}

        evaluations: dict[str, dict[str, Any]] = {}
        for entry in entries:
            q_id = str(entry["question_id"])
            evaluations[q_id] = self._evaluate_entry(entry, answers_map)

        first_q_id = str(entries[0]["question_id"])
        first_eval = evaluations[first_q_id]
        any_review = any(ev["lane"] == "HUMAN_REVIEW" for ev in evaluations.values())

        bundle = {
            "model": raw_response.get("model", model),
            "endpoint": (self.base_url or "http://kev-server:8009").strip(),
            "first_question_id": first_q_id,
            "first_decision": first_eval,
            "all_confident": not any_review,
            "overall_gate": "HUMAN_REVIEW" if any_review else "ALL_CLEAR",
            "routes_by_question": {q_id: ev["route_label"] for q_id, ev in evaluations.items()},
            "evaluations": evaluations,
            "raw_answers": answers_map,
            "usage": raw_response.get("usage", {}),
            "request_state": state,
            "request_questions": questions_payload,
        }

        self._cached_result = bundle
        if hasattr(self, "ctx") and isinstance(self.ctx, dict):
            try:
                self.ctx[cache_key] = bundle
            except Exception:
                pass

        route_pairs = ", ".join(f"{k}:{v}" for k, v in bundle["routes_by_question"].items())
        self.status = f"[{bundle['model']}] {route_pairs}"
        return bundle

    def build_overall_route(self) -> Message:
        """Output 1: Emits the primary or overall route string for Conditional Routers."""
        bundle = self._execute_once()
        mode = getattr(self, "overall_route_mode", "first_question_route") or "first_question_route"

        if mode == "all_clear_or_review":
            text = str(bundle["overall_gate"])
        elif mode == "combined_key_value_routes":
            text = " | ".join(f"{k}={v}" for k, v in bundle["routes_by_question"].items())
        elif mode == "json_routes_map":
            text = json.dumps(bundle["routes_by_question"], ensure_ascii=False)
        else:
            text = str(bundle["first_decision"]["route_label"])

        return Message(text=text, sender="KevCoreEngine", sender_name="Kev Core Router")

    def build_all_decisions_data(self) -> Data:
        """Output 2: Emits the full structured Data object for Kev Question Result Extractors."""
        bundle = self._execute_once()
        return Data(data=bundle, text_key="overall_gate")

    def build_decisions_table(self) -> DataFrame:
        """Output 3: Emits a DataFrame showing manual values, weighted contributions, and routes."""
        bundle = self._execute_once()
        rows: list[dict[str, Any]] = []
        for q_id, ev in bundle["evaluations"].items():
            rows.append(
                {
                    "question_id": q_id,
                    "type": ev["type"],
                    "raw_decision": ev["raw_decision"],
                    "route_label": ev["route_label"],
                    "policy_lane": ev["lane"],
                    "manual_score": ev.get("manual_score"),
                    "winning_item": ev.get("winning_item_name"),
                    "winning_item_manual_value": ev.get("winning_item_manual_value"),
                    "confidence_or_cert": ev["confidence"],
                    "item_contributions": json.dumps(ev.get("item_contributions", {}), ensure_ascii=False),
                    "probabilities": json.dumps(ev["probabilities"], ensure_ascii=False),
                }
            )
        return DataFrame(pd.DataFrame(rows))

    def build_agent_summary(self) -> Message:
        """Output 4: Emits a Markdown report of all parallel decisions and manual weight breakdowns."""
        bundle = self._execute_once()
        lines = [
            f"### Kev System 1 Parallel Decisions (`{bundle['model']}`)",
        ]
        for q_id, ev in bundle["evaluations"].items():
            q_type = ev["type"]
            if q_type == "choice":
                lines.append(
                    f"- **`{q_id}` [Choice]:** `{ev['raw_decision']}` "
                    f"(P={ev['primary_metric']:.2f}, Conf={ev['confidence']:.2f}) "
                    f"-> Route: **`{ev['route_label']}`** ({ev['lane']})"
                )
            elif q_type == "score":
                contribs = ev.get("item_contributions") or {}
                contrib_str = ", ".join(f"{k}: {v:.3f}" for k, v in contribs.items())
                lines.append(
                    f"- **`{q_id}` [Manual Score]:** **`{ev['manual_score']:.4f}`** / `1.00` "
                    f"(Top Item: `{ev['winning_item_name']}` [manual value=`{ev['winning_item_manual_value']}`], "
                    f"Contributions: {{{contrib_str}}}, Conf={ev['confidence']:.2f}) "
                    f"-> Route: **`{ev['route_label']}`** ({ev['lane']})"
                )
            elif q_type == "noul":
                lines.append(
                    f"- **`{q_id}` [Noul]:** `{ev['raw_decision']}` "
                    f"(P(yes)={ev['primary_metric']:.2f}, Certainty={ev['confidence']:.2f}) "
                    f"-> Route: **`{ev['route_label']}`** ({ev['lane']})"
                )
        return Message(text="\n".join(lines), sender="KevCoreEngine", sender_name="Kev Summary")