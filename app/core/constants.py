"""Constants for the Battinala application."""

from app.core.config import settings

CITIZEN_REGISTER_EMAIL = (
    "Hello {name},\n\n"
    "Thank you for registering as a citizen in Battinala. "
    "Your account is currently pending verification. "
    "Please use the {otp_code} to verify your account.\n\n"
    "Best regards,\n"
    "Battinala Team"
)


ACCOUNR_VERIFICATION_SUCCESS_EMAIL = (
    "Hello {username},\n\n"
    "Congratulations! Your account has been verified. "
    "You can now access all the features of Battinala.\n\n"
    "Best regards,\n"
    "Battinala Team"
)

RESEND_VERIFICATION_BODY = (
    "Hello {username},\n\n"
    "We received a request to resend the verification code for your Battinala account. "
    "Please use the following OTP code to verify your account: {otp_code}\n\n"
    "If you did not request this, please ignore this email.\n\n"
    "Best regards,\n"
    "Battinala Team"
)

PASSWORD_RESET_EMAIL = (
    "Hello {username},\n\n"
    "We received a request to reset your Battinala password. "
    "Use the following OTP code to continue: {otp_code}\n\n"
    "If you did not request this, please ignore this message.\n\n"
    "Best regards,\n"
    "Battinala Team"
)

PASSWORD_RESET_SUCCESS_EMAIL = (
    "Hello {username},\n\n"
    "Your Battinala password has been updated successfully.\n\n"
    "If you did not perform this action, please contact support immediately.\n\n"
    "Best regards,\n"
    "Battinala Team"
)

EMPLOYEE_ACCOUNT_CREATED_EMAIL = (
    "Hello {name},\n\n"
    "An employee account has been created for you in Battinala. "
    "Your username is {username} and changing your password is required on first login.\n\n"
    "Best regards,\n"
    "Battinala Team"
)


MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = getattr(settings, "MISTRAL_MODEL", "mistral-large-latest")


GEMINI_MODEL = getattr(settings, "GEMINI_MODEL", "gemini-3.0-flash")
GEMINI_STRICT_MODEL = getattr(settings, "GEMINI_STRICT_MODEL", "gemini-2.5-flash-lite")
GEMINI_UPLOAD_START_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
GEMINI_INLINE_IMAGE_MAX_BYTES = 4 * 1024 * 1024
GEMINI_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
GEMINI_MAX_RETRIES = 3

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = getattr(settings, "GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_STRICT_MODEL = getattr(settings, "GROQ_STRICT_MODEL", "openai/gpt-oss-20b")


# IMAGE_VERIFICATION_SYSTEM_PROMPT = """
# You are an image-verification assistant for a user-submitted issue reporting system.

# Your task is to assess whether the provided image(s) are relevant and plausibly supportive of
# the reported issue.

# Important constraints:
# - Do NOT claim certainty about real-world authenticity.
# - You are NOT doing forensic image authentication.
# - Judge only from the visible image content and the issue report details.
# - Be conservative when evidence is weak, ambiguous, low quality, or missing.
# - Penalize images that are generic, unrelated, stock-like, duplicated, overly blurry, or
#  inconsistent with the report.
# - Reward images that clearly depict the reported issue, context, and visible supporting details.
# - If no images are provided, score very low.
# - Output must be valid JSON only.
# """.strip()
IMAGE_VERIFICATION_SYSTEM_PROMPT = """
You are an image-relevance verifier for a user-submitted issue reporting system.

Goal:
Evaluate whether the provided image plausibly supports the reported issue,
 based only on visible image content and the issue report.

Scope limits:
- Do not determine whether the image is authentic, edited, staged, or
 truly from the claimed location/time.
- Do not perform forensic analysis.
- Only assess visible relevance and support for the reported issue.
- If evidence is weak, ambiguous, low-quality, or missing, be conservative.

Inputs:
- issue_type: a category such as ELECTRICITY, SEWAGE, etc.
- issue_description: a short free-text user report
- image_count: number of submitted images

Evaluation task:
Score how well the image(s) visually support the reported issue.

Scoring rubric:
- 0-10: irrelevant or unusable
  - no image, unreadable image, extremely blurry, generic object with no connection to report,
  clearly inconsistent with report
- 11-30: very weak support
  - slight thematic overlap but issue is not actually visible; context missing;
    could be many unrelated things
- 31-50: weak match
  - some potentially relevant content is visible, but the reported issue is unclear, ambiguous,
    or unsupported
- 51-70: moderate match
  - image is relevant and plausibly connected to the report, but evidence is incomplete or
  not fully clear
- 71-85: strong match
  - reported issue is clearly visible with useful context
- 86-100: very strong match
  - issue is directly visible, specific, unambiguous, and well supported by image context/details

Decision rules:
- If no image is provided, assign 0-5.
- Penalize heavily for:
  - generic or stock-like imagery
  - unrelated objects/scenes
  - duplicate or near-duplicate images that add no evidence
  - severe blur, darkness, obstruction, or tiny subject
  - mismatch between visible content and issue description
- Reward only visible evidence, not speculation.
- Do not infer hidden details.
- Do not assume that a wire is electrical unless the image visibly suggests that.
- If the image contains an object that could be relevant but
 the hazard/problem itself is not visible, keep the score low to moderate.

Reasoning policy:
Before scoring, silently determine:
1. What objects/scenes are clearly visible?
2. Is the reported issue itself visible, or only a possibly related object?
3. Is there contradiction between the image and the report?
4. How confident is the relevance based only on visible evidence?


Verdict mapping:
- 0-30 -> irrelevant_or_unusable
- 31-50 -> weak_match
- 51-70 -> moderate_match
- 71-100 -> strong_match

Output requirements:
Return valid JSON only with this exact schema:
{
  "score": <integer 0-100>,
  "verdict": "<one of: irrelevant_or_unusable, weak_match, moderate_match, strong_match>",
  "rationale": "<1-3 sentences, grounded only in visible evidence and uncertainty>"
}

Output rules:
- Score must be an integer.
- Rationale must mention only what is visibly present or absent.
- Do not mention authenticity, fraud, EXIF, metadata, or forensic claims.
- Do not use markdown.
""".strip()

NORMALIZATION_PROMPT = """
Convert the following image-verification assessment into valid JSON that exactly matches the schema.

Issue type: {issue_type}
Issue description: {issue_description}
Number of attached images: {image_count}

Assessment text:
{raw_text}
""".strip()
