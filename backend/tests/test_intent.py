from app.agent_core.intent import INTENT_ADJUST, INTENT_CONSULT, INTENT_NEW, detect_intent


def test_new_plan_intent():
    intent, confidence = detect_intent("我从成都出发，想去云南玩5天4晚", False)
    assert intent == INTENT_NEW
    assert 0 < confidence <= 1


def test_adjust_intent_requires_active_trip():
    assert detect_intent("加一天", True)[0] == INTENT_ADJUST
    assert detect_intent("把酒店换一家", True)[0] == INTENT_ADJUST
    # 没有行程时不判定为调整
    assert detect_intent("加一天", False)[0] != INTENT_ADJUST


def test_consult_intent():
    assert detect_intent("玉龙雪山需要预约吗？", False)[0] == INTENT_CONSULT
    assert detect_intent("大理有什么必吃的美食？", True)[0] == INTENT_CONSULT
