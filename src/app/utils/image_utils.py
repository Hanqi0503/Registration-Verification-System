from io import BytesIO
from typing import Union, Optional, Dict
import logging

import requests
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

from app.config.config import Config

LOG = logging.getLogger(__name__)


def ninja_image_to_text(img_url: str, timeout: float = 10.0) -> Dict:
    """Send an image to the configured OCR endpoint and return the parsed JSON.

    Args:
        img_url: URL (or page URL) pointing to an image to OCR.
        timeout: Network timeout in seconds for the POST request.

    Returns:
        Parsed JSON response from the OCR endpoint.

    Raises:
        ValueError: If `NINJA_API_KEY` or `NINJA_API_URL` is not configured.
        requests.RequestException: On network-related failures.
    """
    if not Config.NINJA_API_KEY:
        raise ValueError("NINJA_API_KEY is not configured")
    if not Config.NINJA_API_URL:
        raise ValueError("NINJA_API_URL is not configured")

    image_bytes = fetch_image_bytes(img_url)

    files = {
        # provide a filename and content-type so requests builds a proper multipart
        'image': ('image.jpg', BytesIO(image_bytes), 'image/jpeg')
    }

    headers = {'X-Api-Key': Config.NINJA_API_KEY}

    try:
        resp = requests.post(Config.NINJA_API_URL, files=files, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        LOG.exception("Error calling ninja_image_to_text %s", exc)
        raise


def extract_image_url(html_content: Union[str, bytes]) -> str:
    """Extract the first <img src=...> URL from HTML content.

    Args:
        html_content: HTML as str or bytes.

    Returns:
        The image URL string.

    Raises:
        ValueError: If no image URL can be found.
    """
    if isinstance(html_content, bytes):
        # Let BeautifulSoup detect encoding where possible; decode as utf-8 as fallback.
        try:
            html_text = html_content.decode('utf-8')
        except Exception:
            html_text = html_content.decode(errors='ignore')
    else:
        html_text = html_content

    soup = BeautifulSoup(html_text, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return img_tag['src']
    raise ValueError("No image URL found in the provided HTML.")


def fetch_image_bytes(image_url: str, timeout: float = 10.0) -> bytes:
    """Download an image from `image_url` and return its bytes.

    Behavior:
    - If the URL points to a page (Content-Type text/html), the function will
      attempt to extract the first <img> and download that image instead.
    - If `Config.JOTFORM_API_KEY` is set the key is appended as `apiKey` query
      parameter to support JotForm-hosted images.

    Args:
        image_url: The URL of the image or a page that contains the image.
        timeout: Network timeout in seconds for GET requests.

    Returns:
        Binary image data.

    Raises:
        ValueError: If the response cannot be handled as an image.
        requests.RequestException: On network problems.
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

    try:
        response = requests.get(full_url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        LOG.exception("Failed to fetch image URL: %s", full_url)
        raise

    content_type = response.headers.get('Content-Type', '')
    # If the server returned an explicit image Content-Type, return it directly.
    if 'image' in content_type:
        return response.content

    # If we received HTML content, try to find an image tag and recurse.
    if 'text/html' in content_type:
        try:
            image_page_url = extract_image_url(response.content)
        except ValueError:
            LOG.error("HTML page did not contain an <img> tag: %s", full_url)
            raise

        if not image_page_url.startswith('http'):
            from urllib.parse import urljoin

            image_page_url = urljoin(image_url, image_page_url)
        return fetch_image_bytes(image_page_url, timeout=timeout)

    # Some servers omit Content-Type but still return image bytes. Try to open
    # with PIL as a last resort when status is 200.
    if response.status_code == 200:
        try:
            img = Image.open(BytesIO(response.content))
            buf = BytesIO()
            # Preserve format when possible, fallback to JPEG
            fmt = img.format if img.format else 'JPEG'
            img.save(buf, format=fmt)
            return buf.getvalue()
        except UnidentifiedImageError:
            LOG.exception("Response body could not be identified as an image for URL: %s", full_url)
            raise ValueError("Content is not a valid image")
        except Exception:
            LOG.exception("Unexpected error while decoding image for URL: %s", full_url)
            raise

    raise ValueError(f"Unable to handle content type: {content_type}")


__all__ = ["fetch_image_bytes", "extract_image_url", "ninja_image_to_text", "is_likely_printed_copy"]


def _decode_to_mat(image_bytes: bytes):
    """Decode bytes to OpenCV mat if possible, else return None."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        mat = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return mat
    except Exception:
        return None


def detect_face_bbox(image_bytes: bytes) -> "tuple[int,int,int,int] | None":
    """Detect a face in the image and return bbox (x,y,w,h) or None.

    Uses OpenCV Haar cascades when available.
    """
    mat = _decode_to_mat(image_bytes)
    if mat is None:
        return None
    try:
        import cv2  # type: ignore
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) == 0:
            return None
        # choose largest face
        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
        x, y, w, h = faces[0]
        return (int(x), int(y), int(w), int(h))
    except Exception:
        return None


def detect_card_bbox(image_bytes: bytes) -> "tuple[int,int,int,int] | None":
    """Attempt to detect a rectangular card-like region and return bbox or None.
    
    Uses multiple fallback strategies to handle cards that fill the frame, have
    glare, noisy backgrounds (carpet, fabric, wood), or have unclear edges.
    """
    mat = _decode_to_mat(image_bytes)
    if mat is None:
        return None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        best = None
        best_area = 0
        
        # Strategy 1: Color-based segmentation (works well on colored backgrounds like wood)
        # PR cards are typically light colored (white/cream) against darker backgrounds
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        
        # Create mask for light-colored regions (cards are usually light)
        lower_light = np.array([0, 0, 120])  # Low saturation, high brightness
        upper_light = np.array([180, 80, 255])
        light_mask = cv2.inRange(hsv, lower_light, upper_light)
        
        # Clean up the mask
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        light_mask = cv2.morphologyEx(light_mask, cv2.MORPH_CLOSE, kernel)
        light_mask = cv2.morphologyEx(light_mask, cv2.MORPH_OPEN, kernel)
        
        contours_color, _ = cv2.findContours(light_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours_color:
            area = cv2.contourArea(cnt)
            if area < (w * h * 0.15):  # Must be at least 15% of image
                continue
            
            x, y, ww, hh = cv2.boundingRect(cnt)
            bbox_area = ww * hh
            aspect = ww / float(hh) if hh > 0 else 0
            
            # Card-like aspect ratio and significant size
            if 0.5 < aspect < 2.5 and bbox_area > best_area:
                best_area = bbox_area
                best = (x, y, ww, hh)
        
        if best is not None and best_area > (w * h * 0.2):
            return best
        
        # Strategy 2: Adaptive thresholding for noisy backgrounds
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
        # Denoise with morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        morph = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
        morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)
        
        edges_adaptive = cv2.Canny(morph, 50, 150)
        contours_adaptive, _ = cv2.findContours(edges_adaptive, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by size and aspect ratio (card-like shape)
        for cnt in contours_adaptive:
            area = cv2.contourArea(cnt)
            if area < (w * h * 0.1):  # Must be at least 10% of image
                continue
            
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            if len(approx) >= 4:  # Accept 4+ points (handles slightly curved edges)
                x, y, ww, hh = cv2.boundingRect(approx)
                bbox_area = ww * hh
                aspect = ww / float(hh) if hh > 0 else 0
                
                # Card aspect ratio: 1.2-1.9 (landscape) or inverse for portrait
                if 0.5 < aspect < 2.5 and bbox_area > best_area:
                    best_area = bbox_area
                    best = (x, y, ww, hh)
        
        if best is not None and best_area > (w * h * 0.15):
            return best
        
        # Strategy 3: Standard Canny + contour detection with blur
        gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray_blur, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                x, y, ww, hh = cv2.boundingRect(approx)
                area = ww * hh
                aspect = ww / float(hh) if hh > 0 else 0
                if area > best_area and area > (w * h * 0.01) and 0.8 < aspect < 2.5:
                    best_area = area
                    best = (x, y, ww, hh)
        if best is not None:
            return best
        
        # Strategy 4: Bilateral filter + edge detection (preserves edges, smooths texture)
        bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
        edges_bilateral = cv2.Canny(bilateral, 30, 100)
        
        # Dilate edges to close gaps
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges_dilated = cv2.dilate(edges_bilateral, kernel_dilate, iterations=2)
        
        contours_bilateral, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours_bilateral:
            area = cv2.contourArea(cnt)
            if area < (w * h * 0.1):
                continue
                
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
            if len(approx) >= 4:
                x, y, ww, hh = cv2.boundingRect(approx)
                bbox_area = ww * hh
                aspect = ww / float(hh) if hh > 0 else 0
                if area > best_area and area > (w * h * 0.02) and 0.7 < aspect < 2.8:
                    best_area = bbox_area
                    best = (x, y, ww, hh)
        if best is not None:
            return best
        
        # Strategy 5: MinAreaRect fallback for rotated cards
        all_contours = contours + contours_adaptive + contours_bilateral + contours_color
        for cnt in all_contours:
            if cv2.contourArea(cnt) > (w * h * 0.05):
                rect = cv2.minAreaRect(cnt)
                box = cv2.boxPoints(rect)
                box = np.int0(box)
                x, y, ww, hh = cv2.boundingRect(box)
                area = ww * hh
                aspect = ww / float(hh) if hh > 0 else 0
                if area > best_area and 0.7 < aspect < 2.8:
                    best_area = area
                    best = (x, y, ww, hh)
        return best
    except Exception:
        return None


def detect_and_warp_card(image_bytes: bytes) -> bytes | None:
    """Detect a four-corner card in the image and return a top-down warped JPEG bytes.

    Returns None if no suitable quadrilateral is found or OpenCV isn't available.
    Handles noisy backgrounds and rotated cards.
    """
    mat = _decode_to_mat(image_bytes)
    if mat is None:
        return None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        # Try multiple edge detection strategies for noisy backgrounds
        candidates = []
        
        # Strategy 1: Adaptive thresholding (good for textured backgrounds)
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 11, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        morph = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
        edges_adaptive = cv2.Canny(morph, 50, 150)
        contours_adaptive, _ = cv2.findContours(edges_adaptive, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates.extend(contours_adaptive)
        
        # Strategy 2: Standard Gaussian blur + Canny
        gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray_blur, 50, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        candidates.extend(contours)
        
        # Strategy 3: Bilateral filter (preserves edges, removes texture)
        bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
        edges_bilateral = cv2.Canny(bilateral, 40, 120)
        contours_bilateral, _ = cv2.findContours(edges_bilateral, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates.extend(contours_bilateral)

        # Find the largest 4-point contour by approximating polygons
        best = None
        best_area = 0
        for cnt in candidates:
            area = cv2.contourArea(cnt)
            if area < (w * h * 0.05):  # Must be at least 5% of image
                continue
                
            peri = cv2.arcLength(cnt, True)
            # Try multiple epsilon values for approximation
            for epsilon_factor in [0.02, 0.03, 0.04]:
                approx = cv2.approxPolyDP(cnt, epsilon_factor * peri, True)
                if len(approx) == 4:
                    x, y, ww, hh = cv2.boundingRect(approx)
                    bbox_area = ww * hh
                    aspect = ww / float(hh) if hh > 0 else 0
                    
                    # Card-like aspect ratio
                    if 0.5 < aspect < 2.5 and bbox_area > best_area:
                        best_area = bbox_area
                        best = approx.reshape(4, 2)
                        break  # Found good approximation, no need to try other epsilons

        if best is None or best_area < (w * h * 0.1):
            return None

        # order points: tl, tr, br, bl
        def _order_pts(pts: np.ndarray) -> np.ndarray:
            rect = np.zeros((4, 2), dtype='float32')
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]
            rect[2] = pts[np.argmax(s)]
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]
            rect[3] = pts[np.argmax(diff)]
            return rect

        rect = _order_pts(best)
        (tl, tr, br, bl) = rect
        
        # Calculate dimensions more robustly
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Validate dimensions
        if maxWidth <= 10 or maxHeight <= 10 or maxWidth > w * 2 or maxHeight > h * 2:
            return None
        
        # Ensure card is in landscape orientation (PR cards are landscape)
        if maxHeight > maxWidth:
            maxWidth, maxHeight = maxHeight, maxWidth

        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype='float32')
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(mat, M, (maxWidth, maxHeight))

        # encode as JPEG
        ok, buf = cv2.imencode('.jpg', warped, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return None
        return buf.tobytes()
    except Exception:
        return None


def face_motion_between(img1_bytes: bytes, img2_bytes: bytes) -> "tuple[bool, float]":
    """Check movement of detected face centers between two images.

    Returns (moved_bool, distance_pixels).
    """
    b1 = detect_face_bbox(img1_bytes)
    b2 = detect_face_bbox(img2_bytes)
    if b1 is None or b2 is None:
        return (False, 0.0)
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    c1 = (x1 + w1 / 2.0, y1 + h1 / 2.0)
    c2 = (x2 + w2 / 2.0, y2 + h2 / 2.0)
    import math

    dist = math.hypot(c2[0] - c1[0], c2[1] - c1[1])
    # relative to face size
    rel = dist / max(w1, w2)
    return (rel > 0.05, dist)


def verify_selfie_with_card(first_image_bytes: bytes, second_image_bytes: bytes | None = None) -> "tuple[bool, float, str]":
    """Verify selfie(s) with card presence and optional motion heuristics.

    Returns (verified, score, reason).
    """
    reasons = []
    score = 0.0

    face1 = detect_face_bbox(first_image_bytes)
    card1 = detect_card_bbox(first_image_bytes)
    if face1 is not None:
        score += 0.3
    else:
        reasons.append('no_face_1')

    if card1 is not None:
        score += 0.3
    else:
        reasons.append('no_card_1')

    if second_image_bytes is not None:
        face2 = detect_face_bbox(second_image_bytes)
        card2 = detect_card_bbox(second_image_bytes)
        moved, dist = face_motion_between(first_image_bytes, second_image_bytes)
        if moved:
            score += 0.3
        else:
            reasons.append('no_motion')
        # bonus if both frames contain card and face
        if face2 is not None and card2 is not None:
            score += 0.1
    else:
        # single image; require both face+card and be slightly conservative
        if face1 is not None and card1 is not None:
            score += 0.1
        else:
            reasons.append('single_frame_missing')

    verified = score >= 0.6
    reason = ','.join(reasons) if reasons else 'ok'
    return (verified, round(score, 3), reason)

__all__.extend(["detect_face_bbox", "detect_card_bbox", "face_motion_between", "verify_selfie_with_card"]) 

def extract_text_lines_from_bytes(image_bytes: bytes) -> list:
    """Extract lines of text from image bytes.

    Strategy (safe for demo environments):
    1. Try the Tesseract CLI (calls the installed `tesseract` binary). This
       avoids importing heavy Python packages that may have ABI issues.
    2. If the CLI is not available or returns no text, attempt EasyOCR (if
       installed). If EasyOCR/import fails, skip it.
    3. Finally, if local OCR is not available, fall back to AWS Textract only
       when explicitly enabled in Config to avoid accidental costs.
    """
    import subprocess
    import tempfile

    # Preprocess image to improve OCR: CRITICAL - rotate to landscape first,
    # auto-correct orientation, sharpen, then crop, resize and enhance contrast.
    # PR cards must be in landscape orientation with text right-side-up for OCR
    # to read "PERMANENT RESIDENT CARD" at top right.
    def _preprocess_for_ocr(img_bytes: bytes) -> bytes:
        try:
            from PIL import Image, ImageOps, ImageFilter, ImageEnhance
            im = Image.open(BytesIO(img_bytes)).convert('RGB')
            
            # STEP 1: Auto-correct image orientation using EXIF data
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass
            
            # STEP 2: Rotate to landscape if portrait (PR cards are landscape)
            if im.width < im.height:
                im = im.rotate(90, expand=True)
            
            # STEP 3: Detect if image is upside-down and correct it
            # Strategy: Crop top 20% of image and do quick OCR test
            # If we find expected text (government, permanent, canada), orientation is correct
            # Otherwise rotate 180° and assume that's correct
            try:
                import subprocess
                import tempfile
                
                # Crop top 20% for orientation test
                h_test = int(im.height * 0.2)
                top_crop = im.crop((0, 0, im.width, h_test))
                
                # Quick OCR test on top crop
                def _quick_ocr_test(img_crop) -> str:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                        img_crop.save(tmp, format='JPEG', quality=85)
                        tmp.flush()
                        tmp_path = tmp.name
                    try:
                        # Try to find tesseract executable
                        tesseract_cmd = "tesseract"
                        try:
                            subprocess.run(["tesseract", "--version"], capture_output=True, check=False, timeout=1)
                        except (FileNotFoundError, subprocess.TimeoutExpired):
                            import os
                            common_paths = [
                                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
                            ]
                            for path in common_paths:
                                if os.path.exists(path):
                                    tesseract_cmd = path
                                    break
                        
                        proc = subprocess.run(
                            [tesseract_cmd, tmp_path, "stdout", "-l", "eng", "--psm", "6"],
                            capture_output=True, text=True, check=False, timeout=3,
                            encoding='utf-8', errors='ignore'
                        )
                        out = (proc.stdout or '').lower()
                        try:
                            import os
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                        return out
                    except Exception:
                        return ''
                
                top_text = _quick_ocr_test(top_crop)
                
                # Check for expected top-of-card keywords
                expected_keywords = ['government', 'gouvernement', 'permanent', 'resident', 'canada', 'carte']
                has_expected = any(kw in top_text for kw in expected_keywords)
                
                if not has_expected:
                    # Try rotating 180 and test again
                    im_rotated = im.rotate(180, expand=False)
                    top_crop_rotated = im_rotated.crop((0, 0, im_rotated.width, h_test))
                    top_text_rotated = _quick_ocr_test(top_crop_rotated)
                    has_expected_rotated = any(kw in top_text_rotated for kw in expected_keywords)
                    
                    # If rotated version is better, use it
                    if has_expected_rotated:
                        im = im_rotated
            except Exception:
                # If orientation detection fails, continue with current orientation
                pass
            
            # Save properly oriented image back to bytes for contour/warp detection
            buf_rotated = BytesIO()
            im.save(buf_rotated, format='JPEG', quality=95)
            img_bytes = buf_rotated.getvalue()
            
            # STEP 4: Try perspective warp on the rotated image (top-down view)
            warped = detect_and_warp_card(img_bytes)
            if warped:
                im = Image.open(BytesIO(warped)).convert('RGB')
            else:
                # Try cropping to detected bbox
                bbox = detect_card_bbox(img_bytes)
                if bbox:
                    x, y, w, h = bbox
                    x = max(0, int(x))
                    y = max(0, int(y))
                    w = max(1, int(w))
                    h = max(1, int(h))
                    im = im.crop((x, y, x + w, y + h))
            
            # STEP 5: Resize to optimal OCR resolution
            max_dim = 2000  # Increased for better OCR quality
            if max(im.width, im.height) > max_dim:
                ratio = max_dim / float(max(im.width, im.height))
                im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.LANCZOS)
            elif max(im.width, im.height) < 1000:
                # Upscale small images for better OCR
                ratio = 1000 / float(max(im.width, im.height))
                im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.LANCZOS)
            
            # STEP 6: Convert to grayscale to remove background color texture noise
            # This dramatically improves OCR on textured backgrounds (carpet, wood, fabric)
            # while removing color distractions that confuse Tesseract
            im = im.convert('L')
            
            # STEP 7: Auto-correct contrast and brightness
            im = ImageOps.autocontrast(im)
            
            # STEP 8: Denoise with median filter (remove noise before sharpening)
            im = im.filter(ImageFilter.MedianFilter(size=3))
            
            # STEP 9: Enhance sharpness for crisp text edges
            enhancer = ImageEnhance.Sharpness(im)
            im = enhancer.enhance(2.0)
            
            buf = BytesIO()
            im.save(buf, format='JPEG', quality=95)
            return buf.getvalue()
        except Exception:
            return img_bytes

    # Prepare two OCR candidates: warped (top-down) and original preprocessed
    warped_raw = None
    try:
        warped_raw = detect_and_warp_card(image_bytes)
    except Exception:
        warped_raw = None

    processed_orig = _preprocess_for_ocr(image_bytes)
    processed_warp = _preprocess_for_ocr(warped_raw) if warped_raw else None
    # Also prepare a full-image candidate with auto-corrections applied
    def _prepare_full(bts: bytes) -> bytes:
        try:
            from PIL import Image, ImageOps, ImageFilter, ImageEnhance
            im = Image.open(BytesIO(bts)).convert('RGB')
            
            # Auto-correct EXIF orientation
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass
            
            # Rotate to landscape first (critical for PR cards)
            if im.width < im.height:
                im = im.rotate(90, expand=True)
            
            # Resize to optimal resolution
            max_dim = 2000
            if max(im.width, im.height) > max_dim:
                ratio = max_dim / float(max(im.width, im.height))
                im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.LANCZOS)
            elif max(im.width, im.height) < 1000:
                ratio = 1000 / float(max(im.width, im.height))
                im = im.resize((int(im.width * ratio), int(im.height * ratio)), Image.LANCZOS)
            
            # NOTE: Keep RGB for visual feature detection (flag/logo colors)
            # Grayscale conversion happens later in _preprocess_for_ocr() for OCR-specific processing
            
            # Auto-contrast and sharpen
            im = ImageOps.autocontrast(im)
            im = im.filter(ImageFilter.MedianFilter(size=3))
            enhancer = ImageEnhance.Sharpness(im)
            im = enhancer.enhance(2.0)
            
            buf = BytesIO()
            im.save(buf, format='JPEG', quality=90)
            return buf.getvalue()
        except Exception:
            return bts

    processed_full = _prepare_full(image_bytes)

    def _tesseract_lines_from_bytes(bts: bytes) -> list:
        if not bts:
            return []
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(bts)
                tmp.flush()
                tmp_path = tmp.name
            
            # Try to find tesseract executable (handle cases where it's not in PATH)
            tesseract_cmd = "tesseract"
            try:
                # Quick test if tesseract is in PATH
                subprocess.run(["tesseract", "--version"], capture_output=True, check=False, timeout=1)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Not in PATH, try common Windows installation paths
                import os
                common_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        tesseract_cmd = path
                        break
            
            # Use PSM 6 (single uniform block of text) and DPI 300 for better OCR quality
            # PSM 6 works well for card layouts, and high DPI improves text recognition
            proc = subprocess.run(
                [tesseract_cmd, tmp_path, "stdout", "-l", "eng", "--psm", "6", "--dpi", "300"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                check=False
            )
            out = proc.stdout or ''
            try:
                import os
                os.unlink(tmp_path)
            except Exception:
                pass
            if out.strip():
                return [line.strip() for line in out.splitlines() if line.strip()]
            return []
        except FileNotFoundError:
            return []
        except Exception:
            return []

    # run Tesseract on warped first, then original; merge unique lines preserving order
    sources = []
    # Order: warped (top-down), cropped/rotated preprocessed, full image
    if processed_warp:
        sources.append(_tesseract_lines_from_bytes(processed_warp))
    if processed_orig:
        sources.append(_tesseract_lines_from_bytes(processed_orig))
    if processed_full:
        sources.append(_tesseract_lines_from_bytes(processed_full))

    # normalize and merge unique lines preserving order; prefer whitelist and
    # longer alphabetic lines so detector sees high-quality tokens first.
    def _norm_ln(s: str) -> str:
        return ' '.join(s.strip().split())

    merged = []
    seen = set()
    for src in sources:
        for ln in src:
            ln2 = _norm_ln(ln)
            key = ln2.lower()
            if not ln2:
                continue
            if key in seen:
                continue
            seen.add(key)
            merged.append(ln2)

    # Prioritization: whitelist tokens (strong PR indicators) appear first,
    # then alphabetic lines with at least two words and reasonable length.
    whitelist_tokens = [
        'confirmation of permanent', 'confirmation of permanent residence', 'confirmation of pr',
        'permanent resident', 'permanent', 'du canada', 'of canada', 'carte de', 'card'
    ]

    def _is_whitelist(ln: str) -> bool:
        ll = ln.lower()
        return any(tok in ll for tok in whitelist_tokens)

    def _is_alpha_good(ln: str) -> bool:
        parts = [p for p in ln.split() if any(c.isalpha() for c in p)]
        alpha_chars = sum(c.isalpha() for c in ln)
        return len(parts) >= 2 and alpha_chars >= 6

    prioritized = []
    rest = []
    seen2 = set()
    # first collect whitelist matches
    for ln in merged:
        key = ln.lower()
        if key in seen2:
            continue
        if _is_whitelist(ln):
            prioritized.append(ln)
            seen2.add(key)
    # then collect good alphabetic lines
    for ln in merged:
        key = ln.lower()
        if key in seen2:
            continue
        if _is_alpha_good(ln):
            prioritized.append(ln)
            seen2.add(key)
    # finally the rest preserving original order
    for ln in merged:
        key = ln.lower()
        if key in seen2:
            continue
        rest.append(ln)

    merged = prioritized + rest
    if merged:
        return merged

    # 2) Try EasyOCR if configured and available (guarded to avoid ABI issues)
    try:
        from app.config.config import Config as _Config
        if getattr(_Config, 'USE_EASY_OCR', False):
            import easyocr
            from PIL import Image
            reader = easyocr.Reader(['en'], gpu=False)
            for bts in (processed_warp, processed_orig):
                if not bts:
                    continue
                img = Image.open(BytesIO(bts)).convert('RGB')
                import numpy as _np
                arr = _np.array(img)
                res = reader.readtext(arr, detail=0)
                for ln in res:
                    ln = ln.strip()
                    if ln and ln not in merged:
                        merged.append(ln)
            if merged:
                return merged
    except Exception:
        pass

    # 3) AWS Textract as last resort (controlled by config)
    try:
        from app.config.config import Config as _Config
        if not (_Config.USE_EXTERNAL_OCR and _Config.AWS_ACCESS_KEY and _Config.AWS_SECRET_KEY):
            return []
    except Exception:
        return []

    try:
        from app.utils.aws_utils import AWSService
        svc = AWSService()
        return svc.extract_text_from_bytes(image_bytes)
    except Exception:
        return []


def extract_candidate_name(lines: list) -> str | None:
    """Simple heuristic to find the most likely name line from OCR lines.

    Picks the longest alphabetic line with at least two words.
    """
    import re
    candidates = []
    for line in lines:
        cleaned = re.sub(r'[^A-Za-z\s]', ' ', line).strip()
        if not cleaned:
            continue
        parts = cleaned.split()
        if len(parts) >= 2:
            candidates.append((len(cleaned), cleaned))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def detect_canada_flag_upper_left(image_bytes: bytes) -> bool:
    """Detect red Canadian flag in upper-left corner with balanced thresholds.
    
    Genuine PR cards have a red maple leaf flag in the upper-left corner
    next to "Government of Canada" / "Gouvernement du Canada" text.
    
    Returns True if Canadian flag red detected in upper-left region.
    Uses moderate thresholds to catch genuine cards while avoiding false positives.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
        
        # Load image
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        img_array = np.array(img)
        
        # Focus on upper-left 40% x 25% of image
        h, w = img_array.shape[:2]
        upper_left = img_array[:int(h * 0.4), :int(w * 0.25)]
        
        if upper_left.size == 0:
            return False
        
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(upper_left, cv2.COLOR_RGB2HSV)
        
        # Canadian flag red - BALANCED thresholds
        red_lower1 = np.array([0, 60, 60])  # Moderate saturation/value
        red_upper1 = np.array([12, 255, 255])
        red_lower2 = np.array([163, 60, 60])
        red_upper2 = np.array([180, 255, 255])
        
        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        
        # Count red pixels
        red_pixels = np.sum(red_mask > 0)
        total_pixels = upper_left.shape[0] * upper_left.shape[1]
        
        # Moderate threshold: at least 0.25% red pixels
        red_ratio = red_pixels / total_pixels
        
        return red_ratio > 0.0025
    except Exception:
        return False


def detect_canada_logo_visual(image_bytes: bytes) -> bool:
    """Detect maple leaf logo colors in bottom-right corner with balanced thresholds.
    
    Genuine PR cards have in the bottom-right:
    - Black "Canada" text
    - Red maple leaf logo
    - Green holographic maple leaf security feature
    
    Returns True if red and green color clusters detected in lower-right region.
    Uses moderate thresholds to balance genuine PR detection vs false positives.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
        
        # Load image
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        img_array = np.array(img)
        
        # Focus on bottom-right corner
        h, w = img_array.shape[:2]
        bottom_right = img_array[int(h * 0.60):, int(w * 0.60):]
        
        if bottom_right.size == 0:
            return False
        
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(bottom_right, cv2.COLOR_RGB2HSV)
        
        # Red color range - BALANCED (not too strict, not too loose)
        red_lower1 = np.array([0, 60, 60])  # Moderate saturation/value
        red_upper1 = np.array([12, 255, 255])
        red_lower2 = np.array([163, 60, 60])
        red_upper2 = np.array([180, 255, 255])
        
        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        
        # Green color range - BALANCED
        green_lower = np.array([35, 40, 40])  # Moderate for holographic
        green_upper = np.array([88, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        
        # Count pixels
        red_pixels = np.sum(red_mask > 0)
        green_pixels = np.sum(green_mask > 0)
        total_pixels = bottom_right.shape[0] * bottom_right.shape[1]
        
        # Moderate thresholds
        red_ratio = red_pixels / total_pixels
        green_ratio = green_pixels / total_pixels
        
        has_red_logo = red_ratio > 0.001  # 0.1%
        has_green_leaf = green_ratio > 0.001  # 0.1%
        
        # Require BOTH colors
        return has_red_logo and has_green_leaf
    except Exception:
        return False


def detect_canada_text_bottom_right(image_bytes: bytes) -> bool:
    """Run OCR specifically on bottom-right corner region to detect "CANADA" text.
    
    This is more precise than checking OCR line order, as it targets the exact
    spatial region where the "Canada" logo appears on genuine PR cards.
    
    Returns True if "CANADA" detected in bottom-right 40% x 40% region.
    """
    try:
        from PIL import Image
        import subprocess
        import tempfile
        
        # Load and crop to bottom-right corner
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        w, h = img.size
        
        # Bottom-right region: last 40% height, last 40% width
        crop_left = int(w * 0.6)
        crop_top = int(h * 0.6)
        bottom_right_crop = img.crop((crop_left, crop_top, w, h))
        
        # Save to temp file for Tesseract
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            bottom_right_crop.save(tmp.name, format='JPEG')
            tmp_path = tmp.name
        
        # Try to find tesseract executable
        tesseract_cmd = "tesseract"
        try:
            subprocess.run(["tesseract", "--version"], capture_output=True, check=False, timeout=1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            import os
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ]
            for path in common_paths:
                if os.path.exists(path):
                    tesseract_cmd = path
                    break
        
        # Run Tesseract on cropped region (PSM 11 = sparse text)
        proc = subprocess.run(
            [tesseract_cmd, tmp_path, 'stdout', '--psm', '11'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Clean up temp file
        import os
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if proc.returncode == 0:
            ocr_text = proc.stdout.lower()
            return 'canada' in ocr_text
        return False
    except Exception:
        return False


def detect_text_upper_right(image_bytes: bytes) -> "tuple[bool, bool]":
    """Run OCR on upper-right region to detect PR card title text.
    
    PR cards have "PERMANENT RESIDENT CARD" / "CARTE DE RÉSIDENT PERMANENT"
    in the upper-right corner.
    
    Returns (has_permanent, has_resident) tuple for scoring flexibility.
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import subprocess
        import tempfile
        
        # Load image
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        w, h = img.size
        
        # Upper-right region: top 30% height, right 50% width
        crop_left = int(w * 0.5)
        crop_bottom = int(h * 0.3)
        upper_right_crop = img.crop((crop_left, 0, w, crop_bottom))
        
        # Enhance for better OCR
        upper_right_crop = ImageEnhance.Contrast(upper_right_crop).enhance(2.0)
        upper_right_crop = ImageEnhance.Sharpness(upper_right_crop).enhance(2.5)
        upper_right_crop = upper_right_crop.filter(ImageFilter.SHARPEN)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            upper_right_crop.save(tmp.name, format='JPEG', quality=95)
            tmp_path = tmp.name
        
        # Find tesseract
        tesseract_cmd = "tesseract"
        try:
            subprocess.run(["tesseract", "--version"], capture_output=True, check=False, timeout=1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            import os
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ]
            for path in common_paths:
                if os.path.exists(path):
                    tesseract_cmd = path
                    break
        
        # Run Tesseract (PSM 6 = uniform block of text)
        proc = subprocess.run(
            [tesseract_cmd, tmp_path, 'stdout', '--psm', '6', '--dpi', '300'],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='ignore'
        )
        
        # Clean up
        import os
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if proc.returncode == 0:
            ocr_text = proc.stdout.lower()
            # Normalize common OCR errors
            ocr_text = ocr_text.replace('permanen', 'permanent').replace('sident', 'resident')
            
            has_permanent = 'permanent' in ocr_text
            has_resident = 'resident' in ocr_text or 'carte' in ocr_text
            
            return (has_permanent, has_resident)
        return (False, False)
    except Exception:
        return (False, False)


def detect_text_upper_left(image_bytes: bytes) -> bool:
    """Run OCR on upper-left region to detect government text.
    
    PR cards have "Government of Canada" / "Gouvernement du Canada"
    in the upper-left corner next to the flag.
    
    Returns True if government/gouvernement text detected.
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import subprocess
        import tempfile
        
        # Load image
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        w, h = img.size
        
        # Upper-left region: top 30% height, left 60% width
        crop_right = int(w * 0.6)
        crop_bottom = int(h * 0.3)
        upper_left_crop = img.crop((0, 0, crop_right, crop_bottom))
        
        # Enhance for better OCR
        upper_left_crop = ImageEnhance.Contrast(upper_left_crop).enhance(2.0)
        upper_left_crop = ImageEnhance.Sharpness(upper_left_crop).enhance(2.5)
        upper_left_crop = upper_left_crop.filter(ImageFilter.SHARPEN)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            upper_left_crop.save(tmp.name, format='JPEG', quality=95)
            tmp_path = tmp.name
        
        # Find tesseract
        tesseract_cmd = "tesseract"
        try:
            subprocess.run(["tesseract", "--version"], capture_output=True, check=False, timeout=1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            import os
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ]
            for path in common_paths:
                if os.path.exists(path):
                    tesseract_cmd = path
                    break
        
        # Run Tesseract (PSM 6 = uniform block of text)
        proc = subprocess.run(
            [tesseract_cmd, tmp_path, 'stdout', '--psm', '6', '--dpi', '300'],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='ignore'
        )
        
        # Clean up
        import os
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if proc.returncode == 0:
            ocr_text = proc.stdout.lower()
            # Look for government/gouvernement keywords
            has_gov = 'government' in ocr_text or 'gouvernement' in ocr_text
            has_canada = 'canada' in ocr_text
            
            return has_gov or (has_canada and ('of' in ocr_text or 'du' in ocr_text))
        return False
    except Exception:
        return False


def detect_text_middle_section(image_bytes: bytes) -> int:
    """Run OCR on middle section (beside photo) to count ID fields.
    
    PR cards have structured fields in the middle section:
    - ID NO / N° ID
    - SEX / SEXE
    - NATIONALITY / NATIONALITÉ
    - DATE OF BIRTH / DATE DE NAISSANCE
    - EXPIRY / EXPIRATION
    
    Returns count of detected ID fields (0-5).
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import subprocess
        import tempfile
        
        # Load image
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        w, h = img.size
        
        # Middle section: middle 50% height, right 60% width (beside photo area)
        crop_left = int(w * 0.4)
        crop_top = int(h * 0.25)
        crop_bottom = int(h * 0.75)
        middle_crop = img.crop((crop_left, crop_top, w, crop_bottom))
        
        # Enhance for better OCR
        middle_crop = ImageEnhance.Contrast(middle_crop).enhance(2.0)
        middle_crop = ImageEnhance.Sharpness(middle_crop).enhance(2.5)
        middle_crop = middle_crop.filter(ImageFilter.SHARPEN)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            middle_crop.save(tmp.name, format='JPEG', quality=95)
            tmp_path = tmp.name
        
        # Find tesseract
        tesseract_cmd = "tesseract"
        try:
            subprocess.run(["tesseract", "--version"], capture_output=True, check=False, timeout=1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            import os
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ]
            for path in common_paths:
                if os.path.exists(path):
                    tesseract_cmd = path
                    break
        
        # Run Tesseract (PSM 6 = uniform block of text)
        proc = subprocess.run(
            [tesseract_cmd, tmp_path, 'stdout', '--psm', '6', '--dpi', '300'],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='ignore'
        )
        
        # Clean up
        import os
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if proc.returncode == 0:
            ocr_text = proc.stdout.lower()
            
            # Count detected ID fields
            field_count = 0
            
            # ID NO field
            if any(kw in ocr_text for kw in ['id no', 'n id', 'no id', 'idno', 'id n']):
                field_count += 1
            
            # SEX field
            if 'sex' in ocr_text or 'sexe' in ocr_text:
                field_count += 1
            
            # NATIONALITY field
            if any(kw in ocr_text for kw in ['nationality', 'nationalite', 'nation']):
                field_count += 1
            
            # DATE OF BIRTH field
            if any(kw in ocr_text for kw in ['birth', 'naissance', 'date of birth', 'date de naissance']):
                field_count += 1
            
            # EXPIRY field
            if any(kw in ocr_text for kw in ['expiry', 'expiration', 'd expiration']):
                field_count += 1
            
            return field_count
        return 0
    except Exception:
        return 0


def fuzzy_name_match(form_name: str, ocr_name: str) -> float:
    """Return similarity ratio (0-100) between form_name and OCRed name using difflib."""
    import difflib
    if not form_name or not ocr_name:
        return 0.0
    s1 = ' '.join(form_name.lower().split())
    s2 = ' '.join(ocr_name.lower().split())
    ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
    return round(ratio * 100.0, 1)



def is_likely_printed_copy(image_bytes: bytes, use_cv: bool = True) -> "tuple[bool, float, str]":
    """Printed-copy detection is disabled.

    The function remains to avoid changing call sites; it always returns
    (False, 0.0, 'disabled').
    """
    return (False, 0.0, 'disabled')


def detect_card_type(image_bytes: bytes) -> "tuple[str, float, str]":
    """Detect the likely card type from image bytes using a multi-factor scoring system.
    
    ACCEPTANCE CRITERIA (Points-based system):
    ========================================
    A card is classified as PR if it scores >= 100 points from the following:
    
    CRITICAL SECURITY FEATURES (Visual Detection):
    - Red Canadian flag (upper-left corner): 40 points [REQUIRED for auto-accept]
    - Red maple leaf logo (bottom-right): 35 points [REQUIRED for auto-accept]
    - Green holographic leaf (bottom-right): 35 points [REQUIRED for auto-accept]
    
    SUPPORTING OCR EVIDENCE (Text Detection):
    - "Government of Canada" / "Gouvernement du Canada": 25 points
    - "Permanent Resident Card" / "Carte de résident permanent": 30 points
    - "CANADA" text in bottom-right corner: 20 points
    - ID fields present (ID NO, SEX, NATIONALITY, DOB, EXPIRY): 5 points each (max 25)
    
    ACCEPTANCE RULES:
    =================
    1. AUTO-ACCEPT (>= 100 points):
       - Must have BOTH bottom-right visual features (red maple + green holographic) = 70 points
       - Plus flag in upper-left = 40 points (total 110 points)
       - OR visual features (70) + supporting OCR (30+ points)
    
    2. MEDIUM CONFIDENCE (75-99 points):
       - Visual features detected but missing some OCR support
       - Strong OCR support but weak/missing visual features
       - Requires manual review
    
    3. REJECT (< 75 points):
       - Provincial IDs, driver licenses (flagged immediately)
       - Insufficient evidence of genuine PR card
       - Missing critical visual security features

    Returns:
        (card_type, score, reason)
        card_type: 'pr' or 'flagged'
        score: 0.0-1.0 confidence (points/100 normalized)
        reason: detailed breakdown of scoring
    """
    # If a model-based detector is enabled, try it first (fast path).
    # This is opt-in via Config.USE_MODEL_DETECTOR to avoid accidental use.
    try:
        if getattr(Config, 'USE_MODEL_DETECTOR', False):
            # If a remote model service is configured and enabled, call it first.
            try:
                if getattr(Config, 'USE_MODEL_SERVICE', False):
                    import requests
                    url = getattr(Config, 'MODEL_SERVICE_URL', 'http://localhost:8000/infer')
                    files = {'image': ('img.jpg', BytesIO(image_bytes), 'image/jpeg')}
                    try:
                        resp = requests.post(url, files=files, timeout=10)
                        if resp.status_code == 200:
                            j = resp.json()
                            scores = j.get('scores', [])
                            labels = j.get('labels', [])
                            if scores:
                                top_score = float(scores[0])
                                top_label = int(labels[0]) if labels else None
                                if top_score >= getattr(Config, 'MODEL_DETECTOR_THRESHOLD', 0.6):
                                    if top_label == 1 or top_label is None:
                                        # Verify there is a detected card-like contour in the image
                                        try:
                                            from PIL import Image
                                            img = Image.open(BytesIO(image_bytes))
                                            iw, ih = img.size
                                            cb = detect_card_bbox(image_bytes)
                                            if cb is None:
                                                # If no contour found, accept only when OCR strongly
                                                # supports PR (covers cases where card fills frame and
                                                # contour detection fails). Otherwise veto.
                                                try:
                                                    ocr_lines = extract_text_lines_from_bytes(image_bytes)
                                                    txt_preview = '\n'.join(l.lower() for l in (ocr_lines or []))
                                                    strong_tokens = ['permanent resident', 'permanent', 'resident', 'confirmation of permanent', 'confirmation of pr', 'carte de', 'du canada', 'of canada', 'pr', 'card', 'carte']
                                                    if any(tok in txt_preview for tok in strong_tokens):
                                                        # allow acceptance when OCR clearly indicates PR
                                                        pass
                                                    else:
                                                        # If both OCR and contour checks fail, be conservative
                                                        # and veto the model prediction rather than accepting
                                                        # on a high but potentially spurious score. This
                                                        # prevents printed/flat images or non-PR cards from
                                                        # being auto-accepted solely on model confidence.
                                                        return ("other", 0.0, f"model_det_veto:no_card_contour_high_conf;score={top_score}")
                                                except Exception:
                                                    return ("other", 0.0, f"model_det_veto:no_card_contour;score={top_score}")
                                            x, y, ww, hh = cb
                                            area_ratio = (ww * hh) / float(max(1, iw * ih))
                                            aspect = ww / float(hh) if hh > 0 else 0
                                            # require reasonable size and aspect ratio for a physical card
                                            if area_ratio < 0.03 or not (1.2 <= aspect <= 1.9):
                                                return ("other", 0.0, f"model_det_veto:contour_mismatch;score={top_score}")
                                        except Exception:
                                            # if any error occurs during contour check, be conservative and veto
                                            LOG.exception('Card contour verification failed')
                                            return ("other", 0.0, f"model_det_veto:contour_error;score={top_score}")
                                        return ("pr", top_score, f"model_service:label={top_label}")
                    except Exception:
                        LOG.exception('Model service request failed to %s', url)
            except Exception:
                LOG.exception('Model service fast-path failed')
            # Lazy-load a TorchScript model if available
            try:
                _MODEL = None
                def _get_model_detector():
                    """Lazily load a TorchScript model from Config.MODEL_DETECTOR_PATH.

                    Returns the loaded module or None on failure.
                    """
                    nonlocal _MODEL
                    if _MODEL is not None:
                        return _MODEL
                    try:
                        import torch
                        path = getattr(Config, 'MODEL_DETECTOR_PATH', 'models/model_epoch_2.ts')
                        # Prefer to load a TorchScript artifact when available
                        try:
                            mdl = torch.jit.load(path, map_location='cpu')
                            mdl.eval()
                            _MODEL = mdl
                            return _MODEL
                        except Exception:
                            # If TorchScript load fails (common when torchvision ops are not scripted),
                            # only attempt to load a state_dict if the path points to a .pth/.pt file.
                            LOG.warning('TorchScript load failed for %s', path)
                            try:
                                import os
                                suffix = os.path.splitext(path)[1].lower()
                                if suffix in ('.pth', '.pt'):
                                    LOG.info('Attempting to load checkpoint state_dict from %s', path)
                                    import torchvision
                                    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
                                    sd = torch.load(path, map_location='cpu')
                                    # detect if sd is a state_dict (dict of tensors) vs full checkpoint
                                    state = None
                                    if isinstance(sd, dict) and any(isinstance(v, torch.Tensor) for v in sd.values()):
                                        state = sd
                                    elif isinstance(sd, dict) and ('model' in sd or 'state_dict' in sd):
                                        state = sd.get('model', sd.get('state_dict'))
                                    if state is not None:
                                        model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=False)
                                        in_features = model.roi_heads.box_predictor.cls_score.in_features
                                        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, 4)
                                        model.load_state_dict(state)
                                        model.eval()
                                        _MODEL = model
                                        return _MODEL
                            except Exception:
                                LOG.exception('Failed to build model from checkpoint %s', path)
                                return None
                    except Exception:
                        LOG.exception('Failed to load model detector from %s', getattr(Config, 'MODEL_DETECTOR_PATH', 'models/model_epoch_2.ts'))
                        return None

                mdl = _get_model_detector()
                if mdl is not None:
                    from PIL import Image
                    import torchvision.transforms.functional as TF
                    import torch
                    img = Image.open(BytesIO(image_bytes)).convert('RGB')
                    img_t = TF.to_tensor(img)
                    with torch.no_grad():
                        try:
                            res = mdl([img_t])
                        except Exception:
                            # Some scripted modules expect a different input shape; attempt to move to cpu and call anyway
                            res = mdl([img_t.cpu()])
                    if isinstance(res, (list, tuple)) and len(res):
                        r0 = res[0]
                        scores = r0.get('scores', None)
                        labels = r0.get('labels', None)
                        if scores is not None and len(scores):
                            top_score = float(scores[0].item())
                            top_label = int(labels[0].item()) if labels is not None and len(labels) else None
                            if top_score >= getattr(Config, 'MODEL_DETECTOR_THRESHOLD', 0.6):
                                # Conservatively map detection label 1 -> PR card
                                if top_label == 1 or top_label is None:
                                    # Post-filter using OCR to reduce false positives.
                                    try:
                                        # lazy OCR check (may be empty but cheap relative to model)
                                        ocr_lines = extract_text_lines_from_bytes(image_bytes)
                                        txt = '\n'.join(l.lower() for l in ocr_lines)

                                        # Driver-license keywords veto: if OCR clearly indicates driver's
                                        # license, prefer that label even if detector thought PR.
                                        dl_keywords = [
                                            # common English/French variants and noisy OCR forms
                                            "driver", "driver's", "drivers", "licence", "license",
                                            "dl", "d/l", "driving licence", "driver licence", "driver's licence",
                                            "licence no", "license no", "lic no", "licence no.", "licence #",
                                            # authority/issuer tokens that indicate a government issued driving ID
                                            "ontario", "canada", "republic", "dvla", "permis", "permis de conduire",
                                            "gouvernement", "government", "permiso", "permiso de conducir"
                                        ]
                                        if any(tok in txt for tok in dl_keywords):
                                            return ("driver_license", 0.95, f"model_det_veto:driver_kw;score={top_score}")

                                        # Handwritten-paper heuristic: OCR returns little machine text
                                        # or mostly single-char tokens -> likely handwritten and should not
                                        # be auto-accepted as PR card.
                                        def _is_likely_handwritten(lines: list) -> bool:
                                            """Lightweight handwritten-vs-printed heuristic.

                                            Returns True when the text looks like hand-written notes or
                                            casual pen-written tokens rather than machine-printed OCRable
                                            text. This uses only simple counts so it runs fast and
                                            doesn't require extra libraries.
                                            """
                                            if not lines:
                                                return True
                                            total_chars = sum(len(l) for l in lines)
                                            if total_chars == 0:
                                                return True
                                            alpha = sum(c.isalpha() for l in lines for c in l)
                                            alpha_ratio = alpha / float(total_chars)

                                            # Tokenization stats
                                            words = [w for l in lines for w in l.split()]
                                            if not words:
                                                return True
                                            avg_word_len = (sum(len(w) for w in words) / float(len(words)))
                                            short_word_frac = sum(1 for w in words if len(w) <= 2) / float(len(words))

                                            # Non-alphanumeric noise fraction (pen scribbles, punctuation)
                                            non_alnum = sum(1 for c in ''.join(lines) if not c.isalnum() and not c.isspace())
                                            non_alnum_frac = non_alnum / float(total_chars) if total_chars else 0.0

                                            # Heuristics (conservative):
                                            # - low alphabetic ratio -> likely noisy/handwritten
                                            # - very short average word length or many short tokens -> handwritten
                                            # - high non-alnum fraction (slashes, punctuation) -> handwritten/notes
                                            if alpha_ratio < 0.45:
                                                return True
                                            if avg_word_len < 3.5:
                                                return True
                                            if short_word_frac > 0.35:
                                                return True
                                            if non_alnum_frac > 0.12:
                                                return True
                                            return False

                                        if _is_likely_handwritten(ocr_lines):
                                            return ("other", 0.0, f"model_det_veto:handwritten;score={top_score}")
                                    except Exception:
                                        LOG.exception('OCR post-filter failed')
                                        return ("other", 0.0, f"model_det_veto:ocr_error;score={top_score}")

                                    # also verify we can detect a card-shaped contour before accepting
                                    try:
                                        from PIL import Image
                                        img = Image.open(BytesIO(image_bytes))
                                        iw, ih = img.size
                                        cb = detect_card_bbox(image_bytes)
                                        if cb is None:
                                            # Do not auto-accept solely on model confidence when
                                            # we cannot detect a card contour. Require OCR support
                                            # (handled above) or a card contour; otherwise veto.
                                            return ("other", 0.0, f"model_det_veto:no_card_contour;score={top_score}")
                                        x, y, ww, hh = cb
                                        area_ratio = (ww * hh) / float(max(1, iw * ih))
                                        aspect = ww / float(hh) if hh > 0 else 0
                                        if area_ratio < 0.03 or not (1.2 <= aspect <= 1.9):
                                            return ("other", 0.0, f"model_det_veto:contour_mismatch;score={top_score}")
                                    except Exception:
                                        LOG.exception('Contour post-filter failed')
                                        return ("other", 0.0, f"model_det_veto:contour_error;score={top_score}")

                                    return ("pr", top_score, f"model_det:label={top_label}")
            except Exception:
                LOG.exception('Model detector invocation failed')
    except Exception:
        # Fall back to heuristic approach if any unexpected error occurs
        LOG.exception('Unexpected error during model detector fast-path')

    try:
        lines = extract_text_lines_from_bytes(image_bytes)
    except Exception:
        lines = []

    # Normalize OCR lines: join, lower, strip common OCR garble, remove
    # diacritics to make matching robust across French/English and noisy OCR.
    def _normalize(s: str) -> str:
        import re, unicodedata
        if not s:
            return ''
        # Replace common OCR encoding errors
        s = s.replace('â€˜', "'").replace('â€™', "'").replace('â€œ', '"').replace('â€', '"')
        s = s.replace('Ã©', 'e').replace('Ã', 'a').replace('Â', ' ')
        # NFC normalize then remove diacritics
        s2 = unicodedata.normalize('NFKD', s)
        s2 = ''.join(c for c in s2 if not unicodedata.combining(c))
        s2 = s2.lower()
        # common OCR artifacts -> normalize separators and remove weird chars
        s2 = re.sub(r'[|\\/\*\^]', ' ', s2)
        s2 = re.sub(r'[^a-z0-9\s\-]', ' ', s2)
        s2 = re.sub(r'\s+', ' ', s2).strip()
        return s2

    txt_lines = [_normalize(l) for l in lines]
    txt = "\n".join(txt_lines)

    # Map common OCR misreads to canonical tokens to improve matching.
    # Keep mapping conservative to avoid false positives.
    ocr_map = {
        'sident': 'resident',
        'resid': 'resident',
        'permanen': 'permanent',
        'permenant': 'permanent',
        'govt': 'government',
        'gouvern': 'gouvernement',
        'du canada': 'du canada',
        'of canada': 'of canada',
        'carte de': 'carte de',
        'card du': 'card du'
    }
    for k, v in ocr_map.items():
        if k in txt:
            txt = txt.replace(k, v)
    reasons = []
    score = 0.0

    # STRUCTURED PR CARD VALIDATION
    # PR cards have a very specific layout with these key elements:
    # - Upper left: "Government of Canada" / "Gouvernement du Canada"
    # - Upper right: "Permanent Resident Card" / "Carte de résident permanent"
    # - Middle section (beside photo): ID NO, SEX/SEXE, NATIONALITY/NATIONALITÉ, DATE OF BIRTH, EXPIRY
    # - Bottom right: "Canada"
    
    # Check for upper left government box
    has_gov_canada = any(phrase in txt for phrase in [
        'government of canada', 'gouvernement du canada', 
        'government canada', 'gouvernement canada'
    ])
    
    # Check for upper right permanent resident box
    has_pr_title = any(phrase in txt for phrase in [
        'permanent resident card', 'carte de resident permanent',
        'permanent resident', 'resident permanent',
        'carte de resident', 'carte resident permanent'
    ])
    
    # Check for middle section ID fields (partial matching is fine)
    id_fields = ['id no', 'n id', 'no id', 'idno']
    sex_fields = ['sex', 'sexe']
    nationality_fields = ['nationality', 'nationalite', 'nation']
    dob_fields = ['date of birth', 'date de naissance', 'birth', 'naissance']
    expiry_fields = ['expiry', 'expiration', 'd expiration']
    
    has_id_field = any(field in txt for field in id_fields)
    has_sex_field = any(field in txt for field in sex_fields)
    has_nationality_field = any(field in txt for field in nationality_fields)
    has_dob_field = any(field in txt for field in dob_fields)
    has_expiry_field = any(field in txt for field in expiry_fields)
    
    # Count how many ID fields are present
    field_count = sum([has_id_field, has_sex_field, has_nationality_field, has_dob_field, has_expiry_field])
    
    # Check for Canada mentions (appears in multiple locations on PR cards)
    has_canada = 'canada' in txt or 'canadian' in txt
    
    # CRITICAL: FLAG driver licenses AND provincial IDs FIRST before any other checks
    # These must be flagged immediately to prevent false PR classification
    driver_keywords = [
        'driver', 'driving', 'licence no', 'license no', 'republic', 
        'driving licence', 'dvla', 'permis de conduire', 'ontario',
        'drivers', 'driver s', 'licence', 'dl no', 'class',
        # Provincial ID cards (not PR cards)
        'saskatchewan', 'identification card', 'alberta', 'british columbia',
        'manitoba', 'nova scotia', 'new brunswick', 'quebec', 'bc services',
        'service bc', 'service ontario', 'service alberta', 'service card',
        'provincial', 'photo card',
        # International driver's licenses
        'ghana', 'dvla', 'gh republic', 'driver vehicle licensing'
    ]
    if any(kw in txt for kw in driver_keywords):
        return ("flagged", 0.0, "provincial_id_or_driver_license_detected")
    
    # ============================================================================
    # MULTI-FACTOR SCORING SYSTEM
    # ============================================================================
    # Points are awarded for each detected feature. Cards need >= 100 points to pass.
    
    points = 0
    score_breakdown = []
    
    # 1. CRITICAL VISUAL SECURITY FEATURES (110 points possible)
    # -----------------------------------------------------------
    
    # Red Canadian flag in upper-left corner (40 points)
    has_canada_flag_upper_left = detect_canada_flag_upper_left(image_bytes)
    if has_canada_flag_upper_left:
        points += 40
        score_breakdown.append('flag_upper_left:40pts')
    
    # Bottom-right visual features (70 points total - BOTH required for auto-accept)
    has_canada_visual = detect_canada_logo_visual(image_bytes)
    if has_canada_visual:
        # This function already checks for BOTH red maple leaf AND green holographic
        points += 70  # 35 for red maple + 35 for green holographic
        score_breakdown.append('visual_logo:70pts(red+green)')
    
    # 2. SUPPORTING OCR EVIDENCE (125 points possible with spatial OCR)
    # -------------------------------------------------------------------
    
    # SPATIAL OCR: Upper-left government text (30 points)
    has_gov_upper_left_spatial = detect_text_upper_left(image_bytes)
    if has_gov_upper_left_spatial:
        points += 30
        score_breakdown.append('gov_spatial_ocr:30pts')
    elif has_gov_canada:
        # Fallback to full-image OCR (25 points)
        points += 25
        score_breakdown.append('gov_canada_ocr:25pts')
    
    # SPATIAL OCR: Upper-right PR title text (35 points)
    has_permanent_spatial, has_resident_spatial = detect_text_upper_right(image_bytes)
    if has_permanent_spatial and has_resident_spatial:
        points += 35
        score_breakdown.append('pr_title_spatial_ocr:35pts')
    elif has_permanent_spatial or has_resident_spatial:
        points += 20
        score_breakdown.append('pr_title_partial_spatial:20pts')
    elif has_pr_title:
        # Fallback to full-image OCR (15 points - reduced since spatial failed)
        points += 15
        score_breakdown.append('pr_title_ocr:15pts')
    
    # SPATIAL OCR: Bottom-right "CANADA" text (20 points)
    has_canada_bottom_right_ocr = detect_canada_text_bottom_right(image_bytes)
    if has_canada_bottom_right_ocr:
        points += 20
        score_breakdown.append('canada_spatial_ocr:20pts')
    
    # SPATIAL OCR: Middle section ID fields (8 points each, max 40 points)
    spatial_field_count = detect_text_middle_section(image_bytes)
    if spatial_field_count > 0:
        spatial_field_points = spatial_field_count * 8
        points += spatial_field_points
        score_breakdown.append(f'id_fields_spatial:{spatial_field_count}x8={spatial_field_points}pts')
    elif field_count > 0:
        # Fallback to full-image OCR field detection (reduced points)
        field_points = field_count * 5
        points += field_points
        score_breakdown.append(f'id_fields:{field_count}x5={field_points}pts')
    
    # 3. APPLY ACCEPTANCE RULES
    # --------------------------
    
    # Calculate normalized confidence (0.0-1.0)
    # Maximum possible points: 235 (110 visual + 125 spatial OCR)
    # We normalize to 100 point scale for confidence calculation
    confidence = min(1.0, points / 100.0)
    
    # CRITICAL: Visual-only detection (110 pts from flag+logo) is NOT sufficient
    # Require at least SOME OCR evidence to prevent false positives from
    # cards that happen to have red+green colors but aren't PR cards
    
    # AUTO-ACCEPT: >= 100 points AND has at least one OCR feature
    ocr_points = points - (40 if has_canada_flag_upper_left else 0) - (70 if has_canada_visual else 0)
    has_ocr_support = ocr_points >= 10  # At least 10 points from OCR (lowered from 20)
    
    # CRITICAL: Require "CANADA" text detection to prevent foreign PR cards (US Green Card, etc.)
    has_canada_text = has_canada_bottom_right_ocr or has_gov_canada or 'canada' in txt
    
    if points >= 100 and has_ocr_support and has_canada_text:
        return ("pr", confidence, f"PASS:{points}pts[{','.join(score_breakdown)}]")
    
    # MEDIUM CONFIDENCE: 75-99 points (manual review recommended)
    # OR 100+ points but lacking OCR support (visual-only match)
    # OR 100+ points but lacking Canada text verification
    if points >= 75:
        if points >= 100 and not has_ocr_support:
            return ("flagged", confidence, f"VISUAL_ONLY:{points}pts[{','.join(score_breakdown)}]:needs_ocr_validation")
        if points >= 100 and not has_canada_text:
            return ("flagged", confidence, f"NO_CANADA_TEXT:{points}pts[{','.join(score_breakdown)}]:foreign_document")
        if has_canada_text:
            return ("pr", confidence, f"PASS:{points}pts[{','.join(score_breakdown)}]")
        # 75-99 pts without Canada text - likely foreign document
        return ("flagged", confidence, f"NO_CANADA_TEXT:{points}pts[{','.join(score_breakdown)}]:foreign_document")
    
    # COPR DOCUMENT DETECTION: 60-74 points with flag + Canada text
    # COPR (Confirmation of Permanent Residence) are A4 paper documents, not plastic cards
    # They have: Canadian flag, Government branding, Canada text, but NO red+green hologram
    # Accept if: flag (40pts) + Canada OCR (20pts) + some ID fields (8+pts) = 68+ pts
    if points >= 60 and has_canada_flag_upper_left and has_canada_text and not has_canada_visual:
        # No hologram (paper document) but has official Canadian government branding
        return ("pr", confidence, f"COPR_DOCUMENT:{points}pts[{','.join(score_breakdown)}]")
    
    # INSUFFICIENT EVIDENCE: < 60 points (or < 75 without Canada text)
    # Try legacy OCR fallback for edge cases before final rejection
    
    # ============================================================================
    # LEGACY FALLBACK (for cards with poor OCR or missing visual features)
    # ============================================================================
    legacy_score = 0.0
    legacy_reasons = []
    
    # Co-occurrence checks: treat separate tokens appearing across OCR lines as
    # a strong PR signal (handles line breaks and OCR tokenization).
    if (any(tok in txt for tok in ('permanent', 'permanen')) and any(tok in txt for tok in ('resident', 'sident', 'resid'))):
        legacy_score += 0.6
        legacy_reasons.append('cooccur:permanent_resident')

    # If we see 'carte/card' together with a country signal and a permanent
    # fragment it's a strong hint even when full phrases are broken.
    if (('carte' in txt or 'card' in txt) and any(tok in txt for tok in ('permanent', 'permanen', 'resident', 'sident'))):
        legacy_score += 0.55
        legacy_reasons.append('fragment_combo:carte_permanent')

    # Country signals (expand list) — include common abbreviations and
    # French/English variants.
    canada_signals = ['canada', 'canadian', 'du canada', 'of canada', 'gouvernement', 'government', 'citizenship', 'cic', 'citizenship and immigration canada']

    # If multiple fragment tokens are present and there's a country signal,
    # upgrade to a strong PR hint (useful for noisy OCR with many small hits).
    frag_hits = sum(1 for tok in ('permanent', 'permanen', 'resident', 'sident', 'carte', 'card') if tok in txt)
    if frag_hits >= 2 and any(sig in txt for sig in canada_signals):
        # Return immediately as high confidence PR hint
        return ("pr", min(1.0, legacy_score + 0.25), f"LEGACY:frag_country_combo[{','.join(legacy_reasons)}]")

    # Small whitelist boost: if we find explicit whitelist tokens in the
    # normalized OCR text, give a modest confidence bump. This helps when
    # OCR is noisy but contains explicit PR phrases.
    whitelist_boost_tokens = [
        'confirmation of permanent', 'confirmation of permanent residence', 'confirmation of pr',
        'permanent resident', 'du canada', 'of canada', 'carte de', 'carte', 'card'
    ]
    for tok in whitelist_boost_tokens:
        if tok in txt:
            legacy_score = min(1.0, legacy_score + 0.12)
            legacy_reasons.append(f'whitelist:{tok}')
            break

    # Check for PR evidence first before applying driver-license classification
    # If our co-occurrence/keyword scoring indicates a likely PR card and we
    # also see any Canada-related signal, classify as PR. This handles cases
    # where OCR splits words across lines and phrase matching fails.
    canada_signals = ['canada', 'canadian', 'du canada', 'of canada', 'gouvernement']
    # Require a higher OCR score before auto-classifying as PR to reduce
    # false-positives from printed or handwritten spoofs.
    if legacy_score >= 0.8 and any(sig in txt for sig in canada_signals):
        return ("pr", min(1.0, legacy_score), f"LEGACY:pr_cooccur[{','.join(legacy_reasons)}]")

    # Additional legacy checks for edge cases
    if (('carte' in txt or 'card' in txt) and any(sig in txt for sig in canada_signals)
            and ('permanent' in txt or 'permanen' in txt or 'confirmation' in txt)):
        return ("pr", 0.75, f"LEGACY:carte_canada_permanent[{','.join(legacy_reasons)}]")
    
    # PR confirmation letter detection (COPR - Confirmation of Permanent Residence)
    letter_keywords = [
        'confirmation of permanent residence', 'confirmation of pr', 
        'client copy', 'uci', 'document no', 'app no', 'imm', 
        'confirmation of permanent', 'imm 5688', 'imm 5292'
    ]
    letter_hits = sum(1 for lk in letter_keywords if lk in txt)
    if letter_hits >= 2:
        return ("pr", 0.85, f"LEGACY:pr_letter:strong:{letter_hits}_keywords")
    elif letter_hits == 1 and ('canada' in txt or 'canadian' in txt or 'immigration' in txt):
        return ("pr", 0.75, f"LEGACY:pr_letter:{letter_hits}_keyword+canada")
    
    # ID-number pattern fallback - REQUIRES Canada text to prevent foreign IDs
    try:
        import re
        id_pattern = re.compile(r"\b\d{1,2}[-\s]?\d{3,4}[-\s]?\d{3,4}\b")
        if id_pattern.search(txt):
            supportive = ['permanent', 'permanen', 'resident', 'sident', 'card', 'carte', 'pr', 'permanent resident']
            has_supportive = any(s in txt for s in supportive)
            has_canada = any(sig in txt for sig in ['canada', 'canadian', 'du canada', 'of canada', 'gouvernement'])
            if has_supportive and has_canada:
                return ("pr", 0.8, "LEGACY:id_and_label")
            # ID without Canada text - likely foreign card
    except Exception:
        pass
    
    # Card + country combo
    if (('du canada' in txt or 'of canada' in txt or 'gouvernement' in txt) and
            ('card' in txt or 'carte' in txt)):
        return ("pr", 0.6, "LEGACY:card_country_combo")
    
    # Bilingual government card
    if ('government' in txt and 'gouvernement' in txt and 'canada' in txt):
        if not any(kw in txt for kw in ['driver', 'licence no', 'license no', 'driving', 'republic']):
            return ("pr", 0.75, "LEGACY:bilingual_gov_canada")

    # FINAL REJECTION: Insufficient evidence across all detection methods
    return ("flagged", confidence, f"INSUFFICIENT:{points}pts[{','.join(score_breakdown) if score_breakdown else 'no_features_detected'}]")


# Export new utility
try:
    __all__.append('detect_card_type')
except Exception:
    pass