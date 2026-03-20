"""Tests for http.py — network fetching utilities."""

from unittest.mock import patch, MagicMock
import pytest
import requests
from local_first_common import http


@patch("requests.get")
def test_fetch_url_success(mock_get):
    """Returns HTML content on 200 OK."""
    mock_resp = MagicMock()
    mock_resp.text = "<html>content</html>"
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp
    
    res = http.fetch_url("https://example.com")
    assert res == "<html>content</html>"
    mock_get.assert_called_once()


@patch("requests.get")
def test_fetch_url_failure(mock_get):
    """Raises RuntimeError on request error."""
    mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")
    
    with pytest.raises(RuntimeError):
        http.fetch_url("https://example.com/missing")
    
    mock_get.assert_called_once()
