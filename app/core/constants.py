"""Constants for the Battinala application."""

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
