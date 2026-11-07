"""Bounded extraction of user-supplied PDFs. No URL fetches or OCR."""
import pymupdf

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 100
MAX_CHARACTERS = 1_000_000


class PDFError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def extract_pages(content: bytes) -> list[tuple[int, str]]:
    if len(content) > MAX_BYTES:
        raise PDFError("oversized", "PDF exceeds the 5 MB limit.")
    if not content.startswith(b"%PDF-"):
        raise PDFError("malformed", "The file does not have a PDF header.")
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise PDFError("encrypted", "Password-protected PDFs are not supported.")
            if len(pdf) > MAX_PAGES:
                raise PDFError("oversized", "PDF exceeds the 100-page limit.")
            pages = []
            count = 0
            for number, page in enumerate(pdf, 1):
                text = page.get_text("text", sort=True).strip()
                count += len(text)
                if count > MAX_CHARACTERS:
                    raise PDFError("oversized", "Extracted text exceeds the document limit.")
                pages.append((number, text))
            if not any(text for _, text in pages):
                raise PDFError("scanned_or_empty", "No extractable text. Upload a text PDF; OCR is unavailable.")
            return pages
    except PDFError:
        raise
    except Exception:
        raise PDFError("malformed", "The PDF could not be read.") from None
