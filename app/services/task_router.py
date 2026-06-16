def detect_task(message: str) -> str:
    text = message.lower()

    if any(word in text for word in ["email", "mail", "send"]):
        return "email"

    if any(word in text for word in ["resume", "cv", "document", "doc"]):
        return "document"

    return "chat"
