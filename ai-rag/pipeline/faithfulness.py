import os
import sys

# Ensure backend directory is in path for standalone AI scripts
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.faithfulness_evaluator import (
    FaithfulnessEvaluator,
    faithfulness_evaluator,
    compute_faithfulness_score,
)
from app.schemas.faithfulness import (
    ClaimVerificationRequest,
    ClaimVerificationResult,
    AnswerFaithfulnessRequest,
    AnswerFaithfulnessReport,
)

__all__ = [
    "FaithfulnessEvaluator",
    "faithfulness_evaluator",
    "compute_faithfulness_score",
    "ClaimVerificationRequest",
    "ClaimVerificationResult",
    "AnswerFaithfulnessRequest",
    "AnswerFaithfulnessReport",
]
