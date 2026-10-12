from typing import List, Optional
from app.models.learner_mastery import LearnerMastery
from app.schemas.learner import RecommendationItem
from app.services.learner_model.weak_topics import WeakTopicDetector
from app.core.config import settings

class RecommendationEngine:
    def __init__(
        self,
        weak_detector: Optional[WeakTopicDetector] = None,
        weak_threshold: Optional[float] = None,
        strong_threshold: Optional[float] = None
    ):
        self.weak_detector = weak_detector or WeakTopicDetector(
            weak_threshold=weak_threshold,
            strong_threshold=strong_threshold
        )
        self.weak_threshold = weak_threshold if weak_threshold is not None else settings.MASTERY_WEAK_THRESHOLD
        self.strong_threshold = strong_threshold if strong_threshold is not None else settings.MASTERY_STRONG_THRESHOLD

    def generate_recommendations(self, records: List[LearnerMastery]) -> List[RecommendationItem]:
        """
        Generates personalized learning recommendations grounded in real student mastery data.
        Determines target topic, recommended action, difficulty, and question count.
        """
        # Case 1: New learner (no prior assessment interaction)
        if not records:
            return [
                RecommendationItem(
                    topic="Course Foundations",
                    priority="high",
                    reason="New learner - take initial assessment to establish baseline mastery",
                    recommended_action="diagnostic",
                    recommended_difficulty="medium",
                    recommended_question_count=5
                )
            ]

        recommendations: List[RecommendationItem] = []

        # Sort all records by mastery score ascending (weakest first)
        sorted_records = sorted(records, key=lambda r: (r.mastery_score, r.confidence))

        # Check for weak topics
        weak_topics = [r for r in sorted_records if self.weak_detector.is_weak(r)]

        if weak_topics:
            # Primary weak topic (lowest score) gets highest priority
            lowest = weak_topics[0]
            difficulty = "easy" if lowest.mastery_score < 0.40 else "medium"
            recommendations.append(
                RecommendationItem(
                    topic=lowest.topic,
                    priority="high",
                    reason="Lowest current mastery",
                    recommended_action="practice",
                    recommended_difficulty=difficulty,
                    recommended_question_count=5
                )
            )

            # Secondary weak topics
            for sec in weak_topics[1:]:
                recommendations.append(
                    RecommendationItem(
                        topic=sec.topic,
                        priority="medium",
                        reason=self.weak_detector.explain_weakness(sec),
                        recommended_action="practice",
                        recommended_difficulty="medium",
                        recommended_question_count=5
                    )
                )

        # Check for moderate topics (between weak and strong thresholds)
        moderate_topics = [
            r for r in sorted_records
            if self.weak_threshold <= r.mastery_score < self.strong_threshold
        ]
        for mod in moderate_topics:
            recommendations.append(
                RecommendationItem(
                    topic=mod.topic,
                    priority="medium",
                    reason="Moderate mastery - practice recommended to achieve proficiency",
                    recommended_action="practice",
                    recommended_difficulty="medium",
                    recommended_question_count=5
                )
            )

        # If all topics are strong (mastery >= strong_threshold)
        if not weak_topics and not moderate_topics and sorted_records:
            top = sorted_records[-1]
            recommendations.append(
                RecommendationItem(
                    topic=top.topic,
                    priority="low",
                    reason="High proficiency achieved - test with advanced questions",
                    recommended_action="challenge",
                    recommended_difficulty="hard",
                    recommended_question_count=5
                )
            )

        return recommendations

    def get_next_practice_session(self, records: List[LearnerMastery]) -> RecommendationItem:
        """Determines the single most impactful next practice session for the student."""
        recs = self.generate_recommendations(records)
        return recs[0]
