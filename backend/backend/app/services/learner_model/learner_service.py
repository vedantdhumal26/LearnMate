from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.learner_mastery import LearnerMastery
from app.models.course import Course
from app.schemas.learner import (
    TopicMasteryItem,
    TopicMasteryResponse,
    StrongTopicSummaryItem,
    WeakTopicSummaryItem,
    RecentTopicSummaryItem,
    LearnerSummaryResponse,
    RecommendationItem,
    LearnerRecommendationsResponse,
    StudyPlanItem,
    StudyPlanResponse,
)
from app.services.learner_model.mastery import update_mastery
from app.services.learner_model.weak_topics import WeakTopicDetector
from app.services.learner_model.recommendations import RecommendationEngine
from app.services.learner_model.study_plan import StudyPlanEngine
from app.core.config import settings
from app.core.logging_config import logger

class LearnerModelService:
    def __init__(self):
        self.weak_detector = WeakTopicDetector()
        self.recommendation_engine = RecommendationEngine(weak_detector=self.weak_detector)
        self.study_plan_engine = StudyPlanEngine(
            weak_detector=self.weak_detector,
            recommendation_engine=self.recommendation_engine,
        )

    def record_assessment_performance(
        self,
        db: Session,
        student_id: str,
        course_id: str,
        performance_items: List[Dict[str, Any]]
    ) -> List[LearnerMastery]:
        """
        Updates student mastery records for each evaluated question in an assessment.

        Args:
            db: Database session.
            student_id: Unique identifier for the learner.
            course_id: Associated course identifier.
            performance_items: List of dicts, each with keys:
                - 'topic': str
                - 'is_correct': bool
                - 'difficulty': str ('easy', 'medium', 'hard')

        Returns:
            List of updated or newly created LearnerMastery records.
        """
        # Map to track in-session records per topic to prevent duplicates
        topic_records: Dict[str, LearnerMastery] = {}

        for item in performance_items:
            raw_topic = item.get("topic")
            topic = raw_topic.strip() if raw_topic and raw_topic.strip() else "General"
            is_correct = bool(item.get("is_correct", False))
            difficulty = item.get("difficulty", "medium")

            now = datetime.now(timezone.utc)

            # Retrieve from in-flight cache or database
            if topic in topic_records:
                record = topic_records[topic]
                new_mastery, new_conf = update_mastery(
                    previous_mastery=record.mastery_score,
                    is_correct=is_correct,
                    difficulty=difficulty,
                    total_attempts_prior=record.attempts,
                    correct_attempts_prior=record.correct_attempts,
                )
                record.mastery_score = new_mastery
                record.confidence = new_conf
                record.attempts += 1
                if is_correct:
                    record.correct_attempts += 1
                record.last_interaction = now
                record.updated_at = now
            else:
                existing = (
                    db.query(LearnerMastery)
                    .filter(
                        LearnerMastery.student_id == student_id,
                        LearnerMastery.course_id == course_id,
                        LearnerMastery.topic == topic,
                    )
                    .first()
                )
                if existing:
                    new_mastery, new_conf = update_mastery(
                        previous_mastery=existing.mastery_score,
                        is_correct=is_correct,
                        difficulty=difficulty,
                        total_attempts_prior=existing.attempts,
                        correct_attempts_prior=existing.correct_attempts,
                    )
                    existing.mastery_score = new_mastery
                    existing.confidence = new_conf
                    existing.attempts += 1
                    if is_correct:
                        existing.correct_attempts += 1
                    existing.last_interaction = now
                    existing.updated_at = now
                    topic_records[topic] = existing
                else:
                    new_mastery, new_conf = update_mastery(
                        previous_mastery=None,
                        is_correct=is_correct,
                        difficulty=difficulty,
                        total_attempts_prior=0,
                        correct_attempts_prior=0,
                    )
                    new_record = LearnerMastery(
                        student_id=student_id,
                        course_id=course_id,
                        topic=topic,
                        mastery_score=new_mastery,
                        confidence=new_conf,
                        attempts=1,
                        correct_attempts=1 if is_correct else 0,
                        last_interaction=now,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(new_record)
                    topic_records[topic] = new_record

        updated_records = list(topic_records.values())

        try:
            db.commit()
            for r in updated_records:
                db.refresh(r)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist learner mastery updates: {e}", exc_info=True)
            raise

        return updated_records

    def get_topic_mastery(
        self,
        db: Session,
        student_id: str,
        course_id: str
    ) -> TopicMasteryResponse:
        """Retrieves topic-by-topic mastery for a given student and course."""
        records = (
            db.query(LearnerMastery)
            .filter(
                LearnerMastery.student_id == student_id,
                LearnerMastery.course_id == course_id,
            )
            .order_by(LearnerMastery.topic.asc())
            .all()
        )

        topic_items = [
            TopicMasteryItem(
                topic=r.topic,
                mastery_score=r.mastery_score,
                confidence=r.confidence,
                attempts=r.attempts,
                correct_attempts=r.correct_attempts,
                last_interaction=r.last_interaction,
            )
            for r in records
        ]

        return TopicMasteryResponse(
            student_id=student_id,
            course_id=course_id,
            topics=topic_items,
        )

    def get_learner_summary(
        self,
        db: Session,
        student_id: str,
        course_id: str
    ) -> LearnerSummaryResponse:
        """Computes aggregate mastery stats, weak topics, strong topics, and recent activity."""
        records = (
            db.query(LearnerMastery)
            .filter(
                LearnerMastery.student_id == student_id,
                LearnerMastery.course_id == course_id,
            )
            .all()
        )

        if not records:
            return LearnerSummaryResponse(
                overall_mastery=0.0,
                strong_topics=[],
                weak_topics=[],
                recent_topics=[],
                status="new_learner",
            )

        overall = round(sum(r.mastery_score for r in records) / len(records), 2)

        # Strong topics: mastery >= strong threshold
        strong_items = [
            StrongTopicSummaryItem(topic=r.topic, mastery_score=r.mastery_score)
            for r in sorted(records, key=lambda x: x.mastery_score, reverse=True)
            if r.mastery_score >= settings.MASTERY_STRONG_THRESHOLD
        ]

        # Weak topics: detected via WeakTopicDetector
        weak_items = self.weak_detector.detect_weak_topics(records)

        # Recent topics: sorted by last_interaction descending
        recent_records = sorted(records, key=lambda x: x.last_interaction, reverse=True)
        recent_items = [
            RecentTopicSummaryItem(
                topic=r.topic,
                mastery_score=r.mastery_score,
                last_interaction=r.last_interaction,
            )
            for r in recent_records
        ]

        return LearnerSummaryResponse(
            overall_mastery=overall,
            strong_topics=strong_items,
            weak_topics=weak_items,
            recent_topics=recent_items,
            status="active",
        )

    def get_recommendations(
        self,
        db: Session,
        student_id: str,
        course_id: str
    ) -> LearnerRecommendationsResponse:
        """Returns personalized recommendations based on actual student mastery state."""
        records = (
            db.query(LearnerMastery)
            .filter(
                LearnerMastery.student_id == student_id,
                LearnerMastery.course_id == course_id,
            )
            .all()
        )

        recommendations = self.recommendation_engine.generate_recommendations(records)
        return LearnerRecommendationsResponse(recommendations=recommendations)

    def record_tutor_interaction(
        self,
        db: Session,
        student_id: str,
        course_id: str,
        topic: str,
        interaction_evidence: Optional[Dict[str, Any]] = None
    ) -> Optional[LearnerMastery]:
        """
        Extensible interface for Phase 4+ tutor-driven mastery signals.
        Tutor chat interactions only count toward mastery if sufficient evidence of learning
        is verified (e.g. successful concept check / comprehension question).
        """
        if not interaction_evidence or not interaction_evidence.get("verified_comprehension"):
            logger.info(
                f"Tutor interaction for student '{student_id}' on topic '{topic}' "
                "not factored into mastery: insufficient performance evidence."
            )
            return None

        # When evidence is present in future extensions, perform deterministic update:
        return None

    def get_available_course_topics(self, db: Session, course_id: str) -> List[str]:
        """
        Discovers existing course topics from questions, source material metadata,
        and course information.
        """
        import re
        from app.models.assessment import Question
        from app.models.source import Source

        topics: List[str] = []

        # 1. Topics from questions
        questions = (
            db.query(Question.topic_id)
            .filter(Question.course_id == course_id, Question.topic_id.isnot(None))
            .distinct()
            .all()
        )
        for q in questions:
            t = q[0]
            if t and t.strip() and t.strip() not in topics:
                topics.append(t.strip())

        # 2. Topics from uploaded sources
        if not topics:
            sources = db.query(Source).filter(Source.course_id == course_id).all()
            for s in sources:
                name = s.title or s.file_name
                if name:
                    cleaned = re.sub(r"\.[a-zA-Z0-9]+$", "", name).strip()
                    if cleaned and cleaned not in topics:
                        topics.append(cleaned)

        # 3. Course title fallback
        if not topics:
            course = db.query(Course).filter(Course.id == course_id).first()
            if course and course.title and course.title.strip():
                topics.append(course.title.strip())

        return topics

    def get_study_plan(
        self,
        db: Session,
        student_id: str,
        course_id: str,
        plan_duration_days: int = 7
    ) -> StudyPlanResponse:
        """
        Generates a deterministic 7-day personalized study plan grounded in actual learner mastery.
        """
        records = (
            db.query(LearnerMastery)
            .filter(
                LearnerMastery.student_id == student_id,
                LearnerMastery.course_id == course_id,
            )
            .all()
        )

        weak_topics = self.weak_detector.detect_weak_topics(records)
        recommendations = self.recommendation_engine.generate_recommendations(records)
        available_topics = self.get_available_course_topics(db, course_id)

        return self.study_plan_engine.generate_study_plan(
            student_id=student_id,
            course_id=course_id,
            records=records,
            weak_topics=weak_topics,
            recommendations=recommendations,
            available_topics=available_topics,
            plan_duration_days=plan_duration_days,
        )

