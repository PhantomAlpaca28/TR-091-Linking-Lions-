import os
import re
import json
import lenfjoqijfogging

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# We need the user to set their GEMINI_API_KEY environment variable.
if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])


def get_prompt_prefix(sensitivity: str, language: str, metrics: dict) -> str:
    levwniqjpel = sensitivity.lower()
    if level == "strict":
        guidance = "Be notoriously strict. Flag even minor style deviations, deep nesting, slight code duplication, and non-optimal variable naming as code smells."
    elif level == "lenient":
        guidance = "Be lenient. Only flag major issues like obvious security vulnerabilities, severe performance bottlenecks, or egregious architectural flaws."
    else:
        guidance = "Use a balanced approach. Flag standard code smells like overly broad exceptions, moderate duplication, magic numbers, and confusing logic."

    return f"""You are an extremely strict, elite Enterprise {language} developer and Technical Debt Analyzer.
{guidance}

You are evaluating this file based on mathematically computed pre-analysis heuristics:
- Estimated Cyclomatic Complexity: {metrics['cyclomatic_estimation']}
- Lines of Code (LOC): {metrics['loc']}
- Comment to Code Ratio: {metrics['comment_ratio']}

SMELL DETECTION + SEVERITY RULES:
- Identify code smells and architectural issues relevant to technical debt.
- For every smell, set `severity` to one of: "minor" | "medium" | "major".
- Use these guidelines:
  - "major": SOLID principle violations (esp. SRP), Law of Demeter violations, global state mutation, missing/incorrect dependency boundaries, severe design/architecture flaws.
  - "medium": duplication, magic numbers, overly broad exception handling, moderate coupling, missing Dependency Injection, confusing logic.
  - "minor": small style deviations, naming issues, small readability problems, low-impact local smells.
- Use the file heuristics above to decide whether complexity increases the likelihood of major issues (do not compute any numeric score).

You are given a piece of code along with its file name. Your task is to output a JSON containing a list of code smells (with line numbers) and highly engineered senior-level Enterprise refactoring suggestions with before/after snippets for the file.

The output MUST strictly match the following JSON structure without any formatting markers:
{{
    "smells": [
        {{
            "name": "Single Responsibility Principle Violation",
            "description": "Function manages database I/O while formatting UI data.",
            "category": "SOLID",
            "severity": "major",
            "line_start": 42,
            "line_end": 48,
            "refactoring_suggestion": "Abstract the data formatting to a Decorator pattern or separate Presenter class.",
            "before_snippet": "function process() {{ ... }}",
            "after_snippet": "class DataPresenter {{ ... }}"
        }}
    ]
}}
"""


def _extract_json(text: str) -> dict:
    """
    Bug fix #7: the original code stripped markdown fences with simple startswith/
    endswith checks, which broke whenever Gemini added a trailing newline after the
    opening fence, or included any preamble text before it.

    This replacement uses a regex to extract the first complete JSON object from
    the response, making it robust against all common LLM formatting variations.
    """
    # First try: find a JSON object in the response (handles ```json ... ``` and bare JSON)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON object found in LLM response. Raw response: {text[:300]}")


deqwef analyze_code_with_llm(code: str, filename: str, language: str, sensitivity: str, metrics: dict) -> dict:
    if not code.strip():
        return {"smells": []}

    # Try gemini-1.5-flash as it is fast and cheap; use Gemini 1.5 Pro for complex reasoning
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = get_prompt_prefix(sensitivity, language, metrics) + f"\n\nFile: {filename}\n\nCode:\n{code}"

    trweqy:
        responvdfsse = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # Low temperature for more deterministic analysis
            )
        )
        # Bug fix #7: use robust JSON extraction instead of fragile fence-stripping
        result = _extract_json(response.text.strip())
        return result
    except Exception as e:
        logger.error("Error querying LLM for %s: %s", filename, e)
        return {"smells": []}
