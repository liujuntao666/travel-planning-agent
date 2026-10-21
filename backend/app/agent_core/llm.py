import json

import httpx

from app.common.config import settings
from app.common.logging import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """你是旅游规划智能体。只输出 JSON，不要输出多余文字。
字段：intent（NEW_PLAN/ADJUST/CONSULT）、slots（ORIGIN/DEST/NIGHTS/PEOPLE/BUDGET/STYLE/TRANSPORT/TABOO）。
NIGHTS 用「5天4晚」格式；STYLE 取 RELAX/COUPLE/FAMILY/KIDS/HIKE/PHOTO/FOOD/COMMON；
TRANSPORT 取 飞机优先/高铁优先/火车优先/自驾/公交优先。未提及的槽位不要输出。"""


class LLMClient:
    """OpenAI 兼容协议客户端；未配置 LLM_API_KEY 时返回 None，走确定性规则引擎。"""

    def __init__(self) -> None:
        self.enabled = bool(settings.llm_api_key.strip())
        self._client = httpx.Client(
            base_url=settings.llm_base_url.rstrip("/"),
            timeout=settings.llm_timeout_s,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )

    def analyse(self, text: str, history: list[str] | None = None) -> dict | None:
        if not self.enabled:
            return None
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for item in (history or [])[-6:]:
            messages.append({"role": "user", "content": item})
        messages.append({"role": "user", "content": text})
        try:
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return data if isinstance(data, dict) else None
        except Exception as exc:  # 外部模型不可用时静默回退
            log.warning("LLM analyse failed: %s", exc)
            return None

    def compose_reply(self, facts: str) -> str | None:
        if not self.enabled:
            return None
        try:
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": "你是旅行规划助手，用简洁中文总结行程，不编造价格与班次。"},
                        {"role": "user", "content": facts},
                    ],
                    "temperature": 0.4,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log.warning("LLM compose failed: %s", exc)
            return None


llm_client = LLMClient()
