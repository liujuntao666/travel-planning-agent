import html
import math
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import settings
from app.common.errors import AppError
from app.common.logging import get_logger
from app.itinerary.service import current_version, serialize_trip
from app.models import Trip, TripExport

log = get_logger(__name__)

FORMAT_EXT = {"PDF": "pdf", "LONG_IMAGE": "png", "WECHAT_ARTICLE": "html"}
FORMAT_LABEL = {"PDF": "PDF 行程单", "LONG_IMAGE": "长图", "WECHAT_ARTICLE": "微信长文"}


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _degrade_count(plan: dict) -> int:
    count = len(plan.get("degrade_notes") or [])
    for day in plan.get("days", []):
        count += sum(1 for i in day.get("items", []) if i.get("degrade_flag"))
        if (day.get("lodging") or {}).get("degrade_flag"):
            count += 1
    for leg in plan.get("transports", []):
        if leg.get("degrade_flag"):
            count += 1
    return count


def render_wechat_html(plan: dict) -> str:
    trip = plan["trip"]
    budget = plan.get("budget") or {}
    parts = [
        '<section style="font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',sans-serif;'
        'max-width:680px;margin:0 auto;color:#2b2b2b;line-height:1.7;">',
        f'<h1 style="font-size:22px;margin:0 0 6px;">{_esc(trip["title"])}</h1>',
        f'<p style="color:#8a8f98;font-size:13px;margin:0 0 16px;">'
        f'{_esc(trip["origin_city"])} 出发 · {_esc(trip["dest_cities"])} · '
        f'{trip["day_count"]} 天 {trip["night_count"]} 晚 · {trip["people_count"]} 人 · {_esc(trip.get("style_name"))}</p>',
        f'<p style="background:#f6f8fa;border-radius:8px;padding:12px;font-size:14px;">'
        f'预算合计约 <b style="color:#e67700;">{budget.get("total", 0):.0f} 元</b>'
        f'（交通 {budget.get("transport", 0):.0f} / 住宿 {budget.get("lodging", 0):.0f} / '
        f'门票 {budget.get("tickets", 0):.0f} / 餐饮 {budget.get("meals", 0):.0f}）</p>',
    ]
    if plan.get("degrade_notes"):
        parts.append(
            '<p style="font-size:13px;color:#b26a00;background:#fff8e6;border-radius:8px;padding:10px;">'
            "以下信息待确认：" + "；".join(_esc(n) for n in plan["degrade_notes"]) + "</p>"
        )
    for day in plan.get("days", []):
        parts.append(f'<h2 style="font-size:17px;margin:22px 0 8px;border-left:4px solid #3b82f6;padding-left:8px;">'
                     f'Day {day["day_index"]} · {_esc(day.get("city"))} · {_esc(day.get("theme"))}</h2>')
        weather = day.get("weather")
        if weather:
            parts.append(f'<p style="font-size:13px;color:#6b7280;margin:0 0 8px;">'
                         f'{_esc(weather.get("weather_text"))} {weather.get("temp_min")}~{weather.get("temp_max")}℃'
                         f'　{_esc(weather.get("dressing_tip"))}</p>')
        for item in day.get("items", []):
            flag = "（信息待确认）" if item.get("degrade_flag") else ""
            parts.append(
                f'<p style="margin:6px 0;font-size:14px;">'
                f'<span style="color:#3b82f6;font-weight:600;">{_esc((item.get("start_time") or "")[:5])}</span> '
                f'{_esc(item.get("ref_name"))}{flag}'
                f'<span style="color:#8a8f98;font-size:13px;">　{_esc(item.get("note"))}</span></p>'
            )
        lodging = day.get("lodging")
        if lodging:
            flag = "（信息待确认）" if lodging.get("degrade_flag") else ""
            parts.append(f'<p style="font-size:13px;color:#6b7280;margin:8px 0 0;">'
                         f'住宿：{_esc(lodging.get("hotel_name"))}{flag} · {_esc(lodging.get("room_type"))} · '
                         f'{lodging.get("price_per_night", 0):.0f} 元/晚</p>')
    parts.append('<p style="font-size:12px;color:#9ca3af;margin-top:24px;">'
                 '本行程单由旅游规划智能体生成，价格与班次均来自实时工具返回，请出行前再次确认。</p>')
    parts.append("</section>")
    return "\n".join(parts)


