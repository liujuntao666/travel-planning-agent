from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.auth import get_current_user, get_owned_trip
from app.common.db import get_db
from app.common.pagination import PageParams, paginate
from app.common.rbac import require_permission
from app.export.service import FORMAT_LABEL, generate_export
from app.itinerary.service import (
    activate_version,
    add_item,
    compare_versions,
    delete_item,
    get_version,
    move_item,
    replace_hotel,
    replan,
    serialize_trip,
    update_item,
)
from app.models import TripExport, TripVersion, User
from app.schemas.requests import ExportIn, HotelReplaceIn, ItemAddIn, ItemUpdateIn, MoveIn

WRITE_PERMISSION = [Depends(require_permission("trip:write"))]

router = APIRouter(prefix="/trips", tags=["trips"], dependencies=[Depends(require_permission("trip:read"))])


@router.get("/{trip_id}")
def detail(
    trip_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    return serialize_trip(db, get_owned_trip(db, trip_id, current))


@router.get("/{trip_id}/versions")
def versions(
    trip_id: int,
    change_type: str | None = Query(None, max_length=32),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    trip = get_owned_trip(db, trip_id, current)
    stmt = select(TripVersion).where(
        TripVersion.trip_id == trip.id, TripVersion.deleted == 0
    )
    if change_type:
        stmt = stmt.where(TripVersion.change_type == change_type)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": TripVersion.id, "version_no": TripVersion.version_no,
                      "created_at": TripVersion.created_at},
        default_sort="version_no:desc",
    )
    page["items"] = [
        {
            "id": v.id,
            "version_no": v.version_no,
            "change_type": v.change_type,
            "change_summary": v.change_summary,
            "total_cost": float(v.total_cost) if v.total_cost is not None else None,
            "current_flag": v.current_flag,
            "valid_flag": v.valid_flag,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in page["items"]
    ]
    return page


@router.get("/{trip_id}/versions/compare")
def compare(
    trip_id: int,
    base: int = Query(..., ge=1),
    target: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    return compare_versions(db, get_owned_trip(db, trip_id, current), base, target)


@router.get("/{trip_id}/versions/{version_id}")
def version_detail(
    trip_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    trip = get_owned_trip(db, trip_id, current)
    return serialize_trip(db, trip, get_version(db, trip, version_id))


@router.post("/{trip_id}/versions/{version_id}/activate")
def activate(
    trip_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = activate_version(db, get_owned_trip(db, trip_id, current), version_id)
    db.commit()
    return result


@router.patch("/{trip_id}/items/{item_id}")
def patch_item(
    trip_id: int,
    item_id: int,
    payload: ItemUpdateIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = update_item(
        db, get_owned_trip(db, trip_id, current), item_id, payload.model_dump(exclude_none=True)
    )
    db.commit()
    return result


@router.delete("/{trip_id}/items/{item_id}", dependencies=WRITE_PERMISSION)
def remove_item(
    trip_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = delete_item(db, get_owned_trip(db, trip_id, current), item_id)
    db.commit()
    return result


@router.post("/{trip_id}/items/{item_id}/move", dependencies=WRITE_PERMISSION)
def move(
    trip_id: int,
    item_id: int,
    payload: MoveIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = move_item(db, get_owned_trip(db, trip_id, current), item_id, payload.direction)
    db.commit()
    return result


@router.post("/{trip_id}/items", dependencies=WRITE_PERMISSION)
def create_item(
    trip_id: int,
    payload: ItemAddIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = add_item(db, get_owned_trip(db, trip_id, current), payload.model_dump())
    db.commit()
    return result


@router.post("/{trip_id}/lodgings/{lodging_id}/replace", dependencies=WRITE_PERMISSION)
def replace(
    trip_id: int,
    lodging_id: int,
    payload: HotelReplaceIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = replace_hotel(
        db, get_owned_trip(db, trip_id, current), lodging_id, payload.hotel_id
    )
    db.commit()
    return result


@router.post("/{trip_id}/replan")
def ai_replan(
    trip_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    result = replan(db, get_owned_trip(db, trip_id, current))
    db.commit()
    return result


@router.post(
    "/{trip_id}/exports",
    dependencies=[Depends(require_permission("export:create"))],
)
def create_export(
    trip_id: int,
    payload: ExportIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    trip = get_owned_trip(db, trip_id, current)
    record = generate_export(db, trip, payload.format)
    db.commit()
    return {
        "id": record.id,
        "export_no": record.export_no,
        "format": record.format,
        "file_url": record.file_url,
        "file_size": record.file_size,
        "page_count": record.page_count,
        "degrade_notice_count": record.degrade_notice_count,
        "status": record.status,
        "fail_reason": record.fail_reason,
    }


@router.get("/{trip_id}/exports")
def exports(
    trip_id: int,
    format: str | None = Query(None, max_length=16),
    status: int | None = Query(None, ge=1, le=3),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    trip = get_owned_trip(db, trip_id, current)
    stmt = select(TripExport).where(TripExport.trip_id == trip.id, TripExport.deleted == 0)
    if format:
        stmt = stmt.where(TripExport.format == format)
    if status:
        stmt = stmt.where(TripExport.status == status)
    page = paginate(
        db, stmt, page_params,
        allowed_sort={"id": TripExport.id, "created_at": TripExport.created_at,
                      "file_size": TripExport.file_size},
        default_sort="id:desc",
    )
    page["items"] = [
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
        for r in page["items"]
    ]
    return page
