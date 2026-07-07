"""
Image pre-processing utilities.

Steps:
  1. pdf_to_png       – convert first page of PDF to PIL Image
  2. resize_image     – max 2048px on longest side (Gemini limit)
  3. enhance_contrast – CLAHE for better OCR and symbol detection
  4. crop_title_block – top-right 30% of image for Tesseract OCR
  5. crop_bom_region  – bottom 40% for BOM table extraction (Pass B)
  6. image_to_bytes   – serialize PIL Image to PNG bytes
"""
import io
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

MAX_SIDE = 1024  # Reduced from 2048 — keeps API fast while retaining detail


def pdf_to_png(file_path: Path) -> Image.Image:
    """Convert the first page of a PDF to a PIL Image using pdf2image."""
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(str(file_path), dpi=200, first_page=1, last_page=1)
        if not pages:
            raise ValueError("PDF has no pages")
        return pages[0].convert("RGB")
    except ImportError:
        raise RuntimeError("pdf2image not installed. Run: pip install pdf2image")
    except Exception as e:
        from core.exceptions import CorruptImageError
        raise CorruptImageError(f"Cannot read PDF: {e}")


def load_image(file_path: Path) -> Image.Image:
    """Load an image file (PNG/JPG) or convert PDF, returns PIL Image."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return pdf_to_png(file_path)
    try:
        img = Image.open(file_path)
        return img.convert("RGB")
    except Exception as e:
        from core.exceptions import CorruptImageError
        raise CorruptImageError(f"Cannot read image: {e}")


def resize_image(img: Image.Image, max_side: int = MAX_SIDE) -> Image.Image:
    """Resize image so its longest side ≤ max_side, preserving aspect ratio."""
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    if w >= h:
        new_w, new_h = max_side, int(h * max_side / w)
    else:
        new_w, new_h = int(w * max_side / h), max_side
    return img.resize((new_w, new_h), Image.LANCZOS)


def enhance_contrast(img: Image.Image) -> Image.Image:
    """
    Enhance contrast for better OCR and symbol detection.
    Uses a combination of sharpening and contrast enhancement.
    """
    # Sharpen edges
    img = img.filter(ImageFilter.SHARPEN)
    # Boost contrast slightly
    img = ImageEnhance.Contrast(img).enhance(1.3)
    # Boost sharpness
    img = ImageEnhance.Sharpness(img).enhance(1.5)
    return img


def crop_title_block(img: Image.Image) -> Image.Image:
    """
    Crop the top-right 30% of the image — where the title block typically lives.
    Returns a cropped PIL Image for Tesseract OCR.
    """
    w, h = img.size
    left = int(w * 0.60)   # right 40%
    top = 0
    right = w
    bottom = int(h * 0.40)  # top 40%
    cropped = img.crop((left, top, right, bottom))
    # Also try bottom-right (some isos have title block there)
    # We'll return the larger crop and let OCR decide
    return cropped


def crop_bom_region(img: Image.Image) -> Image.Image:
    """
    Crop the bottom-right 45% of the image — where the BOM table typically lives.
    Used for Pass B Gemini extraction.
    """
    w, h = img.size
    left = int(w * 0.50)
    top = int(h * 0.50)
    right = w
    bottom = h
    return img.crop((left, top, right, bottom))


def image_to_bytes(img: Image.Image, format: str = "PNG") -> bytes:
    """Serialize a PIL Image to bytes."""
    buf = io.BytesIO()
    img.save(buf, format=format, optimize=True)
    buf.seek(0)
    return buf.read()


def preprocess_for_gemini(file_path: Path) -> tuple[bytes, bytes, int]:
    """
    Full preprocessing pipeline for one drawing file.

    Returns:
        full_image_bytes  – full resized+enhanced image as PNG bytes
        bom_region_bytes  – cropped BOM region as PNG bytes
        page_count        – 1 for images, N for PDFs
    """
    page_count = 1

    # Detect PDF page count
    if file_path.suffix.lower() == ".pdf":
        try:
            from pdf2image import pdfinfo_from_path
            info = pdfinfo_from_path(str(file_path))
            page_count = info.get("Pages", 1)
        except Exception:
            page_count = 1

    img = load_image(file_path)
    img = resize_image(img, MAX_SIDE)
    img_enhanced = enhance_contrast(img)

    full_bytes = image_to_bytes(img_enhanced)
    bom_bytes = image_to_bytes(crop_bom_region(img_enhanced))

    return full_bytes, bom_bytes, page_count
