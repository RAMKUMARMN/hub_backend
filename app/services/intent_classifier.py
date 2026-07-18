import httpx
import json


async def classify_intent(message: str) -> str:
   
    prompt = f"""
    You are an intent classifier.

    Classify the message into ONE of:

    chat
    email
    document
    workflow
    search
    summarize

    Return ONLY valid JSON.

    Examples:

    Message: send my resume to hr@example.com
    Response:
    {{"intent":"email","confidence":95}}

    Message: summarize this document
    Response:
    {{"intent":"summarize","confidence":92}}

    Message: what is machine learning
    Response:
    {{"intent":"chat","confidence":98}}

    Message:
    {message}
    """

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(

                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen3",
                    "prompt": prompt,
                    "stream": False,
                },
            )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        raw = response.json()["response"].strip()
        
        print("RAW:", raw)

        try:
            result = json.loads(raw)
            return result
        except Exception:
            return {
                "intent": "chat",
                "confidence": 0
            }

    except Exception:
        return {
            "intent": "chat",
            "confidence": 0
        }
