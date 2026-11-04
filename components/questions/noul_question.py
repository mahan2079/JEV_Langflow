from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataInput,
    FloatInput,
    MultilineInput,
    Output,
    StrInput,
)
from lfx.schema.data import Data


class KevNoulQuestionNode(Component):
    """Visual GUI Builder for a Kev/Jev System 1 'noul' (Yes/No Probability) Question."""

    display_name: str = "Kev Noul Question (Yes/No GUI)"
    description: str = (
        "Visual builder for a Noul (Yes/No) binary proposition. Returns calibrated P(yes) "
        "in [0, 1] with dedicated True/False boundary boxes and 3-lane probability thresholds."
    )
    icon: str = "CheckCircle2"
    name: str = "KevNoulQuestionNode"

    inputs = [
        StrInput(
            name="question_id",
            display_name="Question ID",
            value="requests_refund",
            info="Unique identifier for this Noul question (e.g., 'requests_refund', 'is_urgent', 'has_pii').",
            required=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="Yes/No Proposition or Question",
            value="Does this message explicitly ask for a refund, charge reversal, or billing credit?",
            info="Phrase as a clear Yes/No question or affirmative statement where YES = true.",
            required=True,
        ),
        MultilineInput(
            name="true_criteria",
            display_name="What Counts as YES (True Criteria - Optional)",
            value="The sender asks for money back, a refund, duplicate charge reversal, or account credit.",
            info=(
                "Describe what counts as 'true' (Yes). Leave both YES and NO boxes blank "
                "if the statement alone is sufficient."
            ),
            required=False,
        ),
        MultilineInput(
            name="false_criteria",
            display_name="What Counts as NO (False Criteria - Optional)",
            value="The sender reports a bug, asks an invoice question, or cancels future renewal without asking for money back.",
            info="Describe what counts as 'false' (No).",
            required=False,
        ),
        FloatInput(
            name="yes_threshold",
            display_name="YES Probability Cutoff (>=)",
            value=0.70,
            info="If P(yes) >= this value, routes to the YES Route Label.",
            advanced=False,
        ),
        FloatInput(
            name="no_threshold",
            display_name="NO Probability Cutoff (<=)",
            value=0.30,
            info="If P(yes) <= this value, routes to the NO Route Label. Values in between route to Uncertain.",
            advanced=False,
        ),
        StrInput(
            name="yes_route_label",
            display_name="YES Route Label",
            value="YES",
            info="Route label emitted when P(yes) >= YES Probability Cutoff.",
            advanced=True,
        ),
        StrInput(
            name="no_route_label",
            display_name="NO Route Label",
            value="NO",
            info="Route label emitted when P(yes) <= NO Probability Cutoff.",
            advanced=True,
        ),
        StrInput(
            name="uncertain_route_label",
            display_name="Uncertain / Middle-Band Route Label",
            value="HUMAN_REVIEW",
            info="Route label emitted when P(yes) is between NO Cutoff and YES Cutoff.",
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
            display_name="Noul Question Spec",
            name="question_spec_out",
            method="build_noul_question",
        ),
    ]

    def build_noul_question(self) -> Data:
        q_id = (self.question_id or "noul_question").strip() or "noul_question"
        instr = (self.instructions or "").strip()
        true_desc = (self.true_criteria or "").strip()
        false_desc = (self.false_criteria or "").strip()

        if not instr and not (true_desc or false_desc):
            raise ValueError(
                f"Kev Noul Question '{q_id}' requires either Instructions or True/False criteria."
            )

        api_spec: dict[str, Any] = {
            "type": "noul",
            "instructions": instr,
        }
        if true_desc or false_desc:
            api_spec["criteria"] = {
                "true": true_desc,
                "false": false_desc,
            }

        yes_t = float(self.yes_threshold if self.yes_threshold is not None else 0.70)
        no_t = float(self.no_threshold if self.no_threshold is not None else 0.30)
        if no_t > yes_t:
            raise ValueError(
                f"In Kev Noul Question '{q_id}', NO Cutoff ({no_t}) cannot be greater than YES Cutoff ({yes_t})."
            )

        current_entry = {
            "question_id": q_id,
            "api_spec": api_spec,
            "policy": {
                "yes_threshold": yes_t,
                "no_threshold": no_t,
                "yes_route_label": (self.yes_route_label or "YES").strip(),
                "no_route_label": (self.no_route_label or "NO").strip(),
                "uncertain_route_label": (self.uncertain_route_label or "HUMAN_REVIEW").strip(),
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
        self.status = f"Noul '{q_id}' (YES>={yes_t}, NO<={no_t})"

        return Data(
            data={
                "question_id": q_id,
                "api_spec": current_entry["api_spec"],
                "policy": current_entry["policy"],
                "kev_question_bundle": bundle_list,
            },
            text_key="question_id",
        )