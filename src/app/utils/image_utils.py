from io import BytesIO
from typing import Union
import requests
from bs4 import BeautifulSoup
from PIL import Image

from app.config.config import Config

def ninja_image_to_text(imgURL):
    """
    Converts the image at img_url to text using the API.
    """
    image = fetch_image_bytes(imgURL)

    files = {'image': image}

    headers = {
        'X-Api-Key': Config.NINJA_API_KEY
    }

    r = requests.post(Config.NINJA_API_URL, files=files, headers=headers)
    return r.json()

def extract_image_url(html_content: Union[str, bytes]) -> str:
    """
    Extract the first image `src` URL found in the provided HTML content.

    Args:
        html_content: HTML markup as a string or bytes.

    Returns:
        The image URL string extracted from the HTML.

    Raises:
        ValueError: If no <img> tag with a `src` attribute is found.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return img_tag['src']
    raise ValueError("No image URL found in the provided HTML.")


def fetch_image_bytes(image_url: str) -> bytes:
    """
    Download an image from `image_url` and return its bytes.

    If `image_url` points to an HTML page, this function will extract the first
    image URL from that page and attempt to download the image instead.

    The function will append the configured JotForm API key as a query
    parameter if present.

    Args:
        image_url: The URL of the image or a page that contains the image.

    Returns:
        Binary image data.

    Raises:
        ValueError: If the response cannot be handled as an image.
        requests.HTTPError: On non-success HTTP responses.
    """
    # Safely append API key if it's configured.
    if Config.JOTFORM_API_KEY:
        sep = '&' if '?' in image_url else '?'
        full_url = f"{image_url}{sep}apiKey={Config.JOTFORM_API_KEY}"
    else:
        full_url = image_url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/58.0.3029.110 Safari/537.3"
        )
    }
    response = requests.get(full_url, headers=headers)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise

    content_type = response.headers.get('Content-Type', '')
    # If the server returned an image Content-Type, return it directly.
    if 'image' in content_type:
        return response.content

    # If we got HTML, try to parse it and find an image element.
    if 'text/html' in content_type:
        image_page_url = extract_image_url(response.content)
        if not image_page_url.startswith('http'):
            from urllib.parse import urljoin

            image_page_url = urljoin(image_url, image_page_url)
        return fetch_image_bytes(image_page_url)

    # Some servers return image bytes without an image/ content-type; try to
    # open with PIL as a last resort when status is 200.
    if response.status_code == 200:
        image = Image.open(BytesIO(response.content))
        buf = BytesIO()
        image.save(buf, format='JPEG')
        return buf.getvalue()

    raise ValueError(f"Unable to handle content type: {content_type}")