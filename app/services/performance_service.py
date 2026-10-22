
def calculate_quiz_score(correct_answers, total_questions):
    """Calculate the percentage of correctly answered quiz questions."""

    # Validate question counts before calculating the score.
    if total_questions <= 0:
        raise ValueError("Total questions must be greater than zero.")

    if correct_answers < 0 or correct_answers > total_questions:
        raise ValueError("Invalid number of correct answers.")

    score = (correct_answers / total_questions) * 100

    return round(score)


def classify_performance(score):
    """Classify student performance based on quiz percentage."""

    if not 0 <= score <= 100:
        raise ValueError("Score must be between 0 and 100.")

    # Assign a category based on the student's score.
    if score < 60:
        return "Needs Improvement"
    elif score < 80:
        return "Developing"
    else:
        return "Proficient"


def identify_weak_topics(topic_results):
    """Identify topics with quiz scores below 70%."""

    weak_topics = []

    for topic, results in topic_results.items():

        score = calculate_quiz_score(
            results["correct"],
            results["total"]
        )

        # Flag topics that need additional review.
        if score < 70:
            weak_topics.append({
                "topic": topic,
                "score": score,
                "status": "Needs Review"
            })

    return weak_topics


def calculate_average_score(quiz_scores):
    """Calculate the average percentage across completed quizzes."""

    # Return zero when no quiz attempts are available.
    if not quiz_scores:
        return 0

    average = sum(quiz_scores) / len(quiz_scores)

    return round(average, 2)
