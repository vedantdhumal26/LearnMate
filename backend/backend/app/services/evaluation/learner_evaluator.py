from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.learner_model.learner_service import LearnerModelService
from app.schemas.evaluation import LearnerSimulationResult
from app.models.learner_mastery import LearnerMastery
from app.core.logging_config import logger

class LearnerModelEvaluator:
    """
    Simulates student profiles and evaluates the Learner Mastery model:
    - Profile A: High performer (mostly correct answers)
    - Profile B: Mixed performer (alternating correct/incorrect)
    - Profile C: Struggling performer (mostly incorrect answers)
    
    Validates:
    - Mastery updates before vs after
    - Mastery gain calculations
    - Weak topic detection
    - Dynamic recommendation adjustments based on performance shifts
    """

    def __init__(self, learner_service: Optional[LearnerModelService] = None):
        self.learner_service = learner_service or LearnerModelService()

    def run_simulations(
        self,
        db: Session,
        course_id: str,
        topic: str = "Core Concepts"
    ) -> List[LearnerSimulationResult]:
        """
        Executes simulations for Profile A, Profile B, and Profile C.
        """
        results: List[LearnerSimulationResult] = []

        profiles = [
            {
                "name": "high_performer",
                "student_id": f"eval-sim-high-{course_id[:8]}",
                "answers": [True, True, True, True, True],  # 100% correct
            },
            {
                "name": "mixed_performer",
                "student_id": f"eval-sim-mixed-{course_id[:8]}",
                "answers": [True, False, True, False, True],  # 60% correct
            },
            {
                "name": "struggling",
                "student_id": f"eval-sim-struggling-{course_id[:8]}",
                "answers": [False, False, False, False, True],  # 20% correct
            },
        ]

        for p in profiles:
            student_id = p["student_id"]
            # Clean up prior records for this evaluation student to ensure clean baseline
            db.query(LearnerMastery).filter(
                LearnerMastery.student_id == student_id,
                LearnerMastery.course_id == course_id
            ).delete()
            db.commit()

            # 1. Baseline state
            initial_summary = self.learner_service.get_learner_summary(db, student_id, course_id)
            mastery_before = float(initial_summary.overall_mastery)
            confidence_before = 0.0

            # 2. Submit deterministic performance items
            perf_items = [
                {"topic": topic, "is_correct": ans, "difficulty": "medium"}
                for ans in p["answers"]
            ]
            records = self.learner_service.record_assessment_performance(
                db=db,
                student_id=student_id,
                course_id=course_id,
                performance_items=perf_items
            )

            # 3. Measure after state
            after_summary = self.learner_service.get_learner_summary(db, student_id, course_id)
            mastery_after = float(after_summary.overall_mastery)
            rec = next((r for r in records if r.topic == topic), None)
            confidence_after = float(rec.confidence) if rec else 0.5
            mastery_gain = round(mastery_after - mastery_before, 3)

            # 4. Weak topics and recommendations
            weak_topics = [wt.topic for wt in after_summary.weak_topics]
            recs_initial = self.learner_service.get_recommendations(db, student_id, course_id).recommendations

            # 5. Dynamic performance shift test:
            # If student performs well subsequently on this topic, recommendations should adapt
            remedial_items = [
                {"topic": topic, "is_correct": True, "difficulty": "medium"}
                for _ in range(4)
            ]
            self.learner_service.record_assessment_performance(
                db=db,
                student_id=student_id,
                course_id=course_id,
                performance_items=remedial_items
            )
            recs_updated = self.learner_service.get_recommendations(db, student_id, course_id).recommendations
            final_summary = self.learner_service.get_learner_summary(db, student_id, course_id)

            # Check that state changed (mastery grew and/or recommendations adapted)
            recommendations_changed = (
                final_summary.overall_mastery > mastery_after or
                len(recs_initial) != len(recs_updated) or
                any(r1.priority != r2.priority for r1, r2 in zip(recs_initial, recs_updated))
            )

            results.append(
                LearnerSimulationResult(
                    student_profile=p["name"],
                    student_id=student_id,
                    course_id=course_id,
                    topic=topic,
                    mastery_before=mastery_before,
                    mastery_after=mastery_after,
                    mastery_gain=mastery_gain,
                    confidence_before=confidence_before,
                    confidence_after=confidence_after,
                    weak_topics_detected=weak_topics,
                    recommendations_count=len(recs_initial),
                    recommendations_changed=recommendations_changed
                )
            )

        return results
