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

def create_user(user_id: str, email: str, name: str, password_hash: str, role: str = "user", isActive: bool = True):
    _table().put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "email": email,
        "name": name,
        "passwordHash": password_hash,
        "role": role,
        "isActive": isActive,
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


def update_user_active_status(user_id: str, isActive: bool):
    _table().update_item(
        Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
        UpdateExpression="SET isActive = :a",
        ExpressionAttributeValues={":a": isActive},
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


# ── Topic operations ──

def create_topic(name: str):
    topic_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": "TOPICS",
        "SK": f"TOP#{topic_id}",
        "topicId": topic_id,
        "name": name,
        "createdAt": now,
    }
    _table().put_item(Item=item)
    return item


def get_topics() -> list[dict]:
    resp = _table().scan(FilterExpression=Attr("SK").begins_with("TOP#"))
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    items.sort(key=lambda x: x.get("name", ""))
    return items


def get_topic(topic_id: str):
    resp = _table().get_item(Key={"PK": "TOPICS", "SK": f"TOP#{topic_id}"})
    return _from_decimal(resp.get("Item"))


def delete_topic(topic_id: str):
    _table().delete_item(Key={"PK": "TOPICS", "SK": f"TOP#{topic_id}"})


# ── Post operations ──

def create_post(post_id: str, title: str, body: str, topic_id: str,
                author_id: str, author_name: str):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": f"POST#{post_id}",
        "SK": "META",
        "postId": post_id,
        "title": title,
        "body": body,
        "topicId": topic_id,
        "authorId": author_id,
        "authorName": author_name,
        "createdAt": now,
        "commentCount": 0,
    }
    _table().put_item(Item=item)
    return item


def get_posts(topic_id: Optional[str] = None, limit: int = 20,
              last_evaluated_key: Optional[dict] = None) -> tuple[list[dict], Optional[dict]]:
    kwargs = {}
    if last_evaluated_key:
        kwargs["ExclusiveStartKey"] = last_evaluated_key

    if topic_id:
        filter_expr = Attr("SK").eq("META") & Attr("topicId").eq(topic_id)
        resp = _table().scan(FilterExpression=filter_expr, **kwargs)
    else:
        resp = _table().scan(FilterExpression=Attr("SK").eq("META"), **kwargs)

    items = [_from_decimal(i) for i in resp.get("Items", [])]
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    lek = resp.get("LastEvaluatedKey")
    return items, lek


def get_post(post_id: str):
    resp = _table().get_item(Key={"PK": f"POST#{post_id}", "SK": "META"})
    return _from_decimal(resp.get("Item"))


def delete_post(post_id: str):
    # Delete post meta and all comments
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(f"POST#{post_id}")
    )
    with _table().batch_writer() as batch:
        for item in resp.get("Items", []):
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})


def increment_comment_count(post_id: str):
    _table().update_item(
        Key={"PK": f"POST#{post_id}", "SK": "META"},
        UpdateExpression="ADD commentCount :one",
        ExpressionAttributeValues={":one": 1},
    )


def decrement_comment_count(post_id: str, amount: int = 1):
    _table().update_item(
        Key={"PK": f"POST#{post_id}", "SK": "META"},
        UpdateExpression="ADD commentCount :minus",
        ExpressionAttributeValues={":minus": -amount},
    )


# ── Comment operations ──

def create_comment(comment_id: str, post_id: str, parent_comment_id: Optional[str],
                   author_id: str, author_name: str, body: str):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": f"POST#{post_id}",
        "SK": f"COMMENT#{now}#{comment_id}",
        "commentId": comment_id,
        "postId": post_id,
        "parentCommentId": parent_comment_id,
        "authorId": author_id,
        "authorName": author_name,
        "body": body,
        "createdAt": now,
    }
    _table().put_item(Item=item)
    return item


def get_comments(post_id: str) -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(f"POST#{post_id}")
    )
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    # Return only comment items, not META
    return [i for i in items if i["SK"].startswith("COMMENT#")]


