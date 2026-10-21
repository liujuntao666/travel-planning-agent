import re
from dataclasses import dataclass

SLOT_KEYS = ("ORIGIN", "DEST", "NIGHTS", "PEOPLE", "BUDGET", "STYLE", "TRANSPORT", "TABOO")
REQUIRED_SLOTS = ("ORIGIN", "DEST", "NIGHTS")

CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
NUM_CHARS = "0-9零一二三四五六七八九十两"
NUM_RE = rf"[{NUM_CHARS}]+"

STYLE_KEYWORDS = (
    ("RELAX", ("休闲", "不累", "放松", "慢节奏", "躺平", "轻松")),
    ("COUPLE", ("情侣", "二人世界", "蜜月", "浪漫")),
    ("KIDS", ("亲子", "带娃", "带孩子", "小朋友")),
    ("FAMILY", ("家庭", "一家老小", "父母", "老人")),
    ("HIKE", ("徒步", "爬山", "户外", "登山")),
    ("PHOTO", ("摄影", "拍照", "出片", "机位", "日出", "日落")),
    ("FOOD", ("美食", "吃货", "小吃", "吃遍", "当地特色")),
)

TRANSPORT_KEYWORDS = (
    ("飞机优先", ("飞机", "航班", "坐飞机", "飞过去")),
    ("高铁优先", ("高铁", "动车", "坐高铁")),
    ("火车优先", ("火车", "卧铺", "硬座")),
    ("自驾", ("自驾", "开车", "租车")),
    ("公交优先", ("公交", "大巴", "客车")),
)

TABOO_KEYWORDS = (
    ("不吃辣", ("不吃辣", "忌辣", "不能吃辣", "不要辣")),
    ("清真", ("清真", "穆斯林")),
    ("素食", ("素食", "吃素")),
    ("恐高", ("恐高", "怕高")),
    ("不购物", ("不要购物", "不购物", "别安排购物", "拒绝购物", "不去购物店")),
)

DEST_SUFFIXES = ("旅游", "旅行", "自由行", "玩", "游玩", "度假", "转转", "逛逛")


@dataclass
class ExtractedSlot:
    key: str
    value: str
    value_type: str = "TEXT"
    confidence: float = 0.85
    source: str = "EXTRACT"


def cn_to_int(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CN_NUM.get(left, 1) if left else 1
        ones = CN_NUM.get(right, 0) if right else 0
        return tens * 10 + ones
    total = 0
    for ch in text:
        if ch in CN_NUM:
            total = total * 10 + CN_NUM[ch]
        else:
            return None
    return total


def _clean_city(raw: str) -> str:
    value = re.split(r"[\s，。,.!！?？、；;：:]", raw.strip())[0]
    for suffix in DEST_SUFFIXES:
        if value.endswith(suffix) and len(value) > len(suffix):
            value = value[: -len(suffix)]
    return value


def extract_slots(text: str) -> dict[str, ExtractedSlot]:
    """规则抽取八类需求要素；LLM 可用时由 llm.py 再做一次结构化补全。"""
    result: dict[str, ExtractedSlot] = {}

    m = re.search(r"(?:从|由)\s*([\u4e00-\u9fa5]{2,8}?)\s*(?:出发|启程|走|去|到)", text)
    if not m:
        m = re.search(r"出发地\s*[:：]?\s*([\u4e00-\u9fa5]{2,8})", text)
    if m:
        result["ORIGIN"] = ExtractedSlot("ORIGIN", _clean_city(m.group(1)), "TEXT", 0.96)

    m = re.search(r"(?:去|到|前往|想去|目的地\s*[:：]?)\s*([\u4e00-\u9fa5]{2,16})", text)
    if m:
        dest = _clean_city(m.group(1))
        if dest:
            result["DEST"] = ExtractedSlot("DEST", dest, "TEXT", 0.93)

    m = re.search(rf"({NUM_RE})\s*天\s*({NUM_RE})\s*晚", text)
    if m:
        days, nights = cn_to_int(m.group(1)), cn_to_int(m.group(2))
        if days and nights is not None:
            result["NIGHTS"] = ExtractedSlot("NIGHTS", f"{days}天{nights}晚", "TEXT", 0.98)
    else:
        m = re.search(rf"({NUM_RE})\s*(?:天|日游)", text)
        if m:
            days = cn_to_int(m.group(1))
            if days:
                result["NIGHTS"] = ExtractedSlot("NIGHTS", f"{days}天{days - 1}晚", "TEXT", 0.9)
        else:
            m = re.search(rf"({NUM_RE})\s*晚", text)
            if m:
                nights = cn_to_int(m.group(1))
                if nights:
                    result["NIGHTS"] = ExtractedSlot("NIGHTS", f"{nights + 1}天{nights}晚", "TEXT", 0.85)

    m = re.search(rf"({NUM_RE})\s*(?:个)?\s*人", text)
    people = cn_to_int(m.group(1)) if m else None
    if not people:
        if any(k in text for k in ("情侣", "二人世界", "两个人", "俩")):
            people = 2
        elif "一家三口" in text:
            people = 3
    if people:
        result["PEOPLE"] = ExtractedSlot("PEOPLE", str(people), "NUMBER", 0.95)

    m = re.search(r"(?:预算|总预算|花费)\s*(?:是|为|在|大概|约)?\s*(\d+(?:\.\d+)?)\s*(万)?", text)
    per_capita = "人均" in text
    if m:
        amount = float(m.group(1)) * (10000 if m.group(2) else 1)
        if per_capita and people:
            amount *= people
        result["BUDGET"] = ExtractedSlot("BUDGET", str(int(amount)), "NUMBER", 0.95)
    else:
        m = re.search(r"(\d{3,6})\s*(?:元|块|以内|左右)", text)
        if m:
            result["BUDGET"] = ExtractedSlot("BUDGET", m.group(1), "NUMBER", 0.75)

    for code, words in STYLE_KEYWORDS:
        if any(w in text for w in words):
            result["STYLE"] = ExtractedSlot("STYLE", code, "TEXT", 0.9)
            break

    for mode, words in TRANSPORT_KEYWORDS:
        if any(w in text for w in words):
            result["TRANSPORT"] = ExtractedSlot("TRANSPORT", mode, "TEXT", 0.9)
            break

    taboos = [name for name, words in TABOO_KEYWORDS if any(w in text for w in words)]
    if taboos:
        result["TABOO"] = ExtractedSlot("TABOO", ",".join(taboos), "LIST", 0.92)

    return result


def slot_label(key: str) -> str:
    return {
        "ORIGIN": "出发地",
        "DEST": "目的地",
        "NIGHTS": "天数",
        "PEOPLE": "出行人数",
        "BUDGET": "预算",
        "STYLE": "行程风格",
        "TRANSPORT": "出行方式",
        "TABOO": "禁忌与偏好",
    }.get(key, key)


def clarify_question(key: str) -> str:
    return {
        "ORIGIN": "请问你从哪个城市出发？",
        "DEST": "想去哪里玩？可以告诉我城市或省份，比如「云南」「大理 + 丽江」。",
        "NIGHTS": "计划玩几天？比如「5 天 4 晚」。",
    }.get(key, f"请补充{slot_label(key)}。")
