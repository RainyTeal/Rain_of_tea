import uuid
import hashlib
import os
from config import engine,User,templates,name_to_bk
from fastapi import Request,APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from script.user_admin import check_ban, clear_expired_ban

login_router=APIRouter()

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "static", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

@login_router.get("/")
def home(request: Request):
    if not request.session.get("uuid"):
        return RedirectResponse("/login",status_code=303)
    with Session(engine) as session:
        getted=session.exec(select(User).where(User.uuid==request.session.get("uuid"))).first()
        if(not getted):
            return RedirectResponse("/login",status_code=303)
        banned, ban_msg = check_ban(getted)
        if banned:
            request.session.clear()
            return RedirectResponse("/login?banned=1",status_code=303)
        clear_expired_ban(getted, session)
    theme_name = request.session.get("bk", "淡青")
    bg_url = name_to_bk.get(theme_name, "/static/bg.png")
    return templates.TemplateResponse(request,"index.html",{"request":request,"username":getted.username,"avatar":getted.avatar or "","role":getted.role or "user","theme_class":"theme-light" if theme_name == "淡青" else "","bg_url":bg_url})



@login_router.get("/login")
def login(request: Request):
    with Session(engine) as session:
        getted=session.exec(select(User).where(User.uuid==request.session.get("uuid"))).first()
    if getted:
        return RedirectResponse("/",status_code=303)
    theme_name = request.session.get("bk", "淡青")
    bg_url = name_to_bk.get(theme_name, "/static/bg.png")
    return templates.TemplateResponse(request,"login.html",{"request":request,"theme_class":"theme-light" if theme_name == "淡青" else "","bg_url":bg_url})

@login_router.post("/api/logout")
def logout(request:Request):
    request.session.clear()
    return JSONResponse({"success": True, "redirect": "/login"})

class log(BaseModel):
    username:str
    password:str

@login_router.post("/api/login")
def api_login(request:Request,LogMessage:log):
    with Session(engine) as session:
        getted=session.exec(select(User).where(User.username==LogMessage.username)).first()
        if not getted:
            return JSONResponse({"error":"用户名不存在或密码错误，请检查后重试。"},status_code=401)
        if(hashlib.sha256(LogMessage.password.encode()).hexdigest()==getted.password):
            banned, ban_msg = check_ban(getted)
            if banned:
                return JSONResponse({"error": ban_msg}, status_code=403)
            clear_expired_ban(getted, session)
            request.session["uuid"]=getted.uuid
            request.session["bk"]=getted.theme or "淡青"
            return JSONResponse({"success": True, "redirect": "/"})
        else:
            return JSONResponse({"error":"用户名不存在或密码错误，请检查后重试。"},status_code=401)

class Register(BaseModel):
    username:str
    password:str
 
@login_router.post("/api/register")
def login(request:Request,register:Register):
    with Session(engine) as session:
        if(session.exec(select(User).where(User.username==register.username)).first()):
            return JSONResponse({"error":"该用户名已被注册，请选择其他用户名。"},status_code=400)
        else:
            new_user=User(username=register.username,
            password=hashlib.sha256(register.password.encode()).hexdigest(),
            uuid=uuid.uuid4().hex)
            session.add(new_user)
            session.commit()
            return JSONResponse({"success": True,"message": "注册成功，请登录"},status_code=200)

@login_router.get("/api/user_info")
def user_info(request: Request):
    uuid = request.session.get("uuid")
    if not uuid:
        return JSONResponse({"error": "未登录"}, status_code=401)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == uuid)).first()
        if not user:
            return JSONResponse({"error": "用户不存在"}, status_code=404)
        banned, ban_msg = check_ban(user)
        clear_expired_ban(user, session)
    return JSONResponse({"username": user.username, "avatar": user.avatar or "", "role": user.role or "user", "banned": banned, "ban_msg": ban_msg if banned else ""})

@login_router.post("/api/upload_avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    uuid = request.session.get("uuid")
    if not uuid:
        return JSONResponse({"error": "未登录"}, status_code=401)
    # 校验文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        return JSONResponse({"error": "只允许上传图片文件"}, status_code=400)
    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"{uuid}{ext}"
    filepath = os.path.join(AVATAR_DIR, filename)
    # 保存文件
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    # 更新数据库
    avatar_url = f"/static/avatars/{filename}"
    with Session(engine) as session:
        user = session.exec(select(User).where(User.uuid == uuid)).first()
        if not user:
            return JSONResponse({"error": "用户不存在"}, status_code=404)
        user.avatar = avatar_url
        session.add(user)
        session.commit()
    return JSONResponse({"success": True, "avatar": avatar_url})