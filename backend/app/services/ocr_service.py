import csv
import io
import json
import logging
import os
import shutil
from typing import Any

import pypdfium2
import pytesseract
from backend.app.core.exceptions import ValidationException
from backend.app.services.image_processor import image_processor
from backend.app.services.text_cleaner import text_cleaner
from PIL import Image, ImageSequence
from pytesseract import Output

logger = logging.getLogger(__name__)

# Configure Tesseract binary path on Windows if not already in system PATH
if not shutil.which("tesseract"):
    for common_path in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]:
        if os.path.exists(common_path):
            pytesseract.pytesseract.tesseract_cmd = common_path
            logger.info("Configured Tesseract binary at %s", common_path)
            break


class OCRService:
    """Multi-format, multi-page OCR & document parsing engine."""

    @staticmethod
    def rasterize_pdf_to_images(pdf_bytes: bytes, dpi: int = 300) -> list[Image.Image]:
        """Convert multi-page PDF bytes into a list of PIL Images."""
        try:
            pdf_document = pypdfium2.PdfDocument(pdf_bytes)
            pages: list[Image.Image] = []
            scale = dpi / 72.0  # 72 is standard PDF point size

            for page_index in range(len(pdf_document)):
                page = pdf_document[page_index]
                pil_image = page.render(scale=scale).to_pil()
                pages.append(pil_image)

            if not pages:
                raise ValidationException("PDF document has no pages.")
            return pages
        except Exception as exc:
            logger.error("Failed to rasterize PDF: %s", exc)
            raise ValidationException(f"Corrupted or unreadable PDF document: {exc}") from exc

    @staticmethod
    def extract_tiff_pages(tiff_bytes: bytes) -> list[Image.Image]:
        """Extract all pages from a single or multi-page TIFF image."""
        try:
            img = Image.open(io.BytesIO(tiff_bytes))
            pages = [page.copy() for page in ImageSequence.Iterator(img)]
            if not pages:
                raise ValidationException("TIFF image has no valid frames.")
            return pages
        except Exception as exc:
            logger.error("Failed to load TIFF image: %s", exc)
            raise ValidationException(f"Corrupted or invalid TIFF image: {exc}") from exc

    def load_document_pages(self, file_bytes: bytes, extension: str) -> list[Image.Image]:
        """Extract multi-page PIL images for any supported image/document format."""
        clean_ext = extension.lower().lstrip(".")
        if clean_ext == "pdf":
            return self.rasterize_pdf_to_images(file_bytes)
        elif clean_ext in ["tiff", "tif"]:
            return self.extract_tiff_pages(file_bytes)
        elif clean_ext in ["png", "jpg", "jpeg", "bmp", "webp", "gif", "pnm"]:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                return [img]
            except Exception as exc:
                raise ValidationException(f"Corrupted or unreadable image file: {exc}") from exc
        else:
            raise ValidationException(f"Unsupported image/raster file format for OCR: {extension}")

    def ocr_single_page(
        self,
        pil_image: Image.Image,
        page_number: int = 1,
        preprocess: bool = True,
        lang: str = "eng",
    ) -> dict[str, Any]:
        """Run image enhancement and Tesseract OCR on a single page image."""
        try:
            if preprocess:
                _, preprocessed_pil = image_processor.preprocess_pipeline(pil_image)
            else:
                preprocessed_pil = pil_image

            ocr_data = pytesseract.image_to_data(
                preprocessed_pil,
                lang=lang,
                output_type=Output.DICT,
                config="--psm 1",
            )

            words: list[str] = []
            confidences: list[float] = []
            line_words: dict[tuple[str, str, str], list[str]] = {}
            line_order: list[tuple[str, str, str]] = []

            for i in range(len(ocr_data["text"])):
                w = ocr_data["text"][i].strip()
                conf = float(ocr_data["conf"][i])
                if w and conf >= 0:
                    words.append(w)
                    confidences.append(conf)
                    line_key = (
                        str(ocr_data.get("block_num", [0])[i]),
                        str(ocr_data.get("par_num", [0])[i]),
                        str(ocr_data.get("line_num", [i])[i]),
                    )
                    if line_key not in line_words:
                        line_words[line_key] = []
                        line_order.append(line_key)
                    line_words[line_key].append(w)

            raw_text = "\n".join(" ".join(line_words[key]) for key in line_order)
            cleaned = text_cleaner.clean_text(raw_text)
            mean_conf = (sum(confidences) / len(confidences)) / 100.0 if confidences else 0.0

            return {
                "page_number": page_number,
                "raw_text": raw_text,
                "cleaned_text": cleaned,
                "confidence": round(mean_conf, 4),
                "word_count": len(words),
                "is_empty": len(words) == 0,
            }
        except (Exception, SystemExit) as exc:
            logger.warning("OCR page %d execution fallback/error: %s", page_number, exc)
            try:
                raw_text = pytesseract.image_to_string(pil_image, lang=lang)
                cleaned = text_cleaner.clean_text(raw_text)
                return {
                    "page_number": page_number,
                    "raw_text": raw_text,
                    "cleaned_text": cleaned,
                    "confidence": 0.50 if cleaned else 0.0,
                    "word_count": len(cleaned.split()),
                    "is_empty": len(cleaned) == 0,
                }
            except (Exception, SystemExit) as final_exc:
                logger.warning(
                    "Tesseract binary not available or failed on page %d: %s. Returning fallback.",
                    page_number,
                    final_exc,
                )
                return {
                    "page_number": page_number,
                    "raw_text": "",
                    "cleaned_text": "",
                    "confidence": 0.0,
                    "word_count": 0,
                    "is_empty": True,
                }

    def process_document(
        self,
        file_bytes: bytes,
        extension: str,
        lang: str = "eng",
    ) -> dict[str, Any]:
        """Run end-to-end OCR / document parsing pipeline on all pages of a document."""
        clean_ext = extension.lower().lstrip(".")

        # 1. Handle JSON document parsing
        if clean_ext == "json":
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
                data_obj = json.loads(text_content)
                text_lines = []
                if isinstance(data_obj, dict):
                    for k, v in data_obj.items():
                        text_lines.append(f"{k}: {v}")
                elif isinstance(data_obj, list):
                    for idx, item in enumerate(data_obj, start=1):
                        text_lines.append(f"Item {idx}: {item}")
                else:
                    text_lines.append(str(data_obj))
                formatted_text = "\n".join(text_lines) if text_lines else text_content
                stats = text_cleaner.get_text_statistics(formatted_text)
                return {
                    "total_pages": 1,
                    "overall_confidence": 1.0,
                    "full_text": formatted_text,
                    "statistics": stats,
                    "pages": [
                        {
                            "page_number": 1,
                            "raw_text": text_content,
                            "cleaned_text": formatted_text,
                            "confidence": 1.0,
                            "word_count": len(formatted_text.split()),
                            "is_empty": False,
                        }
                    ],
                }
            except Exception as json_err:
                logger.warning("JSON parsing error, treating as raw text: %s", json_err)

        # 2. Handle CSV document parsing
        if clean_ext == "csv":
            try:
                text_content = file_bytes.decode("utf-8-sig", errors="replace")
                reader = csv.reader(io.StringIO(text_content))
                rows = list(reader)
                text_lines = []
                if rows:
                    headers = rows[0]
                    for row in rows[1:]:
                        row_items = []
                        for h_idx, col in enumerate(row):
                            h_name = headers[h_idx] if h_idx < len(headers) else f"Col{h_idx + 1}"
                            row_items.append(f"{h_name}: {col}")
                        text_lines.append(" | ".join(row_items))
                formatted_text = "\n".join(text_lines) if text_lines else text_content
                stats = text_cleaner.get_text_statistics(formatted_text)
                return {
                    "total_pages": 1,
                    "overall_confidence": 1.0,
                    "full_text": formatted_text,
                    "statistics": stats,
                    "pages": [
                        {
                            "page_number": 1,
                            "raw_text": text_content,
                            "cleaned_text": formatted_text,
                            "confidence": 1.0,
                            "word_count": len(formatted_text.split()),
                            "is_empty": False,
                        }
                    ],
                }
            except Exception as csv_err:
                logger.warning("CSV parsing error, treating as raw text: %s", csv_err)

        # 3. Handle Plain Text / Word / Excel / Log / Markdown
        if clean_ext in ["txt", "log", "md", "docx", "doc", "xlsx", "xls"]:
            try:
                text_content = file_bytes.decode("utf-8", errors="replace").strip()
                cleaned = text_cleaner.clean_text(text_content)
                stats = text_cleaner.get_text_statistics(cleaned)
                return {
                    "total_pages": 1,
                    "overall_confidence": 1.0,
                    "full_text": cleaned,
                    "statistics": stats,
                    "pages": [
                        {
                            "page_number": 1,
                            "raw_text": text_content,
                            "cleaned_text": cleaned,
                            "confidence": 1.0,
                            "word_count": len(cleaned.split()),
                            "is_empty": len(cleaned) == 0,
                        }
                    ],
                }
            except Exception as text_err:
                logger.warning("Text format decoding error: %s", text_err)

        # 4. If PDF, attempt native embedded text extraction first
        if clean_ext == "pdf":
            try:
                pdf_document = pypdfium2.PdfDocument(file_bytes)
                total_pages = len(pdf_document)
                page_results: list[dict[str, Any]] = []
                all_text_chunks: list[str] = []

                for page_idx in range(total_pages):
                    page = pdf_document[page_idx]
                    text_page = page.get_textpage()
                    extracted_text = text_page.get_text_range() or ""
                    cleaned = text_cleaner.clean_text(extracted_text)
                    if cleaned:
                        all_text_chunks.append(cleaned)
                    page_results.append(
                        {
                            "page_number": page_idx + 1,
                            "raw_text": extracted_text,
                            "cleaned_text": cleaned,
                            "confidence": 0.95 if cleaned else 0.0,
                            "word_count": len(cleaned.split()),
                            "is_empty": len(cleaned) == 0,
                        }
                    )

                full_text = "\n\n--- Page Break ---\n\n".join(all_text_chunks)
                total_word_count = sum(len(c.split()) for c in all_text_chunks)

                # If native text is substantial (> 10 words), return native text extraction
                if full_text.strip() and total_word_count >= 10:
                    stats = text_cleaner.get_text_statistics(full_text)
                    return {
                        "total_pages": total_pages,
                        "overall_confidence": 0.95,
                        "full_text": full_text,
                        "statistics": stats,
                        "pages": page_results,
                    }
                else:
                    logger.info(
                        "PDF has minimal native text (%d words). Falling through to OCR scanner.",
                        total_word_count,
                    )
            except Exception as pdf_err:
                logger.warning(
                    "Native PDF text extraction failed, falling back to rasterization: %s", pdf_err
                )

        # 5. Fallback to rasterization and Tesseract OCR scanner for scanned documents or images
        pages = self.load_document_pages(file_bytes, extension)
        total_pages = len(pages)

        if total_pages == 0:
            raise ValidationException("Document contains no readable pages.")

        page_results = []
        all_text_chunks = []
        total_confidence = 0.0

        for idx, page_img in enumerate(pages, start=1):
            res = self.ocr_single_page(page_img, page_number=idx, lang=lang)
            page_results.append(res)
            if res["cleaned_text"]:
                all_text_chunks.append(res["cleaned_text"])
            total_confidence += res["confidence"]

        overall_confidence = round(total_confidence / total_pages, 4) if total_pages > 0 else 0.0
        full_cleaned_text = "\n\n--- Page Break ---\n\n".join(all_text_chunks)
        stats = text_cleaner.get_text_statistics(full_cleaned_text)

        return {
            "total_pages": total_pages,
            "overall_confidence": overall_confidence,
            "full_text": full_cleaned_text,
            "statistics": stats,
            "pages": page_results,
        }


ocr_service = OCRService()
