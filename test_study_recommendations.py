from types import SimpleNamespace

from app.services.study_recommendation_service import (
    calculate_topic_scores,
)


def test_topic_scores():

    records = [
        SimpleNamespace(
            topic="Networking",
            correct_answers=2,
            total_questions=5,
        ),
        SimpleNamespace(
            topic="Encryption",
            correct_answers=4,
            total_questions=5,
        ),
        SimpleNamespace(
            topic="Networking",
            correct_answers=3,
            total_questions=5,
        ),
    ]

    results = calculate_topic_scores(records)

    assert len(results) == 2

    assert results[0]["topic"] == "Networking"
    assert results[0]["score"] == 50.0

    assert results[1]["topic"] == "Encryption"
    assert results[1]["score"] == 80.0

    print("Study recommendation score tests passed.")

def test_study_recommendations():

    from app.services.study_recommendation_service import (
        generate_study_recommendations,
    )

    records = [
        SimpleNamespace(
            topic="Networking",
            correct_answers=2,
            total_questions=5,
        ),
        SimpleNamespace(
            topic="Encryption",
            correct_answers=4,
            total_questions=5,
        ),
        SimpleNamespace(
            topic="Operating Systems",
            correct_answers=3,
            total_questions=5,
        ),
    ]

    slots = [
        {
            "start": "2026-11-02T08:00:00-06:00",
            "end": "2026-11-02T10:00:00-06:00",
        },
        {
            "start": "2026-11-03T13:00:00-06:00",
            "end": "2026-11-03T15:00:00-06:00",
        },
    ]

    results = generate_study_recommendations(records, slots)

    assert len(results) == 2
    assert results[0]["topic"] == "Networking"
    assert results[1]["topic"] == "Operating Systems"

    assert results[0]["status"] == "pending"
    assert results[1]["status"] == "pending"

    assert results[0]["start"] != results[1]["start"]

    print("Study recommendation scheduling tests passed.")

if __name__ == "__main__":
    test_topic_scores()
    test_study_recommendations()