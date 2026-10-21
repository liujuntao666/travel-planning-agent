import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ContentAuditLog

# 演示用最小词表；生产环境替换为第三方内容安全服务
RISK_WORDS = {
    "涉政": ("颠覆", "暴恐"),
    "广告": ("加微信", "私聊下单", "代购"),
    "低俗": ("约炮", "裸聊"),
}


def audit_text(db: Session, text: str, biz_type: str, biz_id: int | None = None,
               conversation_id: int | None = None) -> tuple[bool, str | None]:
    """返回 (是否放行, 风险标签)，并写入审核留痕（NFR-09）。"""
    label = None
    for risk, words in RISK_WORDS.items():
        if any(w in text for w in words):
            label = risk
            break
    passed = label is None
    log = ContentAuditLog(
        biz_type=biz_type,
        biz_id=biz_id,
        conversation_id=conversation_id,
        content_digest=hashlib.sha256(text.encode("utf-8")).hexdigest()[:32],
        audit_result="PASS" if passed else "REJECT",
        risk_level="LOW" if passed else "HIGH",
        risk_label=label,
        auditor="MACHINE",
        handle_action="放行" if passed else "拦截",
        audited_at=datetime.now(),
    )
    db.add(log)
    return passed, label
