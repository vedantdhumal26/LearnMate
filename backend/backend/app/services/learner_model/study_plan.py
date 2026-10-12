from typing import List, Dict, Any, Optional
from app.models.learner_mastery import LearnerMastery
from app.schemas.learner import (
    StudyPlanItem,
    StudyPlanResponse,
    WeakTopicSummaryItem,
    RecommendationItem,
)
from app.services.learner_model.weak_topics import WeakTopicDetector
from app.services.learner_model.recommendations import RecommendationEngine
from app.core.config import settings

class StudyPlanEngine:
    """
    Deterministic StudyPlanEngine.
    Uses existing learner mastery records, weak topic indicators, recommendations,
    and course materials to generate an actionable 7-day personalized study plan.
    Requires NO LLM calls.
    """

    def __init__(
        self,
        weak_detector: Optional[WeakTopicDetector] = None,
        recommendation_engine: Optional[RecommendationEngine] = None,
        weak_threshold: Optional[float] = None,
        strong_threshold: Optional[float] = None,
        critical_weak_threshold: float = 0.40,
    ):
        self.weak_detector = weak_detector or WeakTopicDetector(
            weak_threshold=weak_threshold,
            strong_threshold=strong_threshold,
        )
        self.recommendation_engine = recommendation_engine or RecommendationEngine(
            weak_detector=self.weak_detector,
            weak_threshold=weak_threshold,
            strong_threshold=strong_threshold,
        )
        self.weak_threshold = (
            weak_threshold if weak_threshold is not None else settings.MASTERY_WEAK_THRESHOLD
        )
        self.strong_threshold = (
            strong_threshold if strong_threshold is not None else settings.MASTERY_STRONG_THRESHOLD
        )
        self.critical_weak_threshold = critical_weak_threshold

    def generate_study_plan(
        self,
        student_id: str,
        course_id: str,
        records: List[LearnerMastery],
        weak_topics: Optional[List[WeakTopicSummaryItem]] = None,
        recommendations: Optional[List[RecommendationItem]] = None,
        available_topics: Optional[List[str]] = None,
        plan_duration_days: int = 7,
    ) -> StudyPlanResponse:
        """
        Produces a structured, deterministic 7-day study plan.
        If the student has no prior mastery records, returns a diagnostic baseline plan.
        """
        if not records:
            return self._generate_new_learner_plan(
                student_id=student_id,
                course_id=course_id,
                available_topics=available_topics,
                plan_duration_days=plan_duration_days,
            )

        return self._generate_personalized_plan(
            student_id=student_id,
            course_id=course_id,
            records=records,
            weak_topics=weak_topics,
            recommendations=recommendations,
            plan_duration_days=plan_duration_days,
        )

    def _generate_new_learner_plan(
        self,
        student_id: str,
        course_id: str,
        available_topics: Optional[List[str]] = None,
        plan_duration_days: int = 7,
    ) -> StudyPlanResponse:
        """
        Generates a baseline diagnostic study plan for a new learner with no mastery data.
        Does NOT fabricate mastery scores.
        """
        topics = [t for t in (available_topics or []) if t and t.strip()]
        if not topics:
            topics = ["Course Foundations"]

        # Defined diverse schedule for new learners ensuring consecutive actions alternate
        template_schedule = [
            {
                "action": "diagnostic",
                "priority": "high",
                "difficulty": "medium",
                "question_count": 5,
                "reason": "Initial diagnostic assessment to establish baseline mastery",
            },
            {
                "action": "review_material",
                "priority": "high",
                "difficulty": "easy",
                "question_count": 5,
                "reason": "Review foundational course materials",
            },
            {
                "action": "practice",
                "priority": "medium",
                "difficulty": "easy",
                "question_count": 5,
                "reason": "Introductory baseline practice session",
            },
            {
                "action": "tutor_review",
                "priority": "medium",
                "difficulty": "medium",
                "question_count": 5,
                "reason": "Interactive tutor consultation on core concepts",
            },
            {
                "action": "diagnostic",
                "priority": "medium",
                "difficulty": "medium",
                "question_count": 5,
                "reason": "Mid-plan diagnostic checkpoint to gauge initial progress",
            },
            {
                "action": "review_material",
                "priority": "medium",
                "difficulty": "medium",
                "question_count": 5,
                "reason": "Reinforce conceptual understanding through material review",
            },
            {
                "action": "practice",
                "priority": "medium",
                "difficulty": "medium",
                "question_count": 5,
                "reason": "Comprehensive practice session to solidify basics",
            },
        ]

        plan_items: List[StudyPlanItem] = []
        num_topics = len(topics)

        for d in range(1, plan_duration_days + 1):
            sched = template_schedule[(d - 1) % len(template_schedule)]
            topic = topics[(d - 1) % num_topics]

            plan_items.append(
                StudyPlanItem(
                    day=d,
                    topic=topic,
                    priority=sched["priority"],
                    action=sched["action"],
                    difficulty=sched["difficulty"],
                    question_count=sched["question_count"],
                    reason=sched["reason"],
                )
            )

        return StudyPlanResponse(
            student_id=student_id,
            course_id=course_id,
            plan_duration_days=plan_duration_days,
            plan=plan_items,
        )

    def _generate_personalized_plan(
        self,
        student_id: str,
        course_id: str,
        records: List[LearnerMastery],
        weak_topics: Optional[List[WeakTopicSummaryItem]] = None,
        recommendations: Optional[List[RecommendationItem]] = None,
        plan_duration_days: int = 7,
    ) -> StudyPlanResponse:
        """
        Generates a personalized study plan grounded strictly in real learner mastery records.
        Weakest topic appears first.
        Actions alternate every day to maintain engagement and diversity.
        """
        # Sort records by mastery score ascending (weakest first), then confidence ascending
        sorted_records = sorted(records, key=lambda r: (r.mastery_score, r.confidence))
        num_records = len(sorted_records)

        # Distribute topics across the days
        # Days 1..min(num_records, 7) receive topics in ascending order of mastery
        # Subsequent days revisit earlier (weaker) topics for reinforcement
        daily_records: List[LearnerMastery] = []
        for d in range(plan_duration_days):
            if d < num_records:
                daily_records.append(sorted_records[d])
            else:
                # Cycle prioritizing weaker topics
                daily_records.append(sorted_records[d % num_records])

        plan_items: List[StudyPlanItem] = []
        topic_action_history: Dict[str, List[str]] = {}

        for d in range(1, plan_duration_days + 1):
            rec = daily_records[d - 1]
            prev_action = plan_items[-1].action if plan_items else None
            is_lowest = rec.topic == sorted_records[0].topic

            action, difficulty, priority, question_count, reason = self._select_day_parameters(
                day=d,
                record=rec,
                is_lowest=is_lowest,
                prev_action=prev_action,
                topic_history=topic_action_history.get(rec.topic, []),
            )

            if rec.topic not in topic_action_history:
                topic_action_history[rec.topic] = []
            topic_action_history[rec.topic].append(action)

            plan_items.append(
                StudyPlanItem(
                    day=d,
                    topic=rec.topic,
                    priority=priority,
                    action=action,
                    difficulty=difficulty,
                    question_count=question_count,
                    reason=reason,
                )
            )

        return StudyPlanResponse(
            student_id=student_id,
            course_id=course_id,
            plan_duration_days=plan_duration_days,
            plan=plan_items,
        )

    def _select_day_parameters(
        self,
        day: int,
        record: LearnerMastery,
        is_lowest: bool,
        prev_action: Optional[str],
        topic_history: List[str],
    ) -> tuple[str, str, str, int, str]:
        """
        Determines (action, difficulty, priority, question_count, reason) based on
        deterministic mastery rules and alternating action constraints.
        """
        score = record.mastery_score

        # 1. Determine Mastery Band Rules
        if score < self.critical_weak_threshold:
            # mastery < 0.40: priority high, easy practice, 5 questions
            priority = "high"
            difficulty = "easy"
            question_count = 5
            candidate_actions = ["practice", "tutor_review", "review_material"]
        elif score < self.weak_threshold:
            # 0.40 <= mastery < 0.60: priority high/medium, easy or medium practice, 5 questions
            priority = "high" if score < 0.50 else "medium"
            difficulty = "easy" if score < 0.50 else "medium"
            question_count = 5
            candidate_actions = ["practice", "tutor_review", "review_material"]
        elif score < self.strong_threshold:
            # 0.60 <= mastery < 0.75: priority medium, reinforcement, medium questions
            priority = "medium"
            difficulty = "medium"
            question_count = 5
            candidate_actions = ["tutor_review", "practice", "review_material"]
        else:
            # mastery >= 0.75: priority low, challenge, hard questions
            priority = "low"
            difficulty = "hard"
            question_count = 5
            candidate_actions = ["challenge", "tutor_review", "practice"]

        # 2. Select Action ensuring alternation (never repeat the exact same action every day)
        if day == 1:
            if score < self.weak_threshold:
                action = "practice"
            elif score < self.strong_threshold:
                action = "tutor_review"
            else:
                action = "challenge"
        else:
            # Filter out previous day's action
            valid = [a for a in candidate_actions if a != prev_action]
            # Prefer actions not yet taken for this topic to maximize topic diversity
            unused_for_topic = [a for a in valid if a not in topic_history]
            if unused_for_topic:
                action = unused_for_topic[0]
            else:
                action = valid[0]

        # 3. Determine Explainable Reason
        if day == 1 and is_lowest and score < self.weak_threshold:
            reason = "Lowest current mastery"
        elif action == "practice":
            if score < self.critical_weak_threshold:
                reason = "Lowest current mastery" if (is_lowest and "practice" not in topic_history) else "Targeted practice to address critical knowledge gaps"
            elif score < self.weak_threshold:
                reason = "Practice recommended to achieve proficiency"
            elif score < self.strong_threshold:
                reason = "Moderate mastery - practice recommended to achieve proficiency"
            else:
                reason = "Advanced mastery practice to maintain retention"
        elif action == "tutor_review":
            if score < self.weak_threshold:
                reason = "Interactive tutor review to address foundational gaps"
            elif score < self.strong_threshold:
                reason = "Reinforcement recommended"
            else:
                reason = "In-depth tutor discussion on advanced problem solving"
        elif action == "review_material":
            if score < self.weak_threshold:
                reason = "Review core material to build fundamental understanding"
            elif score < self.strong_threshold:
                reason = "Review advanced concepts for topic reinforcement"
            else:
                reason = "Review challenging source material for comprehensive mastery"
        elif action == "challenge":
            reason = "High proficiency achieved - test with advanced questions"
        else:
            reason = "Scheduled study activity"

        return action, difficulty, priority, question_count, reason
