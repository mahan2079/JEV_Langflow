# Contributing to JEV Langflow

Thank you for your interest in expanding the JEV/KEV System 1 Langflow ecosystem! This project is designed to be highly modular and extensible. Whether you are adding a new question builder, an evaluation post-processor, an automated calibration router, or a full end-to-end example flow, this guide covers the architectural standards.

---

## 🏗️ Architecture & Component Philosophy

Every component in this repository adheres to the **Langflow Component Framework** (`lfx` or `langflow.custom.custom_component.component`):

1. **Independent Visual Builders**:
   Question nodes (`choice`, `noul`, `score`) do not make HTTP requests themselves. Instead, they format questions into standardized API specification payloads (`api_spec`) coupled with client routing policies (`policy`).
2. **Question Bundling & Chaining**:
   Each question node supports an `upstream_questions` input. When chaining node A into node B, node B gathers prior entries into `kev_question_bundle`. This allows passing any number of questions into a single input on the Core Engine!
3. **Unified Execution Engine**:
   `KevSystemOneCoreEngine` aggregates all questions and sends a **single** `/v1/systemone` POST request. This eliminates network roundtrips, preserves global context, and returns high-confidence probabilities in parallel.
4. **Targeted Routing**:
   `KevQuestionResultExtractor` unbundles the decisions data so that individual questions can drive separate conditional branches or downstream agents.

---

## 📂 Repository Structure

```
├── components/                # Python source implementations
│   ├── engine/                # Core engines and API evaluators
│   ├── questions/             # Question spec visual builders
│   └── routing/               # Result extractors, routers, formatters
├── flows/                     # Flow JSON files ready to drag & drop
│   ├── components/            # Single-node component exports (.json)
│   └── examples/              # Complete multi-node example pipelines (.json)
├── tests/                     # Validation scripts and mocked flow tests
├── docs/                      # Deep-dive architecture and design specifications
```

---

## ➕ Adding a New Component

Follow these steps to add a new component:

### Step 1: Write the Python Component
Place your component in the appropriate subdirectory under `components/`:
- If it's a question type (e.g., `Ranking`, `Multi-select`): `components/questions/`
- If it evaluates or calls an API: `components/engine/`
- If it filters, routes, or extracts results: `components/routing/`

Follow Langflow's standard typing and component structure:
```python
from lfx.custom.custom_component.component import Component
from lfx.io import StrInput, Output, DataInput
from lfx.schema.data import Data

class MyNewComponent(Component):
    display_name: str = "My New Component"
    description: str = "Clear, descriptive summary of what this node does."
    icon: str = "Sparkles"
    name: str = "MyNewComponent"

    inputs = [
        StrInput(name="custom_param", display_name="Custom Parameter", value="default"),
    ]

    outputs = [
        Output(name="result_data", display_name="Result Data", method="process"),
    ]

    def process(self) -> Data:
        # Business logic here
        return Data(data={"status": "ok"})
```

### Step 2: Export Single-Node JSON (Optional but Recommended)
Langflow allows users to import components by dragging a `.json` file directly onto the canvas. To create one:
1. Load your component in Langflow or use a template.
2. Export the node as JSON and save it in `flows/components/<Component Name>.json`.

### Step 3: Register in `components/__init__.py`
Export the new class in `components/__init__.py` and the sub-package's `__init__.py`.

---

## 🌊 Adding a New Workflow / Pipeline

To add a pre-built example workflow:
1. Build and verify the workflow inside the Langflow UI.
2. Ensure mock mode or clear credentials so the flow runs out-of-the-box for community users.
3. Export the Flow JSON from Langflow (`Settings` -> `Export`).
4. Save the flow inside `flows/examples/` with a descriptive name, e.g.:
   `flows/examples/customer_support_triage_pipeline.json`
5. Add an entry to the **Example Workflows** table in `README.md` with:
   - Name and purpose
   - Questions evaluated
   - Downstream branches

---

## 🧪 Testing Guidelines

Before committing:
1. Verify Python syntax and imports:
   ```bash
   python3 -m py_compile components/questions/*.py components/engine/*.py components/routing/*.py
   ```
2. Run validation tests:
   ```bash
   python3 -m pytest tests/
   ```
3. Test JSON validity:
   ```bash
   python3 -c "import json, glob; [json.load(open(f)) for f in glob.glob('flows/**/*.json', recursive=True)]"
   ```

---

## 💬 Code Style & Conventions

- Use standard Python typing (`list[str]`, `dict[str, Any]`, `Optional[float]`).
- Keep UI labels concise and informative.
- Include sensible default values for all inputs so nodes work right away when dragged onto the canvas.
- Ensure error messages guide the user with actionable instructions (e.g. indicating which field was missing or misconfigured).
