from app.agent_core.slots import REQUIRED_SLOTS, clarify_question, cn_to_int, extract_slots


def test_cn_to_int():
    assert cn_to_int("5") == 5
    assert cn_to_int("两") == 2
    assert cn_to_int("十") == 10
    assert cn_to_int("二十三") == 23
    assert cn_to_int("") is None


def test_extract_full_requirement():
    text = "我从成都出发，想去云南玩5天4晚，预算6000元，两个人，休闲一点，高铁优先，不要购物"
    slots = extract_slots(text)
    assert slots["ORIGIN"].value == "成都"
    assert slots["DEST"].value == "云南"
    assert slots["NIGHTS"].value == "5天4晚"
    assert slots["PEOPLE"].value == "2"
    assert slots["BUDGET"].value == "6000"
    assert slots["STYLE"].value == "RELAX"
    assert slots["TRANSPORT"].value == "高铁优先"
    assert "不购物" in slots["TABOO"].value
    for key in REQUIRED_SLOTS:
        assert key in slots


def test_extract_nights_from_days_only():
    slots = extract_slots("去大理玩三天")
    assert slots["NIGHTS"].value == "3天2晚"


def test_extract_dest_suffix_removed():
    slots = extract_slots("去丽江旅游")
    assert slots["DEST"].value == "丽江"


def test_clarify_question_covers_required_slots():
    for key in REQUIRED_SLOTS:
        assert clarify_question(key)
