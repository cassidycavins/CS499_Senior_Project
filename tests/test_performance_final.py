
import unittest

from app.services.performance_service import (
    calculate_quiz_score,
    classify_performance,
    identify_weak_topics,
    calculate_average_score
)


class TestQuizPerformance(unittest.TestCase):
    """Verify quiz calculations and knowledge-gap detection."""

    def test_quiz_score(self):
        # Verify correct percentage calculation.
        self.assertEqual(calculate_quiz_score(8, 10), 80)
        self.assertEqual(calculate_quiz_score(0, 10), 0)
        self.assertEqual(calculate_quiz_score(10, 10), 100)

    def test_invalid_quiz(self):
        # Reject invalid question counts.
        with self.assertRaises(ValueError):
            calculate_quiz_score(5, 0)

        with self.assertRaises(ValueError):
            calculate_quiz_score(11, 10)

    def test_performance_classification(self):
        self.assertEqual(
            classify_performance(55), "Needs Improvement"
        )
        self.assertEqual(
            classify_performance(75), "Developing"
        )
        self.assertEqual(
            classify_performance(90), "Proficient"
        )

    def test_weak_topics(self):
        # Only topics scoring below 70% should be flagged.
        topics = {
            "Memory Management": {"correct": 4, "total": 10},
            "Process Scheduling": {"correct": 8, "total": 10},
            "File Systems": {"correct": 9, "total": 10}
        }

        weak_topics = identify_weak_topics(topics)

        self.assertEqual(len(weak_topics), 1)
        self.assertEqual(
            weak_topics[0]["topic"], "Memory Management"
        )

    def test_average_score(self):
        self.assertEqual(
            calculate_average_score([70, 80, 90]), 80.0
        )
        self.assertEqual(calculate_average_score([]), 0)


if __name__ == "__main__":
    unittest.main()
