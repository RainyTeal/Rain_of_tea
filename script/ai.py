import uuid,re
from config import using_model,name_to_model,ai_engine,ai_content,templates,prompt,using_prompt,engine,User,name_to_bk
from script.user_admin import check_ban, clear_expired_ban, get_ban_message
from openai import OpenAI
from fastapi import FastAPI, Request, Form,APIRouter,Body
from fastapi.responses import JSONResponse, RedirectResponse,StreamingResponse
from sqlmodel import Session, select
ai_router=APIRouter()

@ai_router.post("/api/create_talk")
def create_talk(request:Request,talk_name:str="未命名",prompt_name:str=None):
    if prompt_name and prompt.get(prompt_name):
        selected_prompt=prompt[prompt_name]
    else:
        selected_prompt=using_prompt
    talk_id=uuid.uuid4().hex
    with Session(ai_engine) as session:
        new_talk=ai_content(user_uuid=request.session.get("uuid"),talk_id=talk_id,message=[{
            "role":"system","content":[{"type":"text",
            "text":selected_prompt}]}],talk_name=talk_name)
        session.add(new_talk)
        session.commit()
    return JSONResponse({"success": True,"talk_id": talk_id},status_code=200)

@ai_router.post("/api/sel_talk")
def sel_talk(request:Request):
    with Session(ai_engine) as session:
        talks=session.exec(select(ai_content).where(ai_content.user_uuid==request.session.get("uuid"))).all()
        return JSONResponse({"success": True,"talks": [{"talk_id": talk.talk_id, "talk_name": talk.talk_name} for talk in talks]},status_code=200)

@ai_router.post("/api/dir_model")
def dir_model(request:Request):
    return JSONResponse({"success": True, "models": list(name_to_model.keys())}, status_code=200)

@ai_router.post("/api/current_model")
def current_model(request:Request):
    """返回会话中真正生效的模型名，供前端初始显示对齐，避免显示与实际不一致"""
    current = request.session.get("using_model") or using_model
    name = None
    if current:
        for key, cfg in name_to_model.items():
            if (cfg.get("model_name") == current.get("model_name")
                    and cfg.get("model_extra_body") == current.get("model_extra_body")):
                name = key
                break
    if not name:
        name = next(iter(name_to_model), None)
    return JSONResponse({"success": True, "current": name}, status_code=200)

@ai_router.post("/api/choose_model")
def choose_model(request:Request,model_name:str):
    if(name_to_model.get(model_name)):
        request.session["using_model"]=name_to_model.get(model_name)
        return JSONResponse({"success": True,"message": f"切换模型成功，当前模型：{model_name}"},status_code=200)
    else:
        return JSONResponse({"error": "模型不存在"},status_code=400)

@ai_router.post("/api/dir_prompt")
def dir_prompt(request:Request):
    return JSONResponse({"success": True, "prompts": list(prompt.keys())}, status_code=200)

@ai_router.get("/chat/{talk_id}")
def chat(request:Request,talk_id:str):
    request.session["using_model"]=using_model
    request.session["using_prompt"]=using_prompt
    with Session(ai_engine) as session:
        getted=session.exec(select(ai_content).where(ai_content.user_uuid==request.session.get("uuid"))).first()
        if(not getted):
            return RedirectResponse("/login",status_code=303)
        talk=session.exec(select(ai_content).where(ai_content.talk_id==talk_id)).first()
        if not talk:
            return RedirectResponse("/",status_code=303)
    with Session(engine) as session:
        user=session.exec(select(User).where(User.uuid==request.session.get("uuid"))).first()
        if not user:
            return RedirectResponse("/login",status_code=303)
        banned, ban_msg = check_ban(user)
        if banned:
            request.session.clear()
            return RedirectResponse("/login?banned=1",status_code=303)
        clear_expired_ban(user, session)
        username=user.username
        avatar=user.avatar or ""
    theme_name = request.session.get("bk", "淡青")
    bg_url = name_to_bk.get(theme_name, "/static/bg.png")
    return templates.TemplateResponse(request,"chat.html",{"request":request,"talk_id":talk_id,"talk_name":talk.talk_name,"content":talk.message,"username":username,"avatar":avatar,"theme_class":"theme-light" if theme_name == "淡青" else "","bg_url":bg_url})

def chat(new_message,messages,talk_id,using_model,pictures_base64):
    client = OpenAI(
        api_key=using_model.get("api_key"),
        base_url=using_model.get("model_url"))
    messages.append({"role":"user","content":[{"type":"text","text":new_message}]})
    if(pictures_base64):
        for picture in pictures_base64:
            messages[-1]["content"].append({"type":"image_url","image_url":{"url": f"data:image/jpeg;base64,{picture}"}})
    ai_reply=""
    response = client.chat.completions.create(
        model=using_model.get("model_name"),
        messages=messages,
        stream=True,
        reasoning_effort=using_model.get("reasoning_effort"),
        extra_body=using_model.get("model_extra_body"),
    )
    flag=0
    for chunk in response:
        delta=chunk.choices[0].delta
        reasoning=getattr(delta,"reasoning_content",None)
        if(not reasoning):
            reasoning=getattr(delta,"reasoning_effort",None)
        if reasoning:
            if(flag==0):
                flag=1
                yield "\n============================\n"
            yield reasoning
        if(delta.content):
            if(flag==1):
                yield "\n============================\n"
            delta.content = re.sub(r'~', '~ ', delta.content)
            yield delta.content
            ai_reply+=delta.content
            break
    for chunk in response:
        delta=chunk.choices[0].delta
        if delta.content:
            delta.content = re.sub(r'~', '~ ', delta.content)
            yield delta.content
            ai_reply+=delta.content
    messages.append({"role":"assistant","content":ai_reply})
    with Session(ai_engine) as session:
        talk=session.exec(select(ai_content).where(ai_content.talk_id==talk_id)).first()
        talk.message=messages
        session.commit()
    
