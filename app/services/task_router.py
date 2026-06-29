def detect_task(message: str) -> str:
    text = message.lower()

    email_keywords = [
        "send email",
        "compose email",
        "draft email",
        "mail this",
    ]

    workflow_keywords = [
        "create todo",
        "add task",
        "schedule meeting",
        "calendar",
        "set reminder",
        "create reminder",
    ]

    if any(keyword in text for keyword in email_keywords):
        return "email"

    if any(keyword in text for keyword in workflow_keywords):
        return "workflow"

    return "chat"