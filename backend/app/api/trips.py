from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.db import get_db
from app.export.service import generate_export, list_exports
from app.itinerary.service import (
    activate_version,
    add_item,
    compare_versions,
    delete_item,
    get_trip,
    get_version,
    list_versions,
    move_item,
    replace_hotel,
    replan,
    serialize_trip,
    update_item,
)
from app.schemas.requests import ExportIn, HotelReplaceIn, ItemAddIn, ItemUpdateIn, MoveIn

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("/{trip_id}")
def detail(trip_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize_trip(db, get_trip(db, trip_id))


@router.get("/{trip_id}/versions")
def versions(trip_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return list_versions(db, get_trip(db, trip_id))


@router.get("/{trip_id}/versions/compare")
def compare(trip_id: int, base: int = Query(...), target: int = Query(...),
            db: Session = Depends(get_db)) -> dict:
    return compare_versions(db, get_trip(db, trip_id), base, target)


@router.get("/{trip_id}/versions/{version_id}")
def version_detail(trip_id: int, version_id: int, db: Session = Depends(get_db)) -> dict:
    trip = get_trip(db, trip_id)
    return serialize_trip(db, trip, get_version(db, trip, version_id))


@router.post("/{trip_id}/versions/{version_id}/activate")
def activate(trip_id: int, version_id: int, db: Session = Depends(get_db)) -> dict:
    result = activate_version(db, get_trip(db, trip_id), version_id)
    db.commit()
    return result


@router.patch("/{trip_id}/items/{item_id}")
def patch_item(trip_id: int, item_id: int, payload: ItemUpdateIn,
               db: Session = Depends(get_db)) -> dict:
    result = update_item(db, get_trip(db, trip_id), item_id, payload.model_dump(exclude_none=True))
    db.commit()
    return result


@router.delete("/{trip_id}/items/{item_id}")
def remove_item(trip_id: int, item_id: int, db: Session = Depends(get_db)) -> dict:
    result = delete_item(db, get_trip(db, trip_id), item_id)
    db.commit()
    return result


@router.post("/{trip_id}/items/{item_id}/move")
def move(trip_id: int, item_id: int, payload: MoveIn, db: Session = Depends(get_db)) -> dict:
    result = move_item(db, get_trip(db, trip_id), item_id, payload.direction)
    db.commit()
    return result


@router.post("/{trip_id}/items")
def create_item(trip_id: int, payload: ItemAddIn, db: Session = Depends(get_db)) -> dict:
    result = add_item(db, get_trip(db, trip_id), payload.model_dump())
    db.commit()
    return result


@router.post("/{trip_id}/lodgings/{lodging_id}/replace")
def replace(trip_id: int, lodging_id: int, payload: HotelReplaceIn,
            db: Session = Depends(get_db)) -> dict:
    result = replace_hotel(db, get_trip(db, trip_id), lodging_id, payload.hotel_id)
    db.commit()
    return result


@router.post("/{trip_id}/replan")
def ai_replan(trip_id: int, db: Session = Depends(get_db)) -> dict:
    result = replan(db, get_trip(db, trip_id))
    db.commit()
    return result


@router.post("/{trip_id}/exports")
def create_export(trip_id: int, payload: ExportIn, db: Session = Depends(get_db)) -> dict:
    trip = get_trip(db, trip_id)
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
def exports(trip_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return list_exports(db, get_trip(db, trip_id))
