"""Real PaddleOCR provider (Phase 4/2).

Runs PaddleOCR (PP-OCRv5/v6 models) inside the SAME Python 3.10–3.12
environment as the backend. The heavy engine is imported lazily so the API —
and the whole test suite — runs fine without paddle installed;
``OCR_PROVIDER=mock`` never imports it.

Verified on this project's macOS ARM64 host with CPython 3.12:
``paddlepaddle==3.3.1`` + ``paddleocr==3.7.0`` (requirements-ocr.txt).
PDF inputs are rasterised page-by-page with pypdfium2 and OCR'd as images.

Every result is REAL OCR output — never labelled ``mocked`` — and carries the
engine name, the model set, and per-line confidences from PP-OCR.
"""
from __future__ import annotations

import io
import statistics


class PaddleOCRProvider:
    """Real OCR engine behind the OCRProvider protocol."""

    name = "paddleocr"
    mocked = False

    def __init__(self, language: str = "en") -> None:
        self._language = language
        self._engine = None  # constructed lazily on first use

    # -- engine lifecycle -----------------------------------------------------

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR  # heavy import — lazy by design

            self._engine = PaddleOCR(
                lang=self._language,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._engine

    # -- provider protocol ------------------------------------------------------

    async def extract(self, image: bytes, mime_type: str | None = None) -> dict:
        """OCR image bytes (or a PDF's rasterised pages) into text + confidences."""
        pages: list[dict] = []
        if (mime_type or "").lower() == "application/pdf":
            pages = self._pdf_pages(image)
        else:
            pages = self._image_page(image)

        engine = self._get_engine()
        lines_out: list[dict] = []
        for page in pages:
            result = engine.predict(page["source"])
            for entry in result or []:
                texts = entry.get("rec_texts") or []
                scores = entry.get("rec_scores") or []
                boxes = entry.get("rec_polys") or entry.get("dt_polys") or []
                for index, text in enumerate(texts):
                    score = float(scores[index]) if index < len(scores) else None
                    lines_out.append(
                        {
                            "page": page["page_number"],
                            "text": str(text).strip(),
                            "confidence": score,
                            "box": _serialise_box(boxes[index] if index < len(boxes) else None),
                        }
                    )
            if not (result or []):
                lines_out.append(
                    {"page": page["page_number"], "text": "", "confidence": None, "box": None}
                )

        per_page: dict[int, list[dict]] = {}
        for line in lines_out:
            per_page.setdefault(line["page"], []).append(line)

        pages_payload = [
            {
                "page_number": number,
                "lines": [
                    {
                        "text": line["text"],
                        "confidence": line["confidence"],
                        "box": line["box"],
                    }
                    for line in lines
                ],
            }
            for number, lines in sorted(per_page.items())
        ]

        confidences = [
            line["confidence"]
            for line in lines_out
            if line["confidence"] is not None and line["text"]
        ]
        overall = round(statistics.fmean(confidences), 4) if confidences else None

        return {
            "pages": pages_payload,
            "page_count": len(pages_payload),
            "text": "\n".join(
                line["text"]
                for page in pages_payload
                for line in page["lines"]
                if line["text"]
            ),
            "confidence": overall,
            "provider": self.name,
            "mocked": False,
        }

    # -- input decoding ----------------------------------------------------------

    def _image_page(self, image: bytes) -> list[dict]:
        """Decode image bytes to an RGB numpy array (PaddleOCR 3.x wants
        ndarray/str inputs — raw bytes are rejected with
        ``Not supported input data type``)."""
        from PIL import Image

        try:
            pil_image = Image.open(io.BytesIO(image)).convert("RGB")
        except Exception as exc:
            raise ValueError("Unsupported or corrupt image data") from exc
        import numpy as np

        return [{"page_number": 1, "source": np.asarray(pil_image)}]

    def _pdf_pages(self, pdf: bytes) -> list[dict]:
        """Rasterise each PDF page to an RGB ndarray with pypdfium2."""
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(pdf)
        pages: list[dict] = []
        try:
            for index in range(len(doc)):
                bitmap = doc[index].render(scale=2.0)  # ~144 dpi — readable, fast
                pil_image = bitmap.to_pil().convert("RGB")
                import numpy as np

                pages.append(
                    {"page_number": index + 1, "source": np.asarray(pil_image)}
                )
        finally:
            doc.close()
        if not pages:
            raise ValueError("PDF contains no pages")
        return pages


def _serialise_box(box) -> list[list[float]] | None:
    """PP-OCR polygon -> plain nested lists (JSON-safe), or None."""
    if box is None:
        return None
    try:
        return [[float(point[0]), float(point[1])] for point in list(box)]
    except (TypeError, ValueError):
        return None


__all__ = ["PaddleOCRProvider"]
