import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List, Any
from boto3.dynamodb.conditions import Key, Attr
from app.config import get_settings, get_dynamodb


def _to_decimal(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def _from_decimal(item: dict) -> dict:
    if not item:
        return item
    result = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        else:
            result[k] = v
    return result


def _table():
    return get_dynamodb().Table(get_settings().DYNAMODB_TABLE)


# ── User operations ──

def create_user(user_id: str, email: str, name: str, password_hash: str, role: str = "user"):
    _table().put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "email": email,
        "name": name,
        "passwordHash": password_hash,
        "role": role,
        "createdAt": datetime.now(timezone.utc).isoformat()
    })


def get_user_by_email(email: str):
    resp = _table().scan(
        FilterExpression=Attr("email").eq(email) & Attr("SK").eq("PROFILE")
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_user_by_id(user_id: str):
    resp = _table().get_item(Key={"PK": f"USER#{user_id}", "SK": "PROFILE"})
    return resp.get("Item")


def get_all_users() -> List[dict]:
    resp = _table().scan(
        FilterExpression=Attr("SK").eq("PROFILE")
    )
    return [_from_decimal(i) for i in resp.get("Items", [])]


def update_user_role(user_id: str, role: str):
    _table().update_item(
        Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
        UpdateExpression="SET #r = :r",
        ExpressionAttributeNames={"#r": "role"},
        ExpressionAttributeValues={":r": role},
    )


# ── Medication operations ──

def create_medication(user_id: str, name: str, dosage: str):
    med_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"MED#{med_id}",
        "medicationId": med_id,
        "name": name,
        "dosage": dosage,
        "createdAt": now
    }
    _table().put_item(Item=item)
    return item


def get_medications(user_id: str) -> List[dict]:
    pk = f"USER#{user_id}"
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("MED#"),
        ScanIndexForward=False
    )
    return resp.get("Items", [])


def get_medication(user_id: str, med_id: str):
    resp = _table().get_item(Key={"PK": f"USER#{user_id}", "SK": f"MED#{med_id}"})
    return resp.get("Item")


def delete_medication(user_id: str, med_id: str):
    _table().delete_item(Key={"PK": f"USER#{user_id}", "SK": f"MED#{med_id}"})


# ── Entry operations ──

def create_entry(user_id: str, entry_type: str, value: float, unit: str,
                 notes: Optional[str] = None, timestamp: Optional[str] = None,
                 medicationId: Optional[str] = None, medicationName: Optional[str] = None):
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    ts = timestamp or now
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"ENTRY#{ts}",
        "entryId": entry_id,
        "type": entry_type,
        "value": _to_decimal(value),
        "unit": unit,
        "notes": notes,
        "medicationId": medicationId,
        "medicationName": medicationName,
        "timestamp": ts,
        "createdAt": now
    }
    _table().put_item(Item=item)

    if entry_type == "glucose" and (value < 70 or value > 180):
        alert_item = {
            "PK": f"USER#{user_id}",
            "SK": f"ALERT#{ts}",
            "alertId": str(uuid.uuid4()),
            "type": "glucose_alert",
            "value": _to_decimal(value),
            "unit": unit,
            "level": "low" if value < 70 else "high",
            "timestamp": ts,
            "createdAt": now,
            "acknowledged": False
        }
        _table().put_item(Item=alert_item)

    return item


def get_entries(user_id: str, entry_type: Optional[str] = None,
                from_date: Optional[str] = None, to_date: Optional[str] = None,
                limit: int = 50) -> List[dict]:
    pk = f"USER#{user_id}"

    if from_date and to_date:
        key_condition = Key("PK").eq(pk) & Key("SK").between(
            f"ENTRY#{from_date}", f"ENTRY#{to_date}"
        )
    elif from_date:
        key_condition = Key("PK").eq(pk) & Key("SK").gte(f"ENTRY#{from_date}")
    elif to_date:
        key_condition = Key("PK").eq(pk) & Key("SK").lte(f"ENTRY#{to_date}")
    else:
        key_condition = Key("PK").eq(pk) & Key("SK").begins_with("ENTRY#")

    resp = _table().query(
        KeyConditionExpression=key_condition,
        ScanIndexForward=False,
        Limit=limit
    )
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    items = [i for i in items if i["SK"].startswith("ENTRY#")]

    if entry_type:
        items = [i for i in items if i.get("type") == entry_type]

    return items


def get_today_entries(user_id: str) -> List[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_entries(user_id, from_date=today)


def get_latest_entry(user_id: str, entry_type: str):
    pk = f"USER#{user_id}"
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(f"ENTRY#"),
        ScanIndexForward=False,
        Limit=1,
        FilterExpression=Attr("type").eq(entry_type)
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_alerts(user_id: str) -> List[dict]:
    pk = f"USER#{user_id}"
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("ALERT#"),
        ScanIndexForward=False,
        Limit=20
    )
    return [_from_decimal(i) for i in resp.get("Items", [])]


# ── Resource operations ──

def create_resource(resource_id: str, name: str, file_type: str, file_key: str,
                    file_size: int, content_type: str, uploaded_by: str,
                    description: str = ""):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": "RESOURCES",
        "SK": f"RES#{resource_id}",
        "resourceId": resource_id,
        "name": name,
        "fileType": file_type,
        "fileKey": file_key,
        "fileSize": file_size,
        "contentType": content_type,
        "uploadedBy": uploaded_by,
        "uploadedAt": now,
        "downloadCount": 0,
        "description": description,
    }
    _table().put_item(Item=item)
    return item


def get_resources() -> List[dict]:
    resp = _table().scan(
        FilterExpression=Attr("SK").begins_with("RES#")
    )
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    items.sort(key=lambda x: x.get("uploadedAt", ""), reverse=True)
    return items


def get_resource(resource_id: str):
    resp = _table().get_item(Key={"PK": "RESOURCES", "SK": f"RES#{resource_id}"})
    return _from_decimal(resp.get("Item"))


def delete_resource_from_db(resource_id: str):
    _table().delete_item(Key={"PK": "RESOURCES", "SK": f"RES#{resource_id}"})


def increment_download_count(resource_id: str):
    _table().update_item(
        Key={"PK": "RESOURCES", "SK": f"RES#{resource_id}"},
        UpdateExpression="ADD downloadCount :one",
        ExpressionAttributeValues={":one": 1},
    )
