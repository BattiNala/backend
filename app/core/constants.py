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


IMAGE_VERIFICATION_SYSTEM_PROMPT = """
You are an image-verification assistant for a user-submitted issue reporting system.

Your task is to assess whether the provided image(s) are relevant and plausibly supportive of
the reported issue.

Important constraints:
- Do NOT claim certainty about real-world authenticity.
- You are NOT doing forensic image authentication.
- Judge only from the visible image content and the issue report details.
- Be conservative when evidence is weak, ambiguous, low quality, or missing.
- Penalize images that are generic, unrelated, stock-like, duplicated, overly blurry, or
 inconsistent with the report.
- Reward images that clearly depict the reported issue, context, and visible supporting details.
- If no images are provided, score very low.
- Output must be valid JSON only.
""".strip()

NORMALIZATION_PROMPT = """
Convert the following image-verification assessment into valid JSON that exactly matches the schema.

Issue type: {issue_type}
Issue description: {issue_description}
Number of attached images: {image_count}

Assessment text:
{raw_text}
""".strip()
