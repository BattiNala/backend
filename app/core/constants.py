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
