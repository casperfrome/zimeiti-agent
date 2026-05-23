from app.schemas import GenerateRequest, PolishRequest


def test_ai_requests_enable_web_search_by_default():
    assert GenerateRequest(description="写一条文案").enable_web_search is True
    assert PolishRequest().enable_web_search is True


def test_ai_requests_allow_disabling_web_search():
    assert GenerateRequest(description="写一条文案", enable_web_search=False).enable_web_search is False
    assert PolishRequest(enable_web_search=False).enable_web_search is False
