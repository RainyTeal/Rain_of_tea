import datetime
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select, delete
from config import engine, User, Broadcast, BroadcastDismiss
from script.auth import require_admin

broadcast_router = APIRouter()


def _serialize(b: Broadcast):
    return {"id": b.id, "title": b.title, "content": b.content, "created_at": b.created_at}


# ============ 用户端 ============

@broadcast_router.get("/api/broadcasts")
def list_broadcasts(request: Request):
    """当前用户可见的广播列表（已选择"不再展示"的会被过滤掉）"""
    uuid = request.session.get("uuid") or ""
    with Session(engine) as session:
        broadcasts = session.exec(select(Broadcast).order_by(Broadcast.id.desc())).all()
        if uuid:
            dismissed = set(session.exec(
                select(BroadcastDismiss.broadcast_id).where(BroadcastDismiss.user_uuid == uuid)
            ).all())
        else:
            dismissed = set()
    items = [_serialize(b) for b in broadcasts if b.id not in dismissed]
    return JSONResponse({"success": True, "broadcasts": items}, status_code=200)


class DismissBody(BaseModel):
    broadcast_id: int


@broadcast_router.post("/api/broadcast/dismiss")
def dismiss_broadcast(request: Request, body: DismissBody):
    """用户选择"不再展示"，该广播对此用户永久隐藏"""
    uuid = request.session.get("uuid")
    if not uuid:
        return JSONResponse({"error": "未登录"}, status_code=401)
    with Session(engine) as session:
        if not session.get(Broadcast, body.broadcast_id):
            return JSONResponse({"error": "广播不存在"}, status_code=404)
        existing = session.exec(select(BroadcastDismiss).where(
            BroadcastDismiss.user_uuid == uuid,
            BroadcastDismiss.broadcast_id == body.broadcast_id
        )).first()
        if not existing:
            session.add(BroadcastDismiss(user_uuid=uuid, broadcast_id=body.broadcast_id))
            session.commit()
    return JSONResponse({"success": True}, status_code=200)


# ============ 管理员端 ============

@broadcast_router.get("/api/admin/broadcasts")
def admin_list_broadcasts(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    with Session(engine) as session:
        broadcasts = session.exec(select(Broadcast).order_by(Broadcast.id.desc())).all()
    return JSONResponse({"success": True, "broadcasts": [_serialize(b) for b in broadcasts]}, status_code=200)


class BroadcastBody(BaseModel):
    title: str
    content: str


@broadcast_router.post("/api/admin/broadcasts")
def admin_add_broadcast(request: Request, body: BroadcastBody):
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    title = body.title.strip()
    content = body.content.strip()
    if not title:
        return JSONResponse({"error": "标题不能为空"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容不能为空"}, status_code=400)
    b = Broadcast(
        title=title,
        content=content,
        created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    with Session(engine) as session:
        session.add(b)
        session.commit()
        session.refresh(b)
    return JSONResponse({"success": True, "broadcast": _serialize(b)}, status_code=200)


@broadcast_router.delete("/api/admin/broadcasts/{broadcast_id}")
def admin_delete_broadcast(request: Request, broadcast_id: int):
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    with Session(engine) as session:
        b = session.get(Broadcast, broadcast_id)
        if not b:
            return JSONResponse({"error": "广播不存在"}, status_code=404)
        session.delete(b)
        session.exec(delete(BroadcastDismiss).where(BroadcastDismiss.broadcast_id == broadcast_id))
        session.commit()
    return JSONResponse({"success": True}, status_code=200)
