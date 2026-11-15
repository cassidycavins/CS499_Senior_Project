
from app.study_tools.source_verifier import verify_flashcard


source_text = (
    "Volume describes the amount of data being "
    "collected and stored. "
    "Velocity describes how quickly data is "
    "generated, transmitted, and processed."
)


supported_card = {
    "front": "What does Volume describe in Big Data?",
    "back": "The amount of data being collected and stored.",
    "citation": {
        "source_id": "manual-1",
        "title": "Big Data Notes",
        "excerpt": (
            "Volume describes the amount of data "
            "being collected and stored."
        ),
    },
}


unsupported_card = {
    "front": "What does Volume describe in Big Data?",
    "back": "How quickly data is generated and processed.",
    "citation": {
        "source_id": "manual-1",
        "title": "Big Data Notes",
        "excerpt": (
            "Volume describes the amount of data "
            "being collected and stored."
        ),
    },
}


print("Testing supported flashcard...")

supported_result = verify_flashcard(
    supported_card,
    source_text,
)

print("Supported card accepted:", supported_result)


print("\nTesting unsupported flashcard...")

unsupported_result = verify_flashcard(
    unsupported_card,
    source_text,
)

print("Unsupported card accepted:", unsupported_result)


assert supported_result is True, (
    "A supported flashcard was incorrectly rejected."
)

assert unsupported_result is False, (
    "An unsupported flashcard was incorrectly accepted."
)

print("\nAll flashcard verification tests passed!")