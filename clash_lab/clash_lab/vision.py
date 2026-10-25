from __future__ import annotations

from io import BytesIO
from PIL import Image

class VisionError(RuntimeError):
    pass

def png_to_pil(png: bytes) -> Image.Image:
    try:
        return Image.open(BytesIO(png)).convert("RGB")
    except Exception as exc:
        raise VisionError(f"تعذر قراءة لقطة الشاشة: {exc}") from exc

def ocr_text(png: bytes, lang: str = "eng") -> str:
    """Optional OCR. Requires Tesseract installed separately on Windows."""
    try:
        import pytesseract
        return pytesseract.image_to_string(png_to_pil(png), lang=lang)
    except ImportError as exc:
        raise VisionError("OCR غير متاح: ثبّت pytesseract وTesseract OCR.") from exc
    except Exception as exc:
        raise VisionError(f"فشل OCR: {exc}") from exc
