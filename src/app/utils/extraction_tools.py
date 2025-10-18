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
    headers = {'X-Api-Key': Config.NINJA_API_KEY}
    r = requests.post(Config.NINJA_API_URL, files=files, headers=headers)
    return r.json()


def extract_image_url(html_content: Union[str, bytes]) -> str:
    """
    Extracts the first image `src` URL found in the provided HTML content.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return img_tag['src']
    raise ValueError("No image URL found in the provided HTML.")


def fetch_image_bytes(image_url: str) -> bytes:
    """
    Download an image from `image_url` and return its bytes.
    Supports:
      - Direct image URLs
      - HTML pages containing an <img> tag
    """
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
    response.raise_for_status()

    content_type = response.headers.get('Content-Type', '')
    if 'image' in content_type:
        return response.content

    if 'text/html' in content_type:
        image_page_url = extract_image_url(response.content)
        if not image_page_url.startswith('http'):
            from urllib.parse import urljoin
            image_page_url = urljoin(image_url, image_page_url)
        return fetch_image_bytes(image_page_url)

    # Fallback: try interpreting raw bytes as image
    image = Image.open(BytesIO(response.content))
    buf = BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()
import re

def extract_form_id(slug: str) -> str | None:
    """
    Extracts the numeric form ID from a given JotForm slug or URL.

    Args:
        slug (str): A URL or slug that may contain the form ID.

    Returns:
        str | None: The numeric form ID, or None if not found.
    """
    match = re.search(r'/(\d+)', slug)
    return match.group(1) if match else None
