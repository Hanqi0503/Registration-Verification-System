import io
import json
import pytest
from unittest import mock

import importlib.util
import sys
from pathlib import Path


# Import the image_utils module directly from source to avoid importing the
# full `app` package during tests (which may require optional deps).
HERE = Path(__file__).resolve().parents[1] / 'app' / 'utils' / 'image_utils.py'
spec = importlib.util.spec_from_file_location('image_utils', str(HERE))
image_utils = importlib.util.module_from_spec(spec)
sys.modules['image_utils'] = image_utils
import types

# Create a minimal dummy `app.config.config` module so the module import
# in image_utils (from app.config.config import Config) does not pull in the
# rest of the application and optional dependencies.
config_mod = types.ModuleType('app.config.config')

class DummyConfig:
    JOTFORM_API_KEY = None
    NINJA_API_KEY = None
    NINJA_API_URL = None

config_mod.Config = DummyConfig

sys.modules['app'] = types.ModuleType('app')
sys.modules['app.config'] = types.ModuleType('app.config')
sys.modules['app.config.config'] = config_mod

# Now execute the module with the dummy config in place.
spec.loader.exec_module(image_utils)


def test_extract_image_url_with_bytes():
    html = b"<html><body><img src=\"/images/foo.jpg\"></body></html>"
    assert image_utils.extract_image_url(html) == "/images/foo.jpg"


def test_extract_image_url_no_image():
    html = "<html><body><p>No images here</p></body></html>"
    with pytest.raises(ValueError):
        image_utils.extract_image_url(html)


@mock.patch('image_utils.requests.get')
def test_fetch_image_bytes_image_content_type(mock_get):
    mock_resp = mock.Mock()
    mock_resp.raise_for_status = mock.Mock()
    mock_resp.headers = {'Content-Type': 'image/png'}
    mock_resp.content = b'PNGDATA'
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    result = image_utils.fetch_image_bytes('https://example.com/image.png')
    assert result == b'PNGDATA'


@mock.patch('image_utils.requests.get')
def test_fetch_image_bytes_html_extracts_and_recurses(mock_get):
    # First call returns HTML with an <img src="/img.jpg">
    html_resp = mock.Mock()
    html_resp.raise_for_status = mock.Mock()
    html_resp.headers = {'Content-Type': 'text/html'}
    html_resp.content = b"<img src=\"/img.jpg\">"
    html_resp.status_code = 200

    # Second call returns the image bytes
    img_resp = mock.Mock()
    img_resp.raise_for_status = mock.Mock()
    img_resp.headers = {'Content-Type': 'image/jpeg'}
    img_resp.content = b'JPEGDATA'
    img_resp.status_code = 200

    mock_get.side_effect = [html_resp, img_resp]

    result = image_utils.fetch_image_bytes('https://example.com/page')
    assert result == b'JPEGDATA'


@mock.patch('image_utils.requests.post')
@mock.patch('image_utils.fetch_image_bytes')
def test_ninja_image_to_text_calls_api(mock_fetch, mock_post):
    mock_fetch.return_value = b'IMAGEDATA'
    mock_resp = mock.Mock()
    mock_resp.raise_for_status = mock.Mock()
    mock_resp.json.return_value = {'text': 'hello'}
    mock_post.return_value = mock_resp

    # temporarily set required config
    with mock.patch.object(image_utils.Config, 'NINJA_API_KEY', 'key'), \
        mock.patch.object(image_utils.Config, 'NINJA_API_URL', 'https://api.test'):
        res = image_utils.ninja_image_to_text('https://example.com/img')
        assert res == {'text': 'hello'}

