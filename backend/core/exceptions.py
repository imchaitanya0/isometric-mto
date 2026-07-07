"""Custom exception classes for the MTO pipeline."""


class MissingAPIKeyError(Exception):
    """Raised when GEMINI_API_KEY is not configured."""
    def __init__(self):
        super().__init__(
            "No Gemini API key configured. Running in mock mode. "
            "Set GEMINI_API_KEY in backend/.env to enable real AI extraction."
        )


class CorruptImageError(Exception):
    """Raised when the uploaded file cannot be decoded as an image."""
    def __init__(self, detail: str = "The uploaded file could not be read as a valid image or PDF."):
        super().__init__(detail)


class FileTooLargeError(Exception):
    """Raised when the uploaded file exceeds the size limit."""
    def __init__(self, size_mb: float, limit_mb: int = 20):
        super().__init__(
            f"File size {size_mb:.1f} MB exceeds the {limit_mb} MB limit. "
            "Please compress or crop the drawing and try again."
        )


class PipelineError(Exception):
    """Generic pipeline processing error."""
    pass
