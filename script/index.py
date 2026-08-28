import uuid
import hashlib
from fastapi import Request, APIRouter
from fastapi.responses import JSONResponse
from config import name_to_bk, engine, User
from sqlmodel import Session, select

settings_router = APIRouter()


@settings_router.get("/api/dir_bk")
def dir_bk(request: Request):
    name=list(name_to_bk.keys())
    return JSONResponse({"success": True, "backgrounds": name}, status_code=200)


@settings_router.get("/api/choose_bk")
def choose_bk(request: Request, name: str):
    if name not in name_to_bk:
        return JSONResponse({"error": "无效的主题名称"}, status_code=400)
    request.session["bk"] = name
    # 同步写入数据库，持久化用户偏好
    user_uuid = request.session.get("uuid")
    if user_uuid:
        with Session(engine) as session:
            user = session.exec(select(User).where(User.uuid == user_uuid)).first()
            if user:
                user.theme = name
                session.add(user)
                session.commit()
    return JSONResponse({"message": f"切换背景成功，当前背景：{name}", "name": name}, status_code=200)


@settings_router.get("/api/check_bk")
def check_bk(request: Request):
    stored = request.session.get("bk", "淡青")
    # 兼容旧格式（URL）和新格式（主题名）
    if stored and stored.startswith("/"):
        for k, v in name_to_bk.items():
            if v == stored:
                name = k
                break
        else:
            name = "淡青"
    elif stored in name_to_bk:
        name = stored
    else:
        name = "淡青"
    url = name_to_bk.get(name, "")
    return JSONResponse({"url": url, "name": name}, status_code=200)
