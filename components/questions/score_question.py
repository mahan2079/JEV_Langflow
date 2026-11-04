from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    FloatInput,
    MultilineInput,
    Output,
    StrInput,
    TableInput,
)
from lfx.schema.data import Data


class KevScoreQuestionNode(Component):
    """Visual GUI Builder for a Manual-Valued Kev/Jev Score Question where item values sum to 1.0.

    Replaces integer rubric levels (0, 1, 2...) with user-defined manual values
    (e.g., shipping = 0.25, packaging = 0.25, product_quality = 0.30, billing = 0.20)
    and validates that the sum of all manual values equals 1.0.
    """

    display_name: str = "Kev Score Question (Manual Values GUI)"
    description: str = (
        "Assign manual numeric weights (e.g., shipping: 0.25) to each scored item or level. "
        "Validates that all manual values accumulate to 1.0."
    )
    icon: str = "Sliders"
    name: str = "KevScoreQuestionNode"

    inputs = [
        StrInput(
            name="question_id",
            display_name="Question ID",
            value="weighted_score",
            info="Unique identifier for this Score question (e.g., 'order_score', 'shipping_eval').",
            required=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="Scoring Question / Instructions",
            value="Evaluate the state against each weighted item below.",
            info=(
                "Instructions telling Kev what to evaluate. Use backticks (e.g., `message`) "
                "to reference specific fields when State is a JSON object."
            ),
            required=True,
        ),
        TableInput(
            name="manual_levels_table",
            display_name="Manual Value Items (Sum Must Equal 1.0)",
            info=(
                "Define 2 to 10 items with manual numeric values that accumulate to 1.0 "
                "(for example: 0.25 + 0.25 + 0.30 + 0.20 = 1.00)."
            ),
            table_schema=[
                {
                    "name": "item_name",
                    "display_name": "Item / Level Name",
                    "type": "str",
                    "description": "Identifier or route tag for this item (e.g., shipping, packaging)",
                },
                {
                    "name": "manual_value",
                    "display_name": "Manual Value (0.0 - 1.0)",
                    "type": "float",
                    "description": "Manual weight assigned to this item. All rows must sum to 1.0.",
                },
                {
                    "name": "description",
                    "display_name": "Criteria Description (Sent to Kev)",
                    "type": "str",
                    "description": "What counts for this item/level when Kev evaluates the state",
                },
            ],
            value=[
                {
                    "item_name": "shipping",
                    "manual_value": 0.25,
                    "description": "Shipping speed, carrier handling, tracking updates, and on-time delivery.",
                },
                {
                    "item_name": "packaging",
                    "manual_value": 0.25,
                    "description": "Box integrity, protective materials, and item condition upon arrival.",
                },
                {
                    "item_name": "product_quality",
                    "manual_value": 0.30,
                    "description": "Product build quality, accuracy to specifications, and defect-free operation.",
                },
                {
                    "item_name": "billing_support",
                    "manual_value": 0.20,
                    "description": "Pricing accuracy, invoice clarity, and responsiveness of customer support.",
                },
            ],
            required=True,
        ),
        DropdownInput(
            name="score_calculation_mode",
            display_name="Manual Score Calculation Mode",
            options=[
                "weighted_sum_probabilities",
                "independent_criteria_accumulation",
                "winning_item_value",
                "cumulative_up_to_winner",
            ],
            value="weighted_sum_probabilities",
            info=(
                "'weighted_sum_probabilities': single Kev score call returning Sum(manual_value_i * P_i); "
                "'independent_criteria_accumulation': evaluates each item independently (Yes/No P_i) and "
                "accumulates Sum(manual_value_i * P_i) up to 1.0; "
                "'winning_item_value': returns the exact manual_value of the highest-probability item; "
                "'cumulative_up_to_winner': accumulates manual values from row 1 up to the winning row."
            ),
            real_time_refresh=True,
        ),
        BoolInput(
            name="strict_sum_to_one",
            display_name="Strictly Enforce Sum == 1.0",
            value=True,
            info=(
                "When enabled (default), raises an error if the Manual Value column does not "
                "sum to 1.0. When disabled, automatically normalizes values so they sum to 1.0."
            ),
            advanced=False,
        ),
        DropdownInput(
            name="routing_mode",
            display_name="Route Output Mode",
            options=[
                "winning_item_name",
                "threshold_pass_fail",
                "manual_score_value",
            ],
            value="winning_item_name",
            info=(
                "'winning_item_name' emits the winning item's name (e.g., 'shipping'); "
                "'threshold_pass_fail' emits HIGH_SCORE / LOW_SCORE based on Score Cutoff; "
                "'manual_score_value' emits the computed numeric score (e.g., '0.685')."
            ),
            real_time_refresh=True,
        ),
        FloatInput(
            name="score_cutoff",
            display_name="Score Cutoff (0.0 to 1.0)",
            value=0.50,
            info="Cutoff between 0.0 and 1.0 used when Route Output Mode is 'threshold_pass_fail'.",
            show=False,
        ),
        StrInput(
            name="high_score_label",
            display_name="High Score Route Label",
            value="HIGH_SCORE",
            info="Route label emitted when computed manual score >= Score Cutoff.",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="low_score_label",
            display_name="Low Score Route Label",
            value="LOW_SCORE",
            info="Route label emitted when computed manual score < Score Cutoff.",
            show=False,
            advanced=True,
        ),
        FloatInput(
            name="min_confidence",
            display_name="Minimum Confidence Threshold",
            value=0.55,
            info="If confidence is below this cutoff, routes to the Low-Confidence Fallback Label.",
            advanced=False,
        ),
        StrInput(
            name="low_confidence_label",
            display_name="Low-Confidence Fallback Label",
            value="HUMAN_REVIEW",
            info="Route label emitted when confidence is below Minimum Confidence Threshold.",
            advanced=True,
        ),
        DataInput(
            name="upstream_questions",
            display_name="Chain Previous Questions (Optional)",
            info="Optionally chain another Kev Question node here, or wire all Question nodes directly to the Core Engine.",
            is_list=True,
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Score Question Spec",
            name="question_spec_out",
            method="build_score_question",
        ),
    ]

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        if field_name == "routing_mode":
            is_thresh = field_value == "threshold_pass_fail"
            for f_name in ("score_cutoff", "high_score_label", "low_score_label"):
                if f_name in build_config:
                    build_config[f_name]["show"] = is_thresh
        return build_config

    def _parse_and_validate_rows(self, q_id: str) -> tuple[list[str], list[float], list[str]]:
        """Parses the GUI table and validates that all manual_value entries accumulate to 1.0."""
        rows = self.manual_levels_table or []
        item_names: list[str] = []
        manual_values: list[float] = []
        descriptions: list[str] = []

        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            name = str(row.get("item_name") or "").strip() or f"item_{idx}"
            desc = str(row.get("description") or "").strip() or name
            raw_val = row.get("manual_value")

            if raw_val is None or str(raw_val).strip() == "":
                raise ValueError(
                    f"Row {idx + 1} ('{name}') in Kev Score Question '{q_id}' is missing a 'manual_value'."
                )
            try:
                val = float(raw_val)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Row {idx + 1} ('{name}') in '{q_id}' has an invalid float for 'manual_value': {raw_val}"
                ) from exc

            if val < 0.0:
                raise ValueError(
                    f"Row {idx + 1} ('{name}') in '{q_id}' has a negative manual_value ({val}). "
                    "All manual values must be >= 0.0."
                )

            item_names.append(name)
            manual_values.append(val)
            descriptions.append(desc)

        if len(item_names) < 2:
            raise ValueError(
                f"Kev Score Question '{q_id}' requires at least 2 items in the Manual Value table."
            )
        if len(item_names) > 10 and self.score_calculation_mode != "independent_criteria_accumulation":
            raise ValueError(
                f"Kev's native 'score' primitive supports 2 to 10 items (received {len(item_names)}). "
                "Switch Manual Score Calculation Mode to 'independent_criteria_accumulation' for >10 items."
            )

        total_sum = sum(manual_values)
        strict = bool(getattr(self, "strict_sum_to_one", True))

        if abs(total_sum - 1.0) > 1e-4:
            if strict:
                breakdown = ", ".join(f"{n}={v}" for n, v in zip(item_names, manual_values))
                diff = 1.0 - total_sum
                diff_str = f"+{diff:.4f}" if diff > 0 else f"{diff:.4f}"
                raise ValueError(
                    f"Manual values in '{q_id}' must accumulate to 1.0, but current sum is "
                    f"{total_sum:.4f} ({breakdown}). Adjustment needed to reach 1.0: {diff_str}."
                )
            if total_sum <= 0:
                raise ValueError(f"Sum of manual values in '{q_id}' must be greater than 0.")
            manual_values = [round(v / total_sum, 6) for v in manual_values]

        return item_names, manual_values, descriptions

    def build_score_question(self) -> Data:
        q_id = (self.question_id or "weighted_score").strip() or "weighted_score"
        instr = (self.instructions or "").strip()
        if not instr:
            raise ValueError(f"Instructions cannot be empty in Kev Score Question '{q_id}'.")

        item_names, manual_values, descriptions = self._parse_and_validate_rows(q_id)
        calc_mode = self.score_calculation_mode or "weighted_sum_probabilities"

        current_entry = {
            "question_id": q_id,
            "api_spec": {
                "type": "score",
                "instructions": instr,
                "criteria": descriptions,
            },
            "policy": {
                "is_manual_weighted_score": True,
                "score_calculation_mode": calc_mode,
                "level_tags": item_names,
                "manual_values": manual_values,
                "descriptions": descriptions,
                "routing_mode": self.routing_mode or "winning_item_name",
                "score_cutoff": float(self.score_cutoff if self.score_cutoff is not None else 0.50),
                "high_score_label": (self.high_score_label or "HIGH_SCORE").strip(),
                "low_score_label": (self.low_score_label or "LOW_SCORE").strip(),
                "min_confidence": float(self.min_confidence if self.min_confidence is not None else 0.55),
                "low_confidence_label": (self.low_confidence_label or "HUMAN_REVIEW").strip(),
            },
        }

        bundle_list: list[dict[str, Any]] = []
        if self.upstream_questions:
            up_items = (
                self.upstream_questions
                if isinstance(self.upstream_questions, list)
                else [self.upstream_questions]
            )
            for item in up_items:
                d = item.data if hasattr(item, "data") and isinstance(item.data, dict) else item
                if isinstance(d, dict):
                    if "kev_question_bundle" in d and isinstance(d["kev_question_bundle"], list):
                        bundle_list.extend(d["kev_question_bundle"])
                    elif "question_id" in d and "api_spec" in d:
                        bundle_list.append(d)

        bundle_list.append(current_entry)
        weights_summary = ", ".join(f"{n}={v:.2f}" for n, v in zip(item_names, manual_values))
        self.status = f"Manual Score '{q_id}' (Sum=1.00: {weights_summary})"

        return Data(
            data={
                "question_id": q_id,
                "api_spec": current_entry["api_spec"],
                "policy": current_entry["policy"],
                "kev_question_bundle": bundle_list,
            },
            text_key="question_id",
        )