"""图形验证码：SVG 输出，答案存 Redis，一次性使用。"""
import base64
import random
import secrets

from app.common.config import settings
from app.common.redis_client import get_redis

CAPTCHA_PREFIX = "captcha:"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
COLORS = ["#0f766e", "#b45309", "#1d4ed8", "#9f1239", "#4d7c0f", "#6b21a8"]


def generate_captcha() -> dict:
    code = "".join(secrets.choice(ALPHABET) for _ in range(4))
    captcha_id = secrets.token_urlsafe(16)
    get_redis().set(f"{CAPTCHA_PREFIX}{captcha_id}", code.lower(), ex=settings.captcha_ttl_s)

    letters = []
    for index, char in enumerate(code):
        x = 16 + index * 24 + random.randint(-2, 2)
        y = 28 + random.randint(-3, 3)
        rotate = random.randint(-18, 18)
        color = random.choice(COLORS)
        letters.append(
            f'<text x="{x}" y="{y}" fill="{color}" font-size="24" font-weight="700" '
            f'font-family="Arial,Helvetica,sans-serif" '
            f'transform="rotate({rotate} {x} {y})">{char}</text>'
        )

    lines = []
    for _ in range(4):
        x1, y1 = random.randint(0, 120), random.randint(0, 40)
        x2, y2 = random.randint(0, 120), random.randint(0, 40)
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{random.choice(COLORS)}" stroke-width="1" opacity="0.5"/>'
        )

    dots = []
    for _ in range(24):
        dots.append(
            f'<circle cx="{random.randint(0, 120)}" cy="{random.randint(0, 40)}" r="1" '
            f'fill="{random.choice(COLORS)}" opacity="0.45"/>'
        )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" '
        'viewBox="0 0 120 40">'
        '<rect width="120" height="40" rx="8" fill="#f8fafc"/>'
        + "".join(lines)
        + "".join(dots)
        + "".join(letters)
        + "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    payload = {
        "captcha_id": captcha_id,
        "image": f"data:image/svg+xml;base64,{encoded}",
        "expires_in": settings.captcha_ttl_s,
    }
    if settings.captcha_debug:
        payload["debug_code"] = code
    return payload


def verify_captcha(captcha_id: str, code: str) -> bool:
    if not captcha_id or not code:
        return False
    client = get_redis()
    key = f"{CAPTCHA_PREFIX}{captcha_id}"
    expected = client.get(key)
    client.delete(key)
    return bool(expected) and secrets.compare_digest(expected, code.strip().lower())
