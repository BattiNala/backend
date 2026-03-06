class OtpResendCooldownException(Exception):
    """Custom exception for OTP resend cooldown."""

    def __init__(self, time_remaining: int):
        self.time_remaining = time_remaining
        super().__init__(
            f"OTP resend is on cooldown. Please wait {time_remaining} seconds before trying again."
        )
