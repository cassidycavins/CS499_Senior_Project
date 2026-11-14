
from app.study_tools.citations import (
    create_citation,
    create_manual_source,
    create_document_source,
)


def test_manual_source_citation():
    """Verify citation metadata for manually entered study material."""
    source = create_manual_source(
        text="Volume describes the amount of data.",
        title="Big Data Notes",
    )

    citation = create_citation(
        source,
        "Volume describes the amount of data.",
    )

    assert citation["source_id"] == "manual-1"
    assert citation["title"] == "Big Data Notes"
    assert "page_number" not in citation


def test_pdf_source_citation():
    """Verify citation metadata for an uploaded PDF."""
    source = create_document_source(
        source_id="document-123-page-7",
        filename="Big_Data_Lecture_3.pdf",
        text="Velocity describes how quickly data is generated.",
        course_id=1,
        page_number=7,
    )

    citation = create_citation(
        source,
        "Velocity describes how quickly data is generated.",
    )

    assert citation["filename"] == "Big_Data_Lecture_3.pdf"
    assert citation["page_number"] == 7
    assert citation["course_id"] == 1