
from dataclasses import dataclass
from typing import Optional


@dataclass
class SourceReference:
    """
    Represents the original source of study content.

    Can support pasted text or extracted documents.
    """

    source_id: str
    title: str
    text: str

    # Optional document metadata
    filename: Optional[str] = None
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    course_id: Optional[int] = None


def create_citation(
    source: SourceReference,
    excerpt: str,
) -> dict:
    """
    Build a consistent citation object.
    """

    citation = {
        "source_id": source.source_id,
        "title": source.title,
        "excerpt": excerpt,
    }

    if source.filename is not None:
        citation["filename"] = source.filename

    if source.page_number is not None:
        citation["page_number"] = source.page_number

    if source.slide_number is not None:
        citation["slide_number"] = source.slide_number

    if source.course_id is not None:
        citation["course_id"] = source.course_id

    return citation


def create_manual_source(
    text: str,
    title: str = "Pasted study material",
) -> SourceReference:
    """
    Create a source reference for pasted notes.
    """

    return SourceReference(
        source_id="manual-1",
        title=title,
        text=text,
    )


def create_document_source(
    source_id: str,
    filename: str,
    text: str,
    course_id: Optional[int] = None,
    page_number: Optional[int] = None,
    slide_number: Optional[int] = None,
) -> SourceReference:
    """
    Create a source reference for extracted
    document text.

    The upload/extraction code will eventually
    supply this metadata.
    """

    return SourceReference(
        source_id=source_id,
        title=filename,
        filename=filename,
        text=text,
        course_id=course_id,
        page_number=page_number,
        slide_number=slide_number,
    )