def get_comment(post_id: str, comment_id: str):
    # We need to find the comment by commentId, SK includes timestamp so we scan
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(f"POST#{post_id}")
    )
    for item in resp.get("Items", []):
        if item.get("commentId") == comment_id:
            return _from_decimal(item)
    return None


def delete_comment_and_replies(post_id: str, comment_id: str) -> int:
    pk = f"POST#{post_id}"
    resp = _table().query(KeyConditionExpression=Key("PK").eq(pk))
    deleted = 0
    with _table().batch_writer() as batch:
        for item in resp.get("Items", []):
            cid = item.get("commentId")
            if cid == comment_id or item.get("parentCommentId") == comment_id:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
                deleted += 1
    return deleted


# ── Report operations ──

def create_report(report_id: str, target_type: str, target_id: str, post_id: str,
                  reported_by_id: str, reported_by_name: str, reason: str):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": "REPORTS",
        "SK": f"REPORT#{now}#{report_id}",
        "reportId": report_id,
        "targetType": target_type,
        "targetId": target_id,
        "postId": post_id,
        "reportedById": reported_by_id,
        "reportedByName": reported_by_name,
        "reason": reason,
        "status": "pending",
        "createdAt": now,
    }
    _table().put_item(Item=item)
    return item


def get_reports(status: Optional[str] = None) -> list[dict]:
    resp = _table().scan(FilterExpression=Attr("SK").begins_with("REPORT#"))
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    if status:
        items = [i for i in items if i.get("status") == status]
    return items


# ── Carousel operations ──

def create_slide(slide_id: str, caption: str, image_key: str, content_type: str,
                 position: int, uploaded_by: str, file_size: int):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "PK": "CAROUSEL",
        "SK": f"SLIDE#{position:03d}#{slide_id}",
        "slideId": slide_id,
        "caption": caption,
        "imageKey": image_key,
        "contentType": content_type,
        "position": position,
        "uploadedBy": uploaded_by,
        "uploadedAt": now,
        "fileSize": file_size,
    }
    _table().put_item(Item=item)
    return item


def get_slides() -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq("CAROUSEL"),
        ScanIndexForward=True,
    )
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    items.sort(key=lambda x: x.get("position", 0))
    return items


def get_slide(slide_id: str):
    resp = _table().scan(
        FilterExpression=Attr("SK").begins_with("SLIDE#") & Attr("slideId").eq(slide_id)
    )
    items = resp.get("Items", [])
    return _from_decimal(items[0]) if items else None


def delete_slide_from_db(slide_id: str):
    resp = _table().scan(
        FilterExpression=Attr("SK").begins_with("SLIDE#") & Attr("slideId").eq(slide_id)
    )
    for item in resp.get("Items", []):
        _table().delete_item(Key={"PK": item["PK"], "SK": item["SK"]})


def reorder_slides(slide_ids: list[str]):
    for idx, slide_id in enumerate(slide_ids):
        new_pos = idx + 1
        resp = _table().scan(
            FilterExpression=Attr("SK").begins_with("SLIDE#") & Attr("slideId").eq(slide_id)
        )
        for item in resp.get("Items", []):
            _table().update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET #p = :p",
                ExpressionAttributeNames={"#p": "position"},
                ExpressionAttributeValues={":p": new_pos},
            )


def resolve_report(report_id: str, resolved_by: str, status: str = "resolved"):
    now = datetime.now(timezone.utc).isoformat()
    # Find the report by scanning (SK includes timestamp)
    resp = _table().scan(FilterExpression=Attr("SK").begins_with("REPORT#"))
    for item in resp.get("Items", []):
        if item.get("reportId") == report_id:
            _table().update_item(
                Key={"PK": item["PK"], "SK": item["SK"]},
                UpdateExpression="SET #s = :s, resolvedAt = :ra, resolvedBy = :rb",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": status,
                    ":ra": now,
                    ":rb": resolved_by,
                },
            )
            return True
    return False
