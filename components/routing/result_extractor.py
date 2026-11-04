import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataInput,
    DropdownInput,
    Output,
    StrInput,
)
from lfx.schema.data import Data
from lfx.schema.message import Message


class KevQuestionResultExtractor(Component):
    """Extracts a specific question's route label, score, or probability from the Core Engine's output."""

    display_name: str = "Kev Question Result Extractor"
    description: str = (
        "Selects a single question_id from 'Kev System 1 Core Engine' results so you can "
        "wire each parallel question to its own downstream Conditional Router."
    )
    icon: str = "Split"
    name: str = "KevQuestionResultExtractor"

    inputs = [
        DataInput(
            name="decisions_data",
            display_name="All Decisions Data (From Core Engine)",
            info="Connect the 'All Decisions Data' output from Kev System 1 Core Engine.",
            required=True,
        ),
        StrInput(
            name="target_question_id",
            display_name="Target Question ID",
            value="severity",
            info="Exact Question ID to extract (e.g., 'department', 'severity', 'requests_refund').",
            required=True,
        ),
        DropdownInput(
            name="extract_field",
            display_name="Route Message Field",
            options=[
                "route_label",
                "raw_decision",
                "score_custom_scaled",
                "score_normalized_pct",
                "score_native",
                "nearest_level_tag",
                "peak_level_tag",
                "policy_lane",
            ],
            value="route_label",
            info="Determines which value is emitted as text on the 'Question Route' port.",
        ),
    ]

    outputs = [
        Output(
            display_name="Question Route / Value",
            name="question_route",
            method="extract_route_message",
            group_outputs=True,
        ),
        Output(
            display_name="Question Details Data",
            name="question_details",
            method="extract_question_data",
            group_outputs=True,
        ),
    ]

    def _get_target_evaluation(self) -> dict[str, Any]:
        raw = self.decisions_data
        payload = raw.data if hasattr(raw, "data") and isinstance(raw.data, dict) else raw
        if not isinstance(payload, dict) or "evaluations" not in payload:
            raise ValueError(
                "Invalid input on 'All Decisions Data'. Connect the 'All Decisions Data' port "
                "from Kev System 1 Core Engine."
            )

        evaluations: dict[str, dict[str, Any]] = payload["evaluations"]
        target_id = (self.target_question_id or "").strip()
        if not target_id:
            first_id = next(iter(evaluations.keys()))
            return evaluations[first_id]

        if target_id not in evaluations:
            available = ", ".join(evaluations.keys())
            raise ValueError(
                f"Question ID '{target_id}' not found in Core Engine results. "
                f"Available Question IDs: [{available}]"
            )
        return evaluations[target_id]

    def extract_route_message(self) -> Message:
        ev = self._get_target_evaluation()
        field = self.extract_field or "route_label"
        field_map = {
            "route_label": ev.get("route_label"),
            "raw_decision": ev.get("raw_decision"),
            "score_custom_scaled": ev.get("score_custom_scaled"),
            "score_normalized_pct": ev.get("score_normalized_pct"),
            "score_native": ev.get("score_native"),
            "nearest_level_tag": ev.get("nearest_level_tag"),
            "peak_level_tag": ev.get("peak_level_tag"),
            "policy_lane": ev.get("lane"),
        }
        val = field_map.get(field, ev.get("route_label"))
        text_val = json.dumps(val) if isinstance(val, (dict, list)) else str(val if val is not None else "")
        self.status = f"{ev['question_id']} ({field}) -> {text_val}"
        return Message(text=text_val, sender="KevExtractor", sender_name=f"Kev [{ev['question_id']}]")

    def extract_question_data(self) -> Data:
        ev = self._get_target_evaluation()
        return Data(data=ev, text_key="route_label")