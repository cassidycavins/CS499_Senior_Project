
from pathlib import Path

import pymupdf


def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extract readable text from a PDF document.

    Args:
        file_path: Location of the PDF file.

    Returns:
        Extracted text as a string.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF cannot be read or has no
                    extractable text.
    """

    pdf_path = Path(file_path)

    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"PDF file not found: {pdf_path}"
        )

    extracted_pages = []

    try:
        with pymupdf.open(str(pdf_path)) as document:

            if document.needs_pass:
                raise ValueError(
                    "Password-protected PDFs are not supported."
                )

            for page in document:
                page_text = page.get_text("text")

                if page_text and page_text.strip():
                    extracted_pages.append(
                        page_text.strip()
                    )

    except (ValueError, FileNotFoundError):
        raise

    except Exception as error:
        raise ValueError(
            "Unable to extract text from this PDF."
        ) from error

    extracted_text = "\n\n".join(extracted_pages).strip()

    if not extracted_text:
        raise ValueError(
            "No extractable text found. "
            "The PDF may contain scanned images."
        )

    return extracted_text
