import sys
import os

# Ensure backend directory is in python path if run from ai-rag or root
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from app.services.query_intent import QueryIntentAnalyzer, query_intent_analyzer
    from app.schemas.intent import QueryIntentEnum, QueryIntentRequest, QueryIntentResponse
except ImportError:
    # Fallback to local import if backend is directly accessible
    from backend.app.services.query_intent import QueryIntentAnalyzer, query_intent_analyzer
    from backend.app.schemas.intent import QueryIntentEnum, QueryIntentRequest, QueryIntentResponse

__all__ = [
    "QueryIntentAnalyzer",
    "query_intent_analyzer",
    "QueryIntentEnum",
    "QueryIntentRequest",
    "QueryIntentResponse"
]
