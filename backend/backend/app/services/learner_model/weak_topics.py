from typing import List, Optional
from app.models.learner_mastery import LearnerMastery
from app.schemas.learner import WeakTopicSummaryItem
from app.core.config import settings

class WeakTopicDetector:
    def __init__(
        self,
        weak_threshold: Optional[float] = None,
        strong_threshold: Optional[float] = None
    ):
        self.weak_threshold = weak_threshold if weak_threshold is not None else settings.MASTERY_WEAK_THRESHOLD
        self.strong_threshold = strong_threshold if strong_threshold is not None else settings.MASTERY_STRONG_THRESHOLD

    def is_weak(self, record: LearnerMastery) -> bool:
        """Determines if a topic is weak based on mastery score, accuracy, and confidence."""
        if record.attempts == 0:
            return False

        accuracy = record.correct_attempts / record.attempts if record.attempts > 0 else 0.0

        # Primary condition: mastery below threshold
        if record.mastery_score < self.weak_threshold:
            return True

        # Secondary condition: repeated mistakes despite borderline mastery
        if record.attempts >= 3 and accuracy < 0.50:
            return True

        # Low confidence with mediocre score
        if record.confidence < 0.40 and record.mastery_score < (self.weak_threshold + 0.05):
            return True

        return False

    def explain_weakness(self, record: LearnerMastery) -> str:
        """Returns a clear, human-readable reason why a topic is flagged as weak."""
        attempts = record.attempts
        correct = record.correct_attempts
        acc = (correct / attempts) if attempts > 0 else 0.0
        pct_mastery = int(round(record.mastery_score * 100))

        if attempts >= 3 and acc <= 0.40:
            return f"Repeated mistakes across multiple attempts (accuracy: {int(round(acc * 100))}%)"

        if record.mastery_score < 0.35:
            return f"Critically low topic mastery ({pct_mastery}%)"

        if attempts >= 2 and acc < 0.50:
            return f"Low accuracy across recent questions ({correct}/{attempts} correct)"

        if attempts == 1 and correct == 0:
            return "Struggled on initial assessment question"

        if record.confidence < 0.45:
            return "Low confidence and accuracy below proficiency threshold"

        threshold_pct = int(round(self.weak_threshold * 100))
        return f"Topic mastery ({pct_mastery}%) is below proficiency threshold ({threshold_pct}%)"

    def detect_weak_topics(self, records: List[LearnerMastery]) -> List[WeakTopicSummaryItem]:
        """Scans mastery records and returns all detected weak topics sorted by lowest mastery first."""
        weak_items: List[WeakTopicSummaryItem] = []
        for rec in records:
            if self.is_weak(rec):
                weak_items.append(
                    WeakTopicSummaryItem(
                        topic=rec.topic,
                        mastery_score=rec.mastery_score,
                        reason=self.explain_weakness(rec)
                    )
                )

        # Sort with lowest mastery score first (highest urgency)
        weak_items.sort(key=lambda x: x.mastery_score)
        return weak_items
