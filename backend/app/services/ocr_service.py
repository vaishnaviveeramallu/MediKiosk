import os
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from PIL import Image, ImageOps
import pytesseract
from pypdf import PdfReader

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    raw_text: str
    page_count: int
    engine: str
    languages: List[str]
    confidence: Optional[float]
    processing_time_ms: int
    handwritten_detected: bool = False
    handwriting_disclaimer: Optional[str] = None
    is_empty: bool = False
    error: Optional[str] = None


class OCRService:
    """
    Modular OCR Service for MediKiosk.
    Supports digital text-based PDFs (pypdf), scanned image PDFs, and standalone images (PNG, JPEG).
    Utilizes local Tesseract engine for English and Hindi recognition.
    """

    def __init__(self):
        self._setup_tesseract()

    def _setup_tesseract(self):
        """Configure Tesseract binary and data paths."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        default_cmd = os.path.join(base_dir, "tesseract_portable", "tesseract.exe")
        default_data = os.path.join(base_dir, "tesseract_portable", "tessdata")

        tess_cmd = settings.TESSERACT_CMD or (default_cmd if os.path.exists(default_cmd) else "tesseract")
        tess_data = settings.TESSDATA_PREFIX or (default_data if os.path.exists(default_data) else None)

        pytesseract.pytesseract.tesseract_cmd = tess_cmd
        if tess_data and os.path.exists(tess_data):
            os.environ["TESSDATA_PREFIX"] = tess_data

        self.tesseract_available = os.path.exists(tess_cmd) or self._check_cli_tesseract()
        logger.info(f"OCRService initialized. Tesseract cmd: {tess_cmd}, Available: {self.tesseract_available}")

    def _check_cli_tesseract(self) -> bool:
        try:
            import subprocess
            r = subprocess.run([pytesseract.pytesseract.tesseract_cmd, "--version"], capture_output=True)
            return r.returncode == 0
        except Exception:
            return False

    def extract_from_file(
        self,
        file_path: str,
        content_type: str,
        preferred_language: Optional[str] = None,
    ) -> OCRResult:
        """
        Execute OCR / text extraction on an uploaded file.
        """
        start_time = time.time()

        file_path_str = str(file_path)
        if not os.path.exists(file_path_str):
            return OCRResult(
                raw_text="",
                page_count=0,
                engine="none",
                languages=[],
                confidence=0.0,
                processing_time_ms=0,
                is_empty=True,
                error="File not found on storage"
            )

        # Normalize content type or extension
        is_pdf = content_type == "application/pdf" or file_path_str.lower().endswith(".pdf")

        try:
            if is_pdf:
                result = self._extract_pdf(file_path_str, preferred_language)
            else:
                result = self._extract_image(file_path_str, preferred_language)

            elapsed_ms = int((time.time() - start_time) * 1000)
            result.processing_time_ms = elapsed_ms
            return result

        except Exception as e:
            logger.error(f"Error during OCR extraction for {file_path}: {e}", exc_info=True)
            elapsed_ms = int((time.time() - start_time) * 1000)
            return OCRResult(
                raw_text="",
                page_count=1,
                engine="error",
                languages=[],
                confidence=0.0,
                processing_time_ms=elapsed_ms,
                is_empty=True,
                error=f"OCR extraction failed: {str(e)}"
            )

    def _extract_pdf(self, file_path: str, preferred_language: Optional[str] = None) -> OCRResult:
        """Extract text from PDF: digital text first, image OCR as fallback for scanned pages."""
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)
        max_pages = min(total_pages, settings.OCR_MAX_PAGES)

        extracted_pages: List[str] = []
        has_selectable_text = False

        # Attempt 1: Extract selectable digital text
        for i in range(max_pages):
            page = reader.pages[i]
            page_text = page.extract_text() or ""
            if len(page_text.strip()) > 10:
                has_selectable_text = True
            extracted_pages.append(page_text.strip())

        full_text = "\n\n".join(p for p in extracted_pages if p)

        if has_selectable_text and len(full_text) > 25:
            # Successfully extracted digital PDF text
            return OCRResult(
                raw_text=full_text,
                page_count=max_pages,
                engine="pypdf_digital",
                languages=["eng"],
                confidence=0.96,
                processing_time_ms=0,
                handwritten_detected=False,
                is_empty=False
            )

        # Attempt 2: PDF is scanned or image-based. Extract embedded images per page.
        image_texts: List[str] = []
        total_confidences: List[float] = []

        lang = self._get_ocr_lang(preferred_language)

        for i in range(max_pages):
            page = reader.pages[i]
            page_images = page.images
            page_extracted = ""

            for img_file in page_images:
                try:
                    import io
                    pil_img = Image.open(io.BytesIO(img_file.data))
                    txt, conf = self._run_tesseract(pil_img, lang)
                    if txt:
                        page_extracted += "\n" + txt
                    if conf is not None:
                        total_confidences.append(conf)
                except Exception as img_err:
                    logger.warning(f"Could not OCR embedded image on page {i}: {img_err}")

            if page_extracted.strip():
                image_texts.append(page_extracted.strip())

        combined_text = "\n\n".join(image_texts) if image_texts else full_text

        avg_conf = (sum(total_confidences) / len(total_confidences)) if total_confidences else (0.80 if combined_text else 0.0)
        is_empty = len(combined_text.strip()) == 0

        handwritten = False
        disclaimer = None
        if not is_empty and avg_conf < 0.65:
            handwritten = True
            disclaimer = "Handwritten text may require physician verification."

        return OCRResult(
            raw_text=combined_text,
            page_count=max_pages,
            engine="tesseract_pdf_images",
            languages=lang.split("+"),
            confidence=round(avg_conf, 2),
            processing_time_ms=0,
            handwritten_detected=handwritten,
            handwriting_disclaimer=disclaimer,
            is_empty=is_empty
        )

    def _extract_image(self, file_path: str, preferred_language: Optional[str] = None) -> OCRResult:
        """Extract text from standalone image (JPG, PNG)."""
        pil_img = Image.open(file_path)
        # Convert RGBA/P to RGB
        if pil_img.mode not in ("RGB", "L"):
            pil_img = pil_img.convert("RGB")

        lang = self._get_ocr_lang(preferred_language)
        text, avg_conf = self._run_tesseract(pil_img, lang)

        is_empty = len(text.strip()) == 0
        conf = round(avg_conf, 2) if avg_conf is not None else (0.85 if not is_empty else 0.0)

        handwritten = False
        disclaimer = None
        if not is_empty and conf < 0.65:
            handwritten = True
            disclaimer = "Handwritten text may require physician verification."

        return OCRResult(
            raw_text=text,
            page_count=1,
            engine="tesseract_image",
            languages=lang.split("+"),
            confidence=conf,
            processing_time_ms=0,
            handwritten_detected=handwritten,
            handwriting_disclaimer=disclaimer,
            is_empty=is_empty
        )

    def _get_ocr_lang(self, preferred_language: Optional[str] = None) -> str:
        """Select appropriate OCR language argument."""
        if preferred_language in ("hi", "hin", "hindi"):
            return "hin+eng"
        return settings.OCR_DEFAULT_LANGUAGES or "eng+hin"

    def _run_tesseract(self, img: Image.Image, lang: str) -> Tuple[str, Optional[float]]:
        """Run pytesseract and calculate average word confidence."""
        try:
            # Try combined or fallback to eng if language model not found
            try:
                text = pytesseract.image_to_string(img, lang=lang)
            except Exception:
                text = pytesseract.image_to_string(img, lang="eng")
                lang = "eng"

            # Compute average confidence from word-level data
            try:
                data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
                confs = [int(c) for c in data.get("conf", []) if str(c).isdigit() and int(c) >= 0]
                avg_conf = (sum(confs) / len(confs) / 100.0) if confs else None
            except Exception:
                avg_conf = None

            return text.strip(), avg_conf

        except Exception as e:
            logger.error(f"Tesseract execution failed: {e}")
            raise e


# Singleton service instance
ocr_service = OCRService()
