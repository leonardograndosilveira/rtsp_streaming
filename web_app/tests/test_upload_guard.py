import pytest

from web_app.upload_guard import sanitize_upload_filename


class TestSanitizeUploadFilename:
    def test_plain_name_unchanged(self):
        assert sanitize_upload_filename("video.mp4") == "video.mp4"

    def test_strips_directory_traversal(self):
        assert sanitize_upload_filename("../../etc/passwd") == "passwd"

    def test_strips_absolute_path(self):
        assert sanitize_upload_filename("/abs/path/x.mp4") == "x.mp4"

    def test_strips_nested_relative(self):
        assert sanitize_upload_filename("foo/bar.mp4") == "bar.mp4"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            sanitize_upload_filename("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError):
            sanitize_upload_filename("   ")

    def test_rejects_dotdot_only(self):
        with pytest.raises(ValueError):
            sanitize_upload_filename("../..")

    def test_rejects_dot(self):
        with pytest.raises(ValueError):
            sanitize_upload_filename(".")

    def test_error_has_context(self):
        with pytest.raises(ValueError, match="filename"):
            sanitize_upload_filename("")
