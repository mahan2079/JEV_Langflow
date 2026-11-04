from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataInput,
    FloatInput,
    MultilineInput,
    Output,
    StrInput,
    TableInput,
)
from lfx.schema.data import Data


class KevChoiceQuestionNode(Component):
    """Visual GUI Builder for a Kev/Jev System 1 'choice' (Categorical Selection) Question."""

    display_name: str = "Kev Choice Question (GUI)"
    description: str = (
        "Visual builder for a Choice question (1 to 255 mutually exclusive options). "
        "Configure option keys, descriptions, and exclusion rules via a GUI table."
    )
    icon: str = "ListFilter"
    name: str = "KevChoiceQuestionNode"

    inputs = [
        StrInput(
            name="question_id",
            display_name="Question ID",
            value="department",
            info="Unique identifier for this Choice question (e.g., 'department', 'intent', 'topic').",
            required=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="Choice Question / Instructions",
            value="Which team should handle this customer request?",
            info="Natural-language question telling Kev how to pick among the options below.",
            required=True,
        ),
        TableInput(
            name="choice_options_table",
            display_name="Choice Options Table",
            info=(
                "Define your mutually exclusive options. Leave 'description' blank to send null "
                "when 'option_key' is self-explanatory. Fill 'not_for' to auto-build structured boundary criteria."
            ),
            table_schema=[
                {
                    "name": "option_key",
                    "display_name": "Option Key",
                    "type": "str",
                    "description": "Option name sent to Kev (e.g., billing, technical, account)",
                },
                {
                    "name": "description",
                    "display_name": "What It Covers (Description)",
                    "type": "str",
                    "description": "Description of what belongs in this option (leave blank for null)",
                },
                {
                    "name": "not_for",
                    "display_name": "Not For / Exclusions (Optional)",
                    "type": "str",
                    "description": "Optional boundary rule for what does NOT belong in this option",
                },
                {
                    "name": "route_alias",
                    "display_name": "Custom Route Alias (Optional)",
                    "type": "str",
                    "description": "Optional custom label emitted on the Router if this option wins",
                },
            ],
            value=[
                {
                    "option_key": "billing",
                    "description": "Charges, refunds, invoices, payment failures, and plan changes.",
                    "not_for": "",
                    "route_alias": "",
                },
                {
                    "option_key": "technical",
                    "description": "Bugs, crashes, API errors, outages, and SSO/SCIM integrations.",
                    "not_for": "",
                    "route_alias": "",
                },
                {
                    "option_key": "account",
                    "description": "Login issues, password resets, profile updates, and team permissions.",
                    "not_for": "SSO or SCIM setup, which goes to technical.",
                    "route_alias": "",
                },
                {
                    "option_key": "needs_review",
                    "description": "Ambiguous, multi-issue, or out-of-scope requests needing human triage.",
                    "not_for": "",
                    "route_alias": "",
                },
            ],
            required=True,
        ),
        FloatInput(
            name="min_confidence",
            display_name="Minimum Confidence Threshold",
            value=0.65,
            info="If Kev's choice confidence is below this cutoff, the question routes to Low-Confidence Label.",
            advanced=False,
        ),
        StrInput(
            name="low_confidence_label",
            display_name="Low-Confidence Fallback Label",
            value="HUMAN_REVIEW",
            info="Route label emitted when confidence is below Minimum Confidence Threshold.",
            advanced=False,
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
            display_name="Choice Question Spec",
            name="question_spec_out",
            method="build_choice_question",
        ),
    ]

    def build_choice_question(self) -> Data:
        q_id = (self.question_id or "choice_question").strip() or "choice_question"
        instr = (self.instructions or "").strip()
        if not instr:
            raise ValueError(f"Instructions cannot be empty in Kev Choice Question '{q_id}'.")

        rows = self.choice_options_table or []
        criteria_map: dict[str, Any] = {}
        route_aliases: dict[str, str] = {}

        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("option_key") or "").strip()
            if not key:
                continue
            desc = str(row.get("description") or "").strip()
            not_for = str(row.get("not_for") or "").strip()
            alias = str(row.get("route_alias") or "").strip()

            if alias:
                route_aliases[key] = alias

            if not desc and not not_for:
                criteria_map[key] = None
            elif not_for:
                criteria_map[key] = {
                    "what": desc or key,
                    "not_for": not_for,
                }
            else:
                criteria_map[key] = desc

        if len(criteria_map) < 2:
            raise ValueError(f"Kev Choice Question '{q_id}' requires at least 2 options in the table.")
        if len(criteria_map) > 255:
            raise ValueError(f"Kev Choice Question '{q_id}' exceeds the 255-option limit ({len(criteria_map)}).")

        current_entry = {
            "question_id": q_id,
            "api_spec": {
                "type": "choice",
                "instructions": instr,
                "criteria": criteria_map,
            },
            "policy": {
                "min_confidence": float(self.min_confidence if self.min_confidence is not None else 0.65),
                "low_confidence_label": (self.low_confidence_label or "HUMAN_REVIEW").strip(),
                "route_aliases": route_aliases,
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
        self.status = f"Choice '{q_id}' ({len(criteria_map)} options)"

        return Data(
            data={
                "question_id": q_id,
                "api_spec": current_entry["api_spec"],
                "policy": current_entry["policy"],
                "kev_question_bundle": bundle_list,
            },
            text_key="question_id",
        )