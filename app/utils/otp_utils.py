import secrets
import hmac
import hashlib
from datetime import datetime, timezone


class OtpUtils:
    @staticmethod
    def handle_otp_generation(otp_length: int = 6) -> tuple[str, bytes, bytes]:
        """
        Handle OTP generation with input validation,salt gen and hash.
        """

        otp_code = OtpUtils.generate_otp(otp_length)
        otp_salt = OtpUtils.generate_salt()
        otp_hash = OtpUtils.hash_otp(otp_code, otp_salt)
        return otp_code, otp_salt, otp_hash

    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """
        Generate a secure numeric OTP of the specified length.
        """

        if length <= 0:
            raise ValueError("length must be greater than 0")

        upper_bound = 10**length
        return f"{secrets.randbelow(upper_bound):0{length}d}"

    @staticmethod
    def generate_salt(length: int = 16) -> bytes:
        """
        Generate a cryptographically secure random salt.
        """

        return secrets.token_bytes(length)

    @staticmethod
    def hash_otp(otp: str, salt: bytes) -> bytes:
        """
        Hash OTP using HMAC-SHA256 with the salt as key.
        """
        # Accept both str and bytes for otp
        if isinstance(otp, str):
            otp_bytes = otp.encode()
        else:
            otp_bytes = otp
        return hmac.new(salt, otp_bytes, hashlib.sha256).digest()

    @staticmethod
    def verify_otp(otp_input: str, salt: bytes, stored_hash: bytes) -> bool:
        """
        Verify OTP using constant-time comparison.
        """
        if OtpUtils.is_otp_expired(stored_hash):
            return False
        candidate_hash = OtpUtils.hash_otp(otp_input, salt)
        return hmac.compare_digest(candidate_hash, stored_hash)

    @staticmethod
    def is_otp_expired(expires_at) -> bool:
        """
        Check if the OTP is expired based on the current time and the expires_at timestamp.
        """

        return datetime.now(timezone.utc) > expires_at

    @staticmethod
    def is_resend_available(resend_available_at) -> tuple[bool, int]:
        """
        Check if the OTP resend is available based on the current time and the resend_available_at timestamp.
        """
        time_remaining = 0

        available = datetime.now(timezone.utc) >= resend_available_at
        if not available:
            time_remaining = (resend_available_at - datetime.now(timezone.utc)).seconds
        return available, time_remaining
