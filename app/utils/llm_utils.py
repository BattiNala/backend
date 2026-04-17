"""
Utility functions for constructing prompts and processing responses
from LLMs in the Battinala application.
"""

import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.logger import get_logger
from app.exceptions.task_exception import VerificationError
from app.schemas.llm_vadiation import ImageVerificationResult, VerificationVerdict

logger = get_logger(__name__)


def build_image_verification_prompt(
    issue_type: str,
    issue_description: str,
    image_count: int,
) -> str:
    """
    Construct a prompt for the LLM to evaluate the relevance and supportiveness of attached images
    for a user-submitted issue report.
    """
    return f"""
You are an image relevance verifier for an issue reporting system.

Your task: Judge how well the image(s) support the reported issue based ONLY on visible content.

Important rules:
- Do NOT assess authenticity or perform forensic analysis.
- Do NOT assume details that are not clearly visible.
- Be conservative: unclear or ambiguous evidence should lower the score.
- A related object alone is NOT enough — the issue itself should be visible or strongly implied.

Inputs:
- Issue type: {issue_type}
- Issue description: {issue_description}
- Number of images: {image_count}

Evaluation steps (internal reasoning):
1. Identify the main visible objects or scene.
2. Check if the reported issue itself is visible (not just a related object).
3. Check for mismatch or contradiction with the report.
4. Assess clarity, usefulness, and specificity of the evidence.

Scoring rubric:
- 0-9: No image, completely irrelevant, or unusable (blur, darkness, wrong subject)
- 10-39: Barely related or generic; issue not visible
- 40-69: Some relevant elements, but issue unclear or weakly supported
- 70-89: Clearly relevant; issue mostly visible with minor ambiguity
- 90-100: Strong, direct, unambiguous visual evidence of the issue

Additional penalties:
- Generic or stock-like images
- Duplicate/redundant images
- Poor quality (blurry, obstructed, tiny subject)
- Weak connection between image and description

Category guidance:
- For ELECTRICITY: expect visible signs like exposed wires, damaged fixtures, unsafe connections,
 sparks, or clearly hazardous wiring context, Fire Hazards.
- A single cable or unclear object without visible hazard = weak evidence.
- For SEWAGE: look for visible leaks, overflowing water, or clear signs of sewage issues.
- A wet patch without clear sewage context = weak evidence.

Output JSON ONLY:
{{
  "score": <integer 0-100>,
  "verdict": "<one of: strong_match, moderate_match, weak_match, irrelevant_or_unusable>",
  "rationale": "<1-2 sentences, based only on visible evidence>"
}}

Verdict mapping:
- 0-39 -> irrelevant_or_unusable
- 40-69 -> weak_match
- 70-89 -> moderate_match
- 90-100 -> strong_match
""".strip()


def image_verification_response_schema() -> dict[str, Any]:
    """JSON schema for structured image verification responses."""
    return {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall relevance and support score for the submitted images.",
            },
            "verdict": {
                "type": "string",
                "enum": [verdict.value for verdict in VerificationVerdict],
                "description": "Categorical assessment of how well the images match the report.",
            },
            "rationale": {
                "type": "string",
                "description": "Short explanation in no more than 40 words.",
            },
        },
        "required": ["score", "verdict", "rationale"],
        "additionalProperties": False,
    }


def extract_json(text: str) -> dict[str, Any]:
    """Attempt to parse JSON from the provided text, with fallback strategies."""
    logger.debug("Extracting JSON from Mistral response text: %s", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise VerificationError("Model did not return valid JSON.") from None

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise VerificationError("Unable to parse JSON from model response.") from exc


def normalize_result(raw: dict[str, Any]) -> ImageVerificationResult:
    """Validate and normalize the raw JSON into an ImageVerificationResult."""
    normalized = raw

    # Some providers occasionally wrap the expected payload in a single extra object.
    while isinstance(normalized, dict) and not {"score", "verdict", "rationale"} <= set(normalized):
        if len(normalized) != 1:
            break
        only_value = next(iter(normalized.values()))
        if not isinstance(only_value, dict):
            break
        normalized = only_value

    try:
        return ImageVerificationResult.model_validate(normalized)
    except ValidationError as exc:
        raise VerificationError(f"Model JSON failed validation: {exc}") from exc
