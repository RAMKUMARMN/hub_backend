from app.ai.api.chat import sanitize_content

def test_sanitize_content():
    raw_leak = 'tags" before providing your final answer." So I will generate the thought block first. </think> Hi! Ready when you are'
    sanitized = sanitize_content(raw_leak)
    assert sanitized == "Hi! Ready when you are"

    raw_leak_2 = 'Some message </think>'
    assert sanitize_content(raw_leak_2) == "Some message"

    raw_leak_3 = '<think> hello </think> world'
    assert sanitize_content(raw_leak_3) == "hello  world"

    raw_leak_4 = 'Respond directly. Do not output any reasoning or step-by-step thinking, and do not use <think> tags. Actual answer'
    assert sanitize_content(raw_leak_4) == ""

if __name__ == "__main__":
    test_sanitize_content()
    print("All sanitize tests passed!")
