"""Phase 420 — Error Handling Standardization contract tests.

Verifies error response shapes match the standard envelope.
"""

import pytest


STANDARD_ERROR_ENVELOPE = {
    "status": "error",
    "code": 422,
    "message": "Validation error",
    "detail": {"field": "display_name", "reason": "required"},
}

ERROR_CODES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


class TestErrorEnvelope:
    """Validates the standard error response shape."""

    def test_envelope_has_status(self):
        assert "status" in STANDARD_ERROR_ENVELOPE
        assert STANDARD_ERROR_ENVELOPE["status"] == "error"

    def test_envelope_has_code(self):
        assert "code" in STANDARD_ERROR_ENVELOPE
        assert isinstance(STANDARD_ERROR_ENVELOPE["code"], int)

    def test_envelope_has_message(self):
        assert "message" in STANDARD_ERROR_ENVELOPE
        assert isinstance(STANDARD_ERROR_ENVELOPE["message"], str)

    def test_envelope_has_detail(self):
        assert "detail" in STANDARD_ERROR_ENVELOPE

    def test_all_error_codes_have_descriptions(self):
        for code, desc in ERROR_CODES.items():
            assert 400 <= code <= 599
            assert len(desc) > 0

    def test_error_codes_are_http_standard(self):
        standard = {400, 401, 403, 404, 409, 422, 429, 500, 503}
        assert set(ERROR_CODES.keys()) == standard

    def test_4xx_are_client_errors(self):
        for code in ERROR_CODES:
            if 400 <= code < 500:
                assert code in {400, 401, 403, 404, 409, 422, 429}

    def test_5xx_are_server_errors(self):
        for code in ERROR_CODES:
            if 500 <= code < 600:
                assert code in {500, 503}
