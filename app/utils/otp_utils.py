import secrets
import hmac
import hashlib


class OtpUtils:
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
        candidate_hash = OtpUtils.hash_otp(otp_input, salt)
        return hmac.compare_digest(candidate_hash, stored_hash)

    @staticmethod
    def is_otp_expired(expires_at) -> bool:
        """
        Check if the OTP is expired based on the current time and the expires_at timestamp.
        """
        from datetime import datetime, timezone

        return datetime.now(timezone.utc) > expires_at