@ai_router.post("/api/ai_reply")
def ai_reply(request:Request,data: dict = Body(...)):
    new_message = data.get("new_message")
    talk_id = data.get("talk_id")
    pictures_base64 = data.get("pictures_base64", [])
    ban_msg = get_ban_message(request.session.get("uuid"))
    if ban_msg:
        return JSONResponse({"error": ban_msg}, status_code=403)
    with Session(ai_engine) as session:
        getted=session.exec(select(ai_content).where(ai_content.user_uuid==request.session.get("uuid"))).first()
        if(not getted):
            return JSONResponse({"error":"请先登录"},status_code=401)
        talk=session.exec(select(ai_content).where(ai_content.talk_id==talk_id)).first()
        if not talk:
            return JSONResponse({"error":"未找到对话"},status_code=404)
        current_model = request.session.get("using_model") or using_model
        return StreamingResponse(chat(new_message,talk.message,talk_id,current_model,pictures_base64))

@ai_router.post("/api/delete_talk")
def delete_talk(request:Request,talk_id:str):
    with Session(ai_engine) as session:
        getted=session.exec(select(ai_content).where(ai_content.user_uuid==request.session.get("uuid"))).first()
        if(not getted):
            return JSONResponse({"error":"请先登录"},status_code=401)
        talk=session.exec(select(ai_content).where(ai_content.talk_id==talk_id)).first()
        if not talk:
            return JSONResponse({"error":"未找到对话"},status_code=404)
        session.delete(talk)
        session.commit()
        return JSONResponse({"success": True,"message": "删除成功"},status_code=200)

@ai_router.post("/api/change_talk")
def change_talk(request:Request,talk_id:str=Form(...),change_talk_id:int=Form(...),new_input:str=Form(...)):
    with Session(ai_engine) as session:
        getted=session.exec(select(ai_content).where(ai_content.user_uuid==request.session.get("uuid"))).first()
        if(not getted):
            return JSONResponse({"error":"请先登录"},status_code=401)
        talk=session.exec(select(ai_content).where(ai_content.talk_id==talk_id)).first()
        if not talk:
            return JSONResponse({"error":"未找到对话"},status_code=404)
        talk.message=talk.message[0:change_talk_id]
        session.commit()
        return JSONResponse({"success": True,"message": "修改成功"},status_code=200)

@ai_router.post("/api/talk_fork")
def talk_fork(request: Request, talk_id: str = Body(...), start: int = Body(default=1),
              end: int = Body(default=None), new_name: str = Body(default=""),
              prompt_name: str = Body(default="")):
    """从现有对话截取一段消息，用新的 system prompt 创建一条新对话（用于对比不同提示词的反应）"""
    user_uuid = request.session.get("uuid")
    if not user_uuid:
        return JSONResponse({"error": "请先登录"}, status_code=401)
    ban_msg = get_ban_message(user_uuid)
    if ban_msg:
        return JSONResponse({"error": ban_msg}, status_code=403)
    with Session(ai_engine) as session:
        getted = session.exec(select(ai_content).where(ai_content.user_uuid == user_uuid)).first()
        if not getted:
            return JSONResponse({"error": "请先登录"}, status_code=401)
        src = session.exec(select(ai_content).where(ai_content.talk_id == talk_id)).first()
        if not src:
            return JSONResponse({"error": "源对话不存在"}, status_code=404)
        messages = src.message or []
        # 第 0 条通常是旧的 system prompt，仅取其后作为对话上下文
        conv = messages[1:] if len(messages) > 1 else []
        total = len(conv)
        s = max(1, int(start or 1))
        e = total if end is None else min(total, int(end))
        if s > total or s > e:
            return JSONResponse({"error": f"截取范围无效（该对话共有 {total} 条可截取消息）"}, status_code=400)
        slice_msgs = conv[s - 1:e]
        if not slice_msgs:
            return JSONResponse({"error": "截取结果为空"}, status_code=400)
        # 新 system prompt：优先用指定的 prompt_name，否则用当前默认
        if prompt_name and prompt.get(prompt_name):
            new_prompt = prompt[prompt_name]
        else:
            new_prompt = using_prompt
        new_messages = [{"role": "system", "content": [{"type": "text", "text": new_prompt}]}] + slice_msgs
        new_talk_id = uuid.uuid4().hex
        name = new_name.strip() if new_name and new_name.strip() else (src.talk_name + " · 副本")
        new_talk = ai_content(user_uuid=user_uuid, talk_id=new_talk_id, talk_name=name, message=new_messages)
        session.add(new_talk)
        session.commit()
    return JSONResponse({"success": True, "talk_id": new_talk_id, "talk_name": name, "copied": len(slice_msgs)}, status_code=200)