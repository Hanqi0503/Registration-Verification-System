from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from typing import List, Tuple, Dict, Any
import requests
from PIL import Image, ImageOps, ImageFilter

from app.config.config import Config
from app.utils.extraction_tools import fetch_image_bytes  # you already have this

@dataclass
class OCRResult:
    text: str
    blocks: List[Dict[str, Any]]
    tried_variants: int

def _pil_from_bytes(b: bytes) -> Image.Image:
    im = Image.open(BytesIO(b))
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    return im.convert("RGB")

def _preprocess_variants(im: Image.Image) -> List[bytes]:
    variants: List[bytes] = []
    def to_bytes(img: Image.Image) -> bytes:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue()
    variants.append(to_bytes(im))
    g = ImageOps.grayscale(im); g = ImageOps.autocontrast(g)
    variants.append(to_bytes(g))
    thr = g.point(lambda x: 255 if x > 180 else 0)
    variants.append(to_bytes(thr.convert("L")))
    sh = im.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    variants.append(to_bytes(sh))
    return variants

def _ninja_ocr(image_bytes: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    headers = {"X-Api-Key": Config.NINJA_API_KEY}
    files = {"image": ("doc.jpg", image_bytes, "image/jpeg")}
    r = requests.post(Config.NINJA_API_URL, headers=headers, files=files, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "text" in data:
        txt = data.get("text") or ""
        blocks = data.get("data", []) if isinstance(data.get("data"), list) else [{"text": txt}]
        return txt, blocks
    if isinstance(data, list):
        txt = " ".join(b.get("text", "") for b in data)
        return txt, data
    return str(data), []

def ocr_image_from_url(image_url: str) -> OCRResult:
    raw = fetch_image_bytes(image_url)
    im = _pil_from_bytes(raw)
    variants = _preprocess_variants(im)
    best_text = ""; best_blocks: List[Dict[str, Any]] = []
    for vb in variants:
        try:
            t, blks = _ninja_ocr(vb)
            t = (t or "").strip()
            if len(t) > len(best_text):
                best_text, best_blocks = t, blks
        except Exception:
            continue
    return OCRResult(text=best_text, blocks=best_blocks, tried_variants=len(variants))
