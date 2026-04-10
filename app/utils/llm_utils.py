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
Evaluate the attached image(s) for a user-submitted issue report.

Issue type: {issue_type}
Issue description: {issue_description}
Number of attached images: {image_count}

Scoring rubric:
- 90-100: Images are highly relevant and strongly support the reported issue.
- 70-89: Images are relevant and reasonably support the issue, with minor ambiguity.
- 40-69: Images are somewhat relevant but weak, incomplete, generic, or unclear.
- 10-39: Images are minimally relevant, suspiciously generic, or poorly matched to the report.
- 0-9: Images are missing, clearly irrelevant, or unusable.

Evaluate:
1. Relevance to the reported issue
2. Visual consistency with the description
3. Clarity and usefulness of the evidence
4. Signs the image may be generic, misleading, staged, duplicated, or low-value evidence

Return valid JSON with exactly these fields:
{{
  "score": <integer 0 to 100>,
  "verdict": "<one of: strong_match, moderate_match, weak_match, irrelevant_or_unusable>",
  "rationale": "<short explanation, max 40 words>"
}}
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
