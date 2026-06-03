import os

from fastapi.testclient import TestClient

from web_app.main import app, UPLOAD_DIR

client = TestClient(app)


class TestStartValidation:
    # Bad port fails in validation BEFORE any subprocess spawn, so these
    # never touch GStreamer.
    def test_rejects_out_of_range_port(self):
        r = client.post("/api/streams/start", json={
            "type": "file", "path": "/v.mp4", "port": 99999, "mount": "/x",
        })
        assert r.status_code == 400
        assert "port" in r.json()["detail"]

    def test_rejects_non_numeric_port(self):
        r = client.post("/api/streams/start", json={
            "type": "file", "path": "/v.mp4", "port": "abc", "mount": "/x",
        })
        assert r.status_code == 400

    def test_requires_type_and_path(self):
        r = client.post("/api/streams/start", json={"type": "file"})
        assert r.status_code == 400


class TestStreamListing:
    def test_list_returns_json_array(self):
        r = client.get("/api/streams")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestStopRouting:
    def test_stop_unknown_port_is_404(self):
        r = client.post("/api/streams/9999/stop")
        assert r.status_code == 404

    def test_probe_unknown_port_is_404(self):
        r = client.get("/api/streams/9999/probe")
        assert r.status_code == 404

    def test_snapshot_unknown_port_is_404(self):
        r = client.get("/api/streams/9999/snapshot")
        assert r.status_code == 404

    def test_stop_all_returns_count(self):
        r = client.post("/api/streams/stop_all")
        assert r.status_code == 200
        assert "stopped" in r.json()


class TestUploadSanitize:
    def test_traversal_filename_reduced_to_basename(self):
        files = {"file": ("../../evil.mp4", b"data", "video/mp4")}
        r = client.post("/api/upload", files=files)
        try:
            assert r.status_code == 200
            assert r.json()["filename"] == "evil.mp4"
            stored = r.json()["path"]
            assert os.path.dirname(stored) == os.path.abspath(UPLOAD_DIR)
        finally:
            os.remove(os.path.join(UPLOAD_DIR, "evil.mp4"))
