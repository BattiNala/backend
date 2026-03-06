"""
Custom exceptions for S3-related errors."""


class S3Exception(Exception):
    """Base exception for S3-related errors."""


class S3UploadException(S3Exception):
    """Exception raised when an error occurs during S3 upload."""

    def __init__(self, message: str = "Failed to upload file to S3"):
        self.message = message
        super().__init__(self.message)


class S3DownloadException(S3Exception):
    """Exception raised when an error occurs during S3 download."""

    def __init__(self, message: str = "Failed to download file from S3"):
        self.message = message
        super().__init__(self.message)


class S3DeleteException(S3Exception):
    """Exception raised when an error occurs during S3 delete."""

    def __init__(self, message: str = "Failed to delete file from S3"):
        self.message = message
        super().__init__(self.message)


class S3ConnectionException(S3Exception):
    """Exception raised when an error occurs during S3 connection."""

    def __init__(self, message: str = "Failed to connect to S3"):
        self.message = message
        super().__init__(self.message)
