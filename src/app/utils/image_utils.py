from io import BytesIO
from typing import Union, Optional
import requests
from bs4 import BeautifulSoup
from PIL import Image
import cv2
import pytesseract
from io import BytesIO
import numpy as np

from app.config.config import Config

def normalize(ocr_results, img_width: int, img_height: int) -> list:
    normalized_results = []
    for item in ocr_results:
        box = item["bounding_box"]
        normalize_item = {}
        normalize_item["x1_norm"] = box["x1"] / img_width
        normalize_item["y1_norm"] = box["y1"] / img_height
        normalize_item["x2_norm"] = box["x2"] / img_width
        normalize_item["y2_norm"] = box["y2"] / img_height
        normalize_item["center_y"] = (normalize_item["y1_norm"] + normalize_item["y2_norm"]) / 2
        normalize_item["center_x"] = (normalize_item["x1_norm"] + normalize_item["x2_norm"]) / 2
        normalize_item['text'] = item["text"].strip().lower()
        normalized_results.append(normalize_item)
    return normalized_results

def bytes_to_cv2(image_bytes: bytes) -> np.ndarray:
    """
    Decode image bytes to an OpenCV BGR ndarray.
    Falls back to PIL if cv2.imdecode fails.
    """
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        # fallback via PIL -> RGB -> BGR
        pil = Image.open(BytesIO(image_bytes)).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img

def get_image(source = 'URL', imgURL = None, imgPath = None):
    """
    Fetch image from URL or local path.

    Args:
        source (str): 'URL' or 'PATH' to indicate image source type.
        imgURL (str): URL of the image (if source is 'URL').
        imgPath (str): Local file path of the image (if source is not 'URL').

    Returns:
        The image as a NumPy array.
    """
    if source == 'URL':
        image_bytes = fetch_image_bytes(imgURL)
        image = bytes_to_cv2(image_bytes)
    else:
        image = cv2.imread(imgPath)

    return image

def local_image_to_text(image):
    """
    Converts the image at img_url to text using the Tesseract OCR engine.
    Args:
        image: The image as a NumPy array or bytes.
    Returns:
        list:  OCR results with text and bounding boxes.
    """

    #image = image_preprocess(image)

    boxes = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    ocr_result = []
    for i, word in enumerate(boxes["text"]):
        x, y, w, h = boxes['left'][i], boxes['top'][i], boxes['width'][i], boxes['height'][i]
        #rel_x = x - cx1
        #rel_y = y - cy1

        item = {
            "text": word.strip(),
            "bounding_box": {
                "x1": x,
                "y1": y,
                "x2": x + w,
                "y2": y + h,
            },
            "center_y": (y + y + h) / 2,
            "center_x": (x + x + w) / 2
        }
        ocr_result.append(item)

    return ocr_result

def ninja_image_to_text(image):
    """
    Converts the image at img_url to text using the API.
    Args:
        image: The image as a NumPy array or bytes.
    Returns:
        list: OCR results with text and bounding boxes. 
    """

    #image = image_preprocess(image)

    if isinstance(image, np.ndarray):
        image = np.ascontiguousarray(image)
        ok, buf = cv2.imencode('.jpg', image)
        if not ok:
            raise RuntimeError("Failed to encode image for OCR API")
        image_bytes = buf.tobytes()
    elif isinstance(image, bytes):
        image_bytes = image
    elif isinstance(image, Image.Image):
        bio = BytesIO()
        image.save(bio, format='JPEG')
        image_bytes = bio.getvalue()
    else:
        # fallback: try reading imgPath if provided
        raise RuntimeError("No image bytes available for OCR API call")

    files = {'image': ('image.jpg', BytesIO(image_bytes), 'image/jpeg')}

    headers = {
        'X-Api-Key': Config.NINJA_API_KEY
    }

    r = requests.post(Config.NINJA_API_URL, files=files, headers=headers)
    ocr_result = r.json()

    return ocr_result

def extract_image_url(html_content: Union[str, bytes]) ->  Optional[str]:
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

def image_preprocess(img: cv2.Mat) -> cv2.Mat:
    cropped = None
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    possible_cards = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        ratio = w / float(h)
        # 85mm x 54mm ≈ 1.57
        if 1.47 < ratio < 1.67 and area > 10000:  
            possible_cards.append((x, y, w, h))
    
    # Choose the biggest area
    if possible_cards:
        x, y, w, h = max(possible_cards, key=lambda b: b[2]*b[3])
        cropped = img[y:y+h,x:x+w]
    else:
        print("❌ Cannot find card-like area")
        cropped = gray
    return cropped