def render_pdf(plan: dict, path: Path) -> int:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    title_style = ParagraphStyle("title", fontName="STSong-Light", fontSize=20, leading=28, spaceAfter=6)
    h2 = ParagraphStyle("h2", fontName="STSong-Light", fontSize=13, leading=20, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", fontName="STSong-Light", fontSize=9.5, leading=14)
    small = ParagraphStyle("small", fontName="STSong-Light", fontSize=8, leading=12, textColor=colors.grey)

    trip = plan["trip"]
    budget = plan.get("budget") or {}
    story = [
        Paragraph(_esc(trip["title"]), title_style),
        Paragraph(
            f'{_esc(trip["origin_city"])} 出发 · {_esc(trip["dest_cities"])} · '
            f'{trip["day_count"]} 天 {trip["night_count"]} 晚 · {trip["people_count"]} 人 · '
            f'{_esc(trip.get("style_name"))}', small),
        Spacer(1, 6),
        Paragraph(
            f'合计约 {budget.get("total", 0):.0f} 元（交通 {budget.get("transport", 0):.0f} / '
            f'住宿 {budget.get("lodging", 0):.0f} / 门票 {budget.get("tickets", 0):.0f} / '
            f'餐饮 {budget.get("meals", 0):.0f}）', body),
    ]
    if plan.get("degrade_notes"):
        story.append(Paragraph("待确认：" + "；".join(_esc(n) for n in plan["degrade_notes"]), small))

    for day in plan.get("days", []):
        story.append(Paragraph(
            f'Day {day["day_index"]} · {_esc(day.get("city"))} · {_esc(day.get("theme"))}', h2))
        if day.get("weather"):
            w = day["weather"]
            story.append(Paragraph(
                f'{_esc(w.get("weather_text"))} {w.get("temp_min")}~{w.get("temp_max")}℃ '
                f'{_esc(w.get("dressing_tip"))}', small))
        rows = [[Paragraph("时间", body), Paragraph("安排", body), Paragraph("说明", body)]]
        for item in day.get("items", []):
            flag = "（待确认）" if item.get("degrade_flag") else ""
            rows.append([
                Paragraph(_esc((item.get("start_time") or "")[:5]), body),
                Paragraph(_esc(item.get("ref_name")) + flag, body),
                Paragraph(_esc(item.get("note")), body),
            ])
        table = Table(rows, colWidths=[20 * mm, 55 * mm, 95 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8dee9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
        lodging = day.get("lodging")
        if lodging:
            story.append(Paragraph(
                f'住宿：{_esc(lodging.get("hotel_name"))} · {_esc(lodging.get("room_type"))} · '
                f'{lodging.get("price_per_night", 0):.0f} 元/晚', small))
        story.append(Spacer(1, 4))

    story.append(Paragraph(
        "本行程单由旅游规划智能体生成，价格、班次、房态均来自工具实时返回；标注「待确认」的信息请在出行前核实。", small))
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=trip["title"], author="Travel Planning Agent")
    doc.build(story)
    return max(1, math.ceil(sum(len(d.get("items", [])) for d in plan["days"]) / 28))


def _font_path() -> str | None:
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def render_long_image(plan: dict, path: Path) -> int:
    from PIL import Image, ImageDraw, ImageFont

    font_path = _font_path()
    if not font_path:
        raise AppError("EXPORT_FONT_MISSING", "缺少中文字体，无法生成长图", 500)
    width, margin = 1080, 60
    try:
        title_font = ImageFont.truetype(font_path, 46)
        head_font = ImageFont.truetype(font_path, 34)
        body_font = ImageFont.truetype(font_path, 26)
        small_font = ImageFont.truetype(font_path, 22)
    except OSError as exc:
        raise AppError("EXPORT_FONT_MISSING", f"字体加载失败：{exc}", 500) from exc

    trip = plan["trip"]
    budget = plan.get("budget") or {}
    lines: list[tuple[str, object, str]] = []
    lines.append((trip["title"], title_font, "#111827"))
    lines.append((f'{trip["origin_city"]} 出发 · {trip["dest_cities"]} · {trip["day_count"]} 天 '
                  f'{trip["night_count"]} 晚 · {trip["people_count"]} 人', small_font, "#6b7280"))
    lines.append((f'合计约 {budget.get("total", 0):.0f} 元', body_font, "#e67700"))
    for note in plan.get("degrade_notes") or []:
        lines.append((f"待确认：{note}", small_font, "#b26a00"))
    for day in plan.get("days", []):
        lines.append((f'Day {day["day_index"]} · {day.get("city")} · {day.get("theme")}', head_font, "#1d4ed8"))
        for item in day.get("items", []):
            flag = "（待确认）" if item.get("degrade_flag") else ""
            text = f'{(item.get("start_time") or "")[:5]}　{item.get("ref_name")}{flag}'
            lines.append((text, body_font, "#111827"))
            if item.get("note"):
                lines.append((f'　　{item.get("note")}', small_font, "#6b7280"))
        if day.get("lodging"):
            lod = day["lodging"]
            lines.append((f'住宿：{lod.get("hotel_name")} · {lod.get("room_type")} · '
                          f'{lod.get("price_per_night", 0):.0f} 元/晚', small_font, "#374151"))

    def wrap(text: str, font, max_width: int) -> list[str]:
        result, current = [], ""
        for ch in text:
            if font.getlength(current + ch) <= max_width:
                current += ch
            else:
                result.append(current)
                current = ch
        if current:
            result.append(current)
        return result or [""]

    rendered: list[tuple[str, object, str, int]] = []
    for text, font, color in lines:
        for segment in wrap(text, font, width - margin * 2):
            rendered.append((segment, font, color, int(font.size * 1.75)))
    height = margin * 2 + sum(line[3] for line in rendered)
    image = Image.new("RGB", (width, max(height, 600)), "#ffffff")
    draw = ImageDraw.Draw(image)
    y = margin
    for text, font, color, line_height in rendered:
        draw.text((margin, y), text, font=font, fill=color)
        y += line_height
    image.save(str(path), "PNG", optimize=True)
    return max(1, math.ceil(height / 1600))


def generate_export(db: Session, trip: Trip, fmt: str) -> TripExport:
    if fmt not in FORMAT_EXT:
        raise AppError("EXPORT_FORMAT", "仅支持 PDF / LONG_IMAGE / WECHAT_ARTICLE", 422)
    version = current_version(db, trip)
    plan = serialize_trip(db, trip, version)
    export_no = f"EXP{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:4].upper()}"
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    path = settings.export_dir / f"{export_no}.{FORMAT_EXT[fmt]}"
    record = TripExport(
        export_no=export_no,
        trip_id=trip.id,
        trip_version_id=version.id,
        format=fmt,
        degrade_notice_count=_degrade_count(plan),
        status=1,
    )
    db.add(record)
    db.flush()
    try:
        if fmt == "PDF":
            pages = render_pdf(plan, path)
        elif fmt == "LONG_IMAGE":
            pages = render_long_image(plan, path)
        else:
            path.write_text(
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{_esc(plan['trip']['title'])}</title></head><body style='background:#fff;padding:16px'>"
                + render_wechat_html(plan) + "</body></html>",
                encoding="utf-8",
            )
            pages = 1
        record.file_url = f"{settings.static_mount}/{path.name}"
        record.file_size = path.stat().st_size
        record.page_count = pages
        record.status = 2
        trip.status = max(trip.status or 2, 4)
    except Exception as exc:
        log.exception("export failed")
        record.status = 3
        record.fail_reason = str(exc)[:250]
    db.flush()
    return record


def list_exports(db: Session, trip: Trip) -> list[dict]:
    rows = db.scalars(
        select(TripExport).where(TripExport.trip_id == trip.id, TripExport.deleted == 0)
        .order_by(TripExport.id.desc())
    ).all()
    return [
        {
            "id": r.id,
            "export_no": r.export_no,
            "format": r.format,
            "format_label": FORMAT_LABEL.get(r.format, r.format),
            "file_url": r.file_url,
            "file_size": r.file_size,
            "page_count": r.page_count,
            "degrade_notice_count": r.degrade_notice_count,
            "status": r.status,
            "fail_reason": r.fail_reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
