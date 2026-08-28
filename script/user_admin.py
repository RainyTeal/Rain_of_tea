import datetime
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select, delete
from config import engine, ai_engine, User, BroadcastDismiss, ai_content
from script.auth import require_admin

user_admin_router = APIRouter()

BAN_FMT = "%Y-%m-%d %H:%M"


def check_ban(user):
    """返回 (是否被封禁, 提示文案)。临时封禁已过期的视为未封禁。"""
    if not user.banned:
        return False, ""
    if user.ban_until:
        try:
            until = datetime.datetime.strptime(user.ban_until, BAN_FMT)
        except ValueError:
            until = None
        if until is not None and datetime.datetime.now() >= until:
            return False, ""
        return True, f"账号已被封禁，封禁至 {user.ban_until}"
    return True, "账号已被永久封禁"


def clear_expired_ban(user, session):
    """临时封禁已过期时解除封禁并写库（会话仍处打开状态时调用）"""
    if user.banned and not check_ban(user)[0]:
        user.banned = False
        user.ban_until = ""
        session.add(user)
        session.commit()


def get_ban_message(uuid: str):
    """按 uuid 返回封禁提示；未登录/未封禁/用户不存在返回 None。临时封禁过期的会自动解除。"""
    if not uuid:
        return None
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == uuid)).first()
        if not user:
            return None
        banned, msg = check_ban(user)
        if banned:
            return msg
        clear_expired_ban(user, session)
        return None


# ============ 管理员：用户管理 ============

@user_admin_router.get("/api/admin/users")
def admin_list_users(request: Request):
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    with Session(engine) as session:
        users = session.exec(select(User).order_by(User.id)).all()
    items = []
    for u in users:
        banned, msg = check_ban(u)
        items.append({
            "uid": u.id,
            "uuid": u.uuid,
            "username": u.username,
            "avatar": u.avatar or "",
            "role": u.role or "user",
            "banned": banned,
            "ban_until": u.ban_until if banned else "",
            "ban_msg": msg if banned else "",
        })
    return JSONResponse({"success": True, "users": items}, status_code=200)


class BanBody(BaseModel):
    uuid: str
    days: float


@user_admin_router.post("/api/admin/ban")
def admin_temp_ban(request: Request, body: BanBody):
    """有限期封禁：保留账号，封禁至 now + days 天"""
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    if body.uuid == request.session.get("uuid"):
        return JSONResponse({"error": "不能封禁当前登录的管理员账号"}, status_code=400)
    if not body.days or body.days <= 0:
        return JSONResponse({"error": "封禁天数必须大于 0"}, status_code=400)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == body.uuid)).first()
        if not user:
            return JSONResponse({"error": "用户不存在"}, status_code=404)
        until = datetime.datetime.now() + datetime.timedelta(days=body.days)
        user.banned = True
        user.ban_until = until.strftime(BAN_FMT)
        session.add(user)
        session.commit()
        ban_until = user.ban_until
    return JSONResponse({"success": True, "ban_until": ban_until}, status_code=200)


class UuidBody(BaseModel):
    uuid: str


@user_admin_router.post("/api/admin/ban_permanent")
def admin_perm_ban(request: Request, body: UuidBody):
    """无限期封禁：保留账号，永久禁止登录"""
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    if body.uuid == request.session.get("uuid"):
        return JSONResponse({"error": "不能封禁当前登录的管理员账号"}, status_code=400)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == body.uuid)).first()
        if not user:
            return JSONResponse({"error": "用户不存在"}, status_code=404)
        user.banned = True
        user.ban_until = ""
        session.add(user)
        session.commit()
    return JSONResponse({"success": True, "message": "已永久封禁该账号"}, status_code=200)


@user_admin_router.post("/api/admin/unban")
def admin_unban(request: Request, body: UuidBody):
    """解封：恢复正常使用"""
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == body.uuid)).first()
        if not user:
            return JSONResponse({"error": "用户不存在"}, status_code=404)
        user.banned = False
        user.ban_until = ""
        session.add(user)
        session.commit()
    return JSONResponse({"success": True, "message": "已解封该账号"}, status_code=200)


@user_admin_router.delete("/api/admin/users/{uuid}")
def admin_delete_user(request: Request, uuid: str):
    """删除账号：删除用户、其广播隐藏记录及 AI 对话记录"""
    if not require_admin(request):
        return JSONResponse({"error": "无权限，仅管理员可操作"}, status_code=403)
    if uuid == request.session.get("uuid"):
        return JSONResponse({"error": "不能删除当前登录的管理员账号"}, status_code=400)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == uuid)).first()
        if not user:
            return JSONResponse({"error": "用户不存在"}, status_code=404)
        session.delete(user)
        session.exec(delete(BroadcastDismiss).where(BroadcastDismiss.user_uuid == uuid))
        session.commit()
    with Session(ai_engine) as session:
        talks = session.exec(select(ai_content).where(ai_content.user_uuid == uuid)).all()
        for t in talks:
            session.delete(t)
        session.commit()
    return JSONResponse({"success": True, "message": "账号已删除"}, status_code=200)
