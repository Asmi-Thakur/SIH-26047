"""OCR service package (Phase 4/2).

- ``registry``  : OCR_PROVIDER selection (mock | paddleocr | auto).
- ``mock``      : honest deterministic fixture provider (``mocked: true``).
- ``paddle``    : real PaddleOCR engine (lazy import; py3.10–3.12).
- ``extract``   : classification + deterministic clinical extraction.
- ``service``   : document processing lifecycle used by the reprocess API.
"""
