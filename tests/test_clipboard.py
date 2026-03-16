import subprocess
import sys
import types
from unittest.mock import MagicMock, patch

from local_first_common.clipboard import get_clipboard


def _mock_pyperclip(text: str):
    """Inject a fake pyperclip module into sys.modules."""
    mod = types.ModuleType("pyperclip")
    mod.paste = lambda: text
    return mod


class TestGetClipboard:
    def test_pbpaste_success(self):
        mock_result = MagicMock()
        mock_result.stdout = "clipboard content\n"
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = get_clipboard()
        mock_run.assert_called_once_with(
            ["pbpaste"], capture_output=True, text=True, timeout=5
        )
        assert result == "clipboard content"

    def test_falls_back_to_pyperclip_on_file_not_found(self):
        fake = _mock_pyperclip("pyperclip content")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch.dict(sys.modules, {"pyperclip": fake}):
                result = get_clipboard()
        assert result == "pyperclip content"

    def test_falls_back_to_pyperclip_on_timeout(self):
        fake = _mock_pyperclip("timed out content")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pbpaste", 5)):
            with patch.dict(sys.modules, {"pyperclip": fake}):
                result = get_clipboard()
        assert result == "timed out content"
