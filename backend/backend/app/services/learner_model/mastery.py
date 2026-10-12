import math
from typing import Optional, Tuple

# BKT Difficulty Parameters: (Guess, Slip, Transition)
DIFFICULTY_PARAMS = {
    "easy": {
        "p_guess": 0.25,
        "p_slip": 0.05,
        "p_transit": 0.10,
    },
    "medium": {
        "p_guess": 0.15,
        "p_slip": 0.10,
        "p_transit": 0.12,
    },
    "hard": {
        "p_guess": 0.08,
        "p_slip": 0.15,
        "p_transit": 0.15,
    },
}

INITIAL_MASTERY_CORRECT = {
    "easy": 0.55,
    "medium": 0.65,
    "hard": 0.75,
}

INITIAL_MASTERY_INCORRECT = {
    "easy": 0.15,
    "medium": 0.20,
    "hard": 0.25,
}

def update_mastery(
    previous_mastery: Optional[float],
    is_correct: bool,
    difficulty: str = "medium",
    total_attempts_prior: int = 0,
    correct_attempts_prior: int = 0,
) -> Tuple[float, float]:
    """
    Computes updated mastery score and confidence deterministically using a
    Bayesian Knowledge Tracing (BKT) inspired probabilistic update model.

    Args:
        previous_mastery: Prior mastery score [0.0, 1.0] or None for new topics.
        is_correct: Whether the question was answered correctly.
        difficulty: Question difficulty ('easy', 'medium', 'hard').
        total_attempts_prior: Number of prior attempts on this topic.
        correct_attempts_prior: Number of prior correct attempts on this topic.

    Returns:
        (updated_mastery, updated_confidence) - both floats in [0.0, 1.0], rounded to 2 decimals.
    """
    diff_key = difficulty.lower().strip() if difficulty else "medium"
    params = DIFFICULTY_PARAMS.get(diff_key, DIFFICULTY_PARAMS["medium"])
    p_guess = params["p_guess"]
    p_slip = params["p_slip"]
    p_transit = params["p_transit"]

    # 1. Determine updated mastery
    if previous_mastery is None:
        # First assessment observation
        if is_correct:
            raw_mastery = INITIAL_MASTERY_CORRECT.get(diff_key, 0.65)
        else:
            raw_mastery = INITIAL_MASTERY_INCORRECT.get(diff_key, 0.20)
    else:
        # Clamp prior to avoid edge singularities
        prior = max(0.01, min(0.99, float(previous_mastery)))

        if is_correct:
            numerator = prior * (1.0 - p_slip)
            denominator = numerator + (1.0 - prior) * p_guess
            posterior = numerator / denominator if denominator > 0 else prior
            raw_mastery = posterior + (1.0 - posterior) * p_transit
        else:
            numerator = prior * p_slip
            denominator = numerator + (1.0 - prior) * (1.0 - p_guess)
            posterior = numerator / denominator if denominator > 0 else prior
            # Minor reflection/learning rate upon failure
            raw_mastery = posterior + (1.0 - posterior) * (0.2 * p_transit)

    # 2. Determine confidence
    attempts_now = total_attempts_prior + 1
    correct_now = correct_attempts_prior + (1 if is_correct else 0)
    accuracy = correct_now / attempts_now

    # Volume of evidence curve (saturates near 1.0 as attempts grow)
    evidence_weight = 1.0 - math.exp(-0.35 * attempts_now)

    # Consistency factor: higher when evidence shows a clear trend
    consistency_factor = 0.85 + 0.15 * abs(2.0 * accuracy - 1.0)
    raw_confidence = evidence_weight * consistency_factor

    # Bound and round
    final_mastery = round(max(0.0, min(1.0, raw_mastery)), 2)
    final_confidence = round(max(0.10, min(1.0, raw_confidence)), 2)

    return final_mastery, final_confidence
