
from app.study_tools.citations import (
    create_citation,
    create_manual_source,
    create_document_source,
)


# Test 1: Pasted study material
manual_source = create_manual_source(
    text="Volume describes the amount of data.",
    title="Big Data Notes",
)

manual_citation = create_citation(
    manual_source,
    "Volume describes the amount of data.",
)

assert manual_citation["source_id"] == "manual-1"
assert manual_citation["title"] == "Big Data Notes"
assert "page_number" not in manual_citation

print("Manual citation test passed.")


# Test 2: Uploaded PDF metadata
document_source = create_document_source(
    source_id="document-123-page-7",
    filename="Big_Data_Lecture_3.pdf",
    text="Velocity describes how quickly data is generated.",
    course_id=1,
    page_number=7,
)

document_citation = create_citation(
    document_source,
    "Velocity describes how quickly data is generated.",
)

assert document_citation["filename"] == "Big_Data_Lecture_3.pdf"
assert document_citation["page_number"] == 7
assert document_citation["course_id"] == 1

print("Document citation test passed.")

print("All citation tests passed!")