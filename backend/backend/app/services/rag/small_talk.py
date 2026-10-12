import re
from typing import Optional
from app.schemas.tutor import TutorChatResponse

GREETING_RESPONSE = (
    "Hi! I'm your LearnSphere AI course tutor. What would you like to learn today? "
    "Ask me about your course materials, and I'll help explain the concepts with relevant citations."
)

THANKS_RESPONSE = (
    "You're welcome! Would you like to explore another concept or practise with a quiz?"
)

FAREWELL_RESPONSE = (
    "Goodbye! Keep learning, and come back whenever you need help with your course materials."
)

# Canonical intent phrase dictionaries
GREETING_PHRASES = {
    "hi",
    "hello",
    "hey",
    "hi there",
    "hello there",
    "hey there",
    "hi tutor",
    "hello tutor",
    "hey tutor",
    "good morning",
    "good afternoon",
    "good evening",
    "good day",
    "how are you",
    "how are you doing",
    "how are you doing today",
    "hows it going",
    "how's it going",
    "how is it going",
    "greetings",
    "hi how are you",
    "hello how are you",
    "hey how are you",
}

THANKS_PHRASES = {
    "thanks",
    "thank you",
    "thank you so much",
    "thank you very much",
    "thanks a lot",
    "thanks so much",
    "thx",
    "many thanks",
}

FAREWELL_PHRASES = {
    "bye",
    "goodbye",
    "good bye",
    "bye bye",
    "see you",
    "see you later",
    "see ya",
    "have a good day",
    "have a nice day",
    "take care",
}

def normalize_text(text: str) -> str:
    """
    Normalize text by stripping surrounding whitespace, converting to lowercase,
    collapsing internal spaces, and stripping harmless surrounding punctuation.
    """
    if not text:
        return ""
    cleaned = text.strip().lower()
    # Collapse multiple whitespaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Strip harmless surrounding punctuation (leading or trailing punctuation like . , ! ? ; : - ~ ` ' ")
    cleaned = re.sub(r'^[^\w]+', '', cleaned)
    cleaned = re.sub(r'[^\w]+$', '', cleaned)
    return cleaned.strip()

def classify_small_talk(message: str) -> Optional[str]:
    """
    Classify whether a user message is purely small talk / conversational greeting / courtesy.
    Returns 'greeting', 'thanks', 'farewell', or None.
    
    Detection is kept strictly narrow to prevent intercepting academic questions.
    """
    norm = normalize_text(message)
    if not norm:
        return None

    if norm in GREETING_PHRASES:
        return "greeting"
    if norm in THANKS_PHRASES:
        return "thanks"
    if norm in FAREWELL_PHRASES:
        return "farewell"

    # Also check variant without internal apostrophes (e.g. "how's it going" -> "hows it going")
    norm_no_apos = norm.replace("'", "")
    if norm_no_apos in GREETING_PHRASES:
        return "greeting"
    if norm_no_apos in THANKS_PHRASES:
        return "thanks"
    if norm_no_apos in FAREWELL_PHRASES:
        return "farewell"

    return None

def get_small_talk_response(message: str) -> Optional[TutorChatResponse]:
    """
    Return a deterministic TutorChatResponse if message is small talk, else None.
    
    Preserves all grounding and security safeguards:
    - Zero LLM calls
    - Zero Qdrant retrieval calls
    - grounded = False (never marked as course grounded)
    - sources = [] (no fabricated citations)
    - response_type = 'conversational'
    """
    intent = classify_small_talk(message)
    if intent == "greeting":
        return TutorChatResponse(
            answer=GREETING_RESPONSE,
            grounded=False,
            sources=[],
            response_type="small_talk",
        )
    elif intent == "thanks":
        return TutorChatResponse(
            answer=THANKS_RESPONSE,
            grounded=False,
            sources=[],
            response_type="small_talk",
        )
    elif intent == "farewell":
        return TutorChatResponse(
            answer=FAREWELL_RESPONSE,
            grounded=False,
            sources=[],
            response_type="small_talk",
        )
    return None
