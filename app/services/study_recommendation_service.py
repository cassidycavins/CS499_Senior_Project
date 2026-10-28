from datetime import datetime, timedelta

def calculate_topic_scores(topic_records):
    """Calculate average performance for each topic."""

    topic_totals = {}

    for record in topic_records:
        topic = record.topic

        if topic not in topic_totals:
            topic_totals[topic] = {
                "correct": 0,
                "total": 0,
            }

        topic_totals[topic]["correct"] += record.correct_answers
        topic_totals[topic]["total"] += record.total_questions

    topic_scores = []

    for topic, results in topic_totals.items():

        if results["total"] == 0:
            continue

        score = (
            results["correct"] / results["total"]
        ) * 100

        topic_scores.append({
            "topic": topic,
            "score": round(score, 2),
        })

    # Prioritize topics with the lowest scores.
    topic_scores.sort(key=lambda item: item["score"])

    return topic_scores


def generate_study_recommendations(
    topic_records,
    available_slots,
    max_recommendations=5,
    session_minutes=60,
    weak_threshold=70,
):
    """Recommend non-overlapping sessions for weak topics."""

    topic_scores = calculate_topic_scores(topic_records)

    # Only recommend topics below the performance threshold.
    weak_topics = [
        topic for topic in topic_scores
        if topic["score"] < weak_threshold
    ]

    recommendations = []
    used_slots = set()

    # Schedule the weakest topics first.
    for topic in weak_topics:

        if len(recommendations) >= max_recommendations:
            break

        for index, slot in enumerate(available_slots):

            if index in used_slots:
                continue

            start = datetime.fromisoformat(slot["start"])
            end = datetime.fromisoformat(slot["end"])

            session_end = start + timedelta(
                minutes=session_minutes
            )

            # Skip slots too short for the study session.
            if session_end > end:
                continue

            recommendations.append({
                "topic": topic["topic"],
                "score": topic["score"],
                "start": start.isoformat(),
                "end": session_end.isoformat(),
                "status": "pending",
            })

            used_slots.add(index)
            break

    return recommendations