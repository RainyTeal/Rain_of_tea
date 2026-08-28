from fastapi import Request
from sqlmodel import Session, select
from config import engine, User


def current_user_role(request: Request):
    """返回当前登录用户的角色，未登录返回 None"""
    uuid = request.session.get("uuid")
    if not uuid:
        return None
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == uuid)).first()
        return user.role if user else None


def require_admin(request: Request):
    """当前请求是否为管理员"""
    return current_user_role(request) == "admin"
