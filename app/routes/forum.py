import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.models import (
    TopicCreate, TopicResponse,
    PostCreate, PostResponse,
    CommentCreate, CommentResponse,
    ReportCreate, ReportResponse,
)
from app.database import (
    create_topic, get_topics, get_topic, delete_topic,
    create_post, get_posts, get_post, delete_post,
    create_comment, get_comments, get_comment,
    delete_comment_and_replies, increment_comment_count, decrement_comment_count,
    create_report, get_reports, resolve_report,
)
from app.auth import get_current_user, get_current_admin
from app.database import get_user_by_id

router = APIRouter()


# ── Topics ──

@router.get("/topics", response_model=list[TopicResponse])
async def list_topics(user: dict = Depends(get_current_user)):
    items = get_topics()
    return [
        TopicResponse(
            topicId=i["topicId"],
            name=i["name"],
            createdAt=i["createdAt"],
        )
        for i in items
    ]


@router.post("/admin/topics", response_model=TopicResponse)
async def create_topic_endpoint(
    body: TopicCreate,
    user: dict = Depends(get_current_admin),
):
    existing = get_topics()
    if any(t["name"].lower() == body.name.strip().lower() for t in existing):
        raise HTTPException(status_code=409, detail="Topic already exists")

    item = create_topic(body.name.strip())
    return TopicResponse(
        topicId=item["topicId"],
        name=item["name"],
        createdAt=item["createdAt"],
    )


@router.delete("/admin/topics/{topic_id}")
async def delete_topic_endpoint(
    topic_id: str,
    user: dict = Depends(get_current_admin),
):
    topic = get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    delete_topic(topic_id)
    return {"detail": "Topic deleted"}


# ── Posts ──

