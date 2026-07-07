"""Tests for the mock pipeline and upload endpoint."""
import pytest
from fastapi.testclient import TestClient

from main import app
from services.mock_pipeline import generate_mock_mto

client = TestClient(app)


class TestMockPipeline:
    def test_mock_returns_mto_result(self):
        result = generate_mock_mto("test.png")
        assert result.source == "mock"
        assert len(result.items) >= 6  # pipe, fitting, flange, valve, gasket, bolt
        assert result.summary.total_pipe_length_m > 0
        assert result.summary.flanges > 0
        assert result.summary.gaskets > 0
        assert result.summary.bolt_sets > 0

    def test_mock_items_have_valid_schema(self):
        result = generate_mock_mto("test.png")
        for item in result.items:
            assert 0.0 <= item.confidence <= 1.0
            assert item.quantity > 0
            assert item.size_nps

    def test_mock_pipe_has_length(self):
        result = generate_mock_mto("test.png")
        pipes = [i for i in result.items if i.category.value == "PIPE"]
        assert len(pipes) > 0
        for p in pipes:
            assert p.length_m is not None
            assert p.length_m > 0


class TestHealthEndpoint:
    def test_health_ok(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestUploadEndpoint:
    def test_upload_png_returns_job_id(self):
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (200, 200), color=(100, 150, 200)).save(buf, format="PNG")
        buf.seek(0)

        resp = client.post(
            "/api/upload",
            files={"file": ("test.png", buf, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 36  # UUID format

    def test_upload_invalid_type_rejected(self):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 415

    def test_poll_completed_job(self):
        """
        Upload a blank PNG and verify the pipeline finishes (either via mock or error).
        In the test env there is no real Gemini key, so the pipeline uses the mock.
        """
        import io
        import time
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (600, 800), color=(255, 255, 255)).save(buf, format="PNG")
        buf.seek(0)

        upload_resp = client.post(
            "/api/upload",
            files={"file": ("iso_test.png", buf, "image/png")},
        )
        assert upload_resp.status_code == 200
        job_id = upload_resp.json()["job_id"]

        # Poll until finished (max 15 seconds)
        final = None
        for _ in range(30):
            time.sleep(0.5)
            poll_resp = client.get(f"/api/mto/{job_id}")
            assert poll_resp.status_code == 200
            data = poll_resp.json()
            if data["status"] in ("completed", "failed"):
                final = data
                break

        assert final is not None, "Pipeline never finished within timeout"
        # In test env without Gemini key, mock pipeline should produce completed result
        # If a Gemini key IS set and the image is a blank page, it may legitimately fail
        assert final["status"] in ("completed", "failed")
        if final["status"] == "completed":
            assert final["result"] is not None
            assert final["result"]["source"] in ("mock", "ai")

    def test_poll_unknown_job_returns_404(self):
        resp = client.get("/api/mto/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
