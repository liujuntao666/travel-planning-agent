import re

INTENT_NEW = "NEW_PLAN"
INTENT_ADJUST = "ADJUST"
INTENT_CONSULT = "CONSULT"

ADJUST_WORDS = (
    "加一天", "多加", "多待", "减少", "少住", "改成", "换成", "替换", "不要", "别安排",
    "住得", "住近", "酒店换", "重排", "重新排", "调整", "删除", "去掉", "换成", "提前",
    "晚点", "往后", "往前", "加个", "增加", "改到", "换一家", "离景区",
)
CONSULT_WORDS = (
    "怎么", "如何", "有什么", "推荐", "注意", "攻略", "签证", "天气", "适合", "需要",
    "门票", "开放时间", "必吃", "习俗", "安全吗", "值得", "贵不贵", "预约", "带什么",
)
PLAN_WORDS = ("出发", "去", "行程", "规划", "玩", "自由行", "度假", "预算", "天", "晚")


def detect_intent(text: str, has_active_trip: bool) -> tuple[str, float]:
    """三类意图：新规划 / 调整 / 咨询（NFR-02）。"""
    if any(w in text for w in ADJUST_WORDS) and has_active_trip:
        return INTENT_ADJUST, 0.94
    if re.search(r"(加|减|改|换|删|调整|重排)", text) and has_active_trip:
        return INTENT_ADJUST, 0.88
    if text.strip().endswith(("?", "？")) and any(w in text for w in CONSULT_WORDS):
        return INTENT_CONSULT, 0.9
    if any(w in text for w in CONSULT_WORDS) and not any(w in text for w in ("出发", "预算", "行程")):
        return INTENT_CONSULT, 0.82
    if re.search(r"(?:从|由).{1,8}(?:出发|去)", text) or any(w in text for w in PLAN_WORDS):
        return INTENT_NEW, 0.9
    if has_active_trip:
        return INTENT_ADJUST, 0.65
    return INTENT_NEW, 0.6