@router.get("/posts", response_model=list[PostResponse])
async def list_posts(
    topic: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    user: dict = Depends(get_current_user),
):
    topics = {t["topicId"]: t["name"] for t in get_topics()}
    items, lek = get_posts(topic_id=topic, limit=limit)
    return [
        PostResponse(
            postId=i["postId"],
            title=i["title"],
            body=i["body"],
            topicId=i["topicId"],
            topicName=topics.get(i["topicId"], ""),
            authorId=i["authorId"],
            authorName=i["authorName"],
            createdAt=i["createdAt"],
            commentCount=i.get("commentCount", 0),
        )
        for i in items
    ]


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post_endpoint(
    post_id: str,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    topic = get_topic(post["topicId"])

    return PostResponse(
        postId=post["postId"],
        title=post["title"],
        body=post["body"],
        topicId=post["topicId"],
        topicName=topic["name"] if topic else "",
        authorId=post["authorId"],
        authorName=post["authorName"],
        createdAt=post["createdAt"],
        commentCount=post.get("commentCount", 0),
    )


@router.post("/posts", response_model=PostResponse)
async def create_post_endpoint(
    body: PostCreate,
    user: dict = Depends(get_current_user),
):
    topic = get_topic(body.topicId)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    post_id = str(uuid.uuid4())
    item = create_post(
        post_id=post_id,
        title=body.title.strip(),
        body=body.body.strip(),
        topic_id=body.topicId,
        author_id=user.get("PK", "").replace("USER#", ""),
        author_name=user.get("name", ""),
    )
    return PostResponse(
        postId=item["postId"],
        title=item["title"],
        body=item["body"],
        topicId=item["topicId"],
        topicName=topic["name"],
        authorId=item["authorId"],
        authorName=item["authorName"],
        createdAt=item["createdAt"],
        commentCount=0,
    )


@router.delete("/posts/{post_id}")
async def delete_post_endpoint(
    post_id: str,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    user_id = user.get("PK", "").replace("USER#", "")
    is_admin = user.get("role") == "admin"
    if post["authorId"] != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    delete_post(post_id)
    return {"detail": "Post deleted"}


# ── Comments ──

@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    post_id: str,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = get_comments(post_id)
    comments.sort(key=lambda c: c.get("createdAt", ""))
    return [
        CommentResponse(
            commentId=c["commentId"],
            postId=c["postId"],
            parentCommentId=c.get("parentCommentId"),
            authorId=c["authorId"],
            authorName=c["authorName"],
            body=c["body"],
            createdAt=c["createdAt"],
        )
        for c in comments
    ]


@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
async def create_comment_endpoint(
    post_id: str,
    body: CommentCreate,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if body.parentCommentId:
        parent = get_comment(post_id, body.parentCommentId)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")

    comment_id = str(uuid.uuid4())
    item = create_comment(
        comment_id=comment_id,
        post_id=post_id,
        parent_comment_id=body.parentCommentId,
        author_id=user.get("PK", "").replace("USER#", ""),
        author_name=user.get("name", ""),
        body=body.body.strip(),
    )
    increment_comment_count(post_id)

    return CommentResponse(
        commentId=item["commentId"],
        postId=item["postId"],
        parentCommentId=item.get("parentCommentId"),
        authorId=item["authorId"],
        authorName=item["authorName"],
        body=item["body"],
        createdAt=item["createdAt"],
    )


@router.delete("/posts/{post_id}/comments/{comment_id}")
async def delete_comment_endpoint(
    post_id: str,
    comment_id: str,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = get_comment(post_id, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user_id = user.get("PK", "").replace("USER#", "")
    is_admin = user.get("role") == "admin"
    if comment["authorId"] != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    deleted = delete_comment_and_replies(post_id, comment_id)
    decrement_comment_count(post_id, deleted)
    return {"detail": f"Deleted {deleted} comment(s)"}


# ── Reports ──

@router.post("/posts/{post_id}/report")
async def report_post(
    post_id: str,
    body: ReportCreate,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    report_id = str(uuid.uuid4())
    create_report(
        report_id=report_id,
        target_type="post",
        target_id=post_id,
        post_id=post_id,
        reported_by_id=user.get("PK", "").replace("USER#", ""),
        reported_by_name=user.get("name", ""),
        reason=body.reason.strip(),
    )
    return {"detail": "Report submitted"}


@router.post("/posts/{post_id}/comments/{comment_id}/report")
async def report_comment(
    post_id: str,
    comment_id: str,
    body: ReportCreate,
    user: dict = Depends(get_current_user),
):
    post = get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = get_comment(post_id, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    report_id = str(uuid.uuid4())
    create_report(
        report_id=report_id,
        target_type="comment",
        target_id=comment_id,
        post_id=post_id,
        reported_by_id=user.get("PK", "").replace("USER#", ""),
        reported_by_name=user.get("name", ""),
        reason=body.reason.strip(),
    )
    return {"detail": "Report submitted"}


@router.get("/admin/reports", response_model=list[ReportResponse])
async def list_reports(
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_admin),
):
    items = get_reports(status=status)
    return [
        ReportResponse(
            reportId=i["reportId"],
            targetType=i["targetType"],
            targetId=i["targetId"],
            postId=i["postId"],
            reportedById=i["reportedById"],
            reportedByName=i["reportedByName"],
            reason=i["reason"],
            status=i["status"],
            createdAt=i["createdAt"],
            resolvedAt=i.get("resolvedAt"),
            resolvedBy=i.get("resolvedBy"),
        )
        for i in items
    ]


@router.patch("/admin/reports/{report_id}")
async def moderate_report(
    report_id: str,
    body: dict,
    user: dict = Depends(get_current_admin),
):
    status = body.get("status", "resolved")
    if status not in ("resolved", "dismissed"):
        raise HTTPException(status_code=422, detail="Invalid status")

    ok = resolve_report(
        report_id=report_id,
        resolved_by=user.get("PK", "").replace("USER#", ""),
        status=status,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"detail": f"Report {status}"}
