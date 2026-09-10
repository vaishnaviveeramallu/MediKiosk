from datetime import datetime
from pymongo import ReturnDocument
from app.database import get_database


async def generate_opd_token() -> str:
    """
    Generates an atomic, sequential daily OPD token number.
    Format: MK-YYYYMMDD-0001 (e.g., MK-20260910-0001)
    """
    db = get_database()
    today_str = datetime.now().strftime("%Y%m%d")
    counter_id = f"opd_token_{today_str}"

    result = await db["counters"].find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    seq_num = result["seq"]
    return f"MK-{today_str}-{seq_num:04d}"
