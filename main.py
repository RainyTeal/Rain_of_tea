print("加载头文件.ing...")
try:
    import os,threading,uvicorn
    from script.data_spawn import data_spawn_router 
    from script.file import file_router
    from script.ai import ai_router
    from script.login import login_router
    from script.index import settings_router
    from script.broadcast import broadcast_router
    from script.user_admin import user_admin_router
    from fastapi import Request,Body
    from fastapi.responses import FileResponse
    from config import app,using_model,templates
except Exception as e:
    print(f"加载头文件失败！\n 错误信息：{e}")
    os.system("pause")
    exit()
try:
    print(f"正在使用模型：{using_model.get('model_name')}\n 正在加载...", flush=True)
    if not using_model.get("api_key"):
        print("api key不存在！")
        os.system("pause")
        exit()


    def startfrp():
        # 内网穿透：token 与端口请通过环境变量 FRP_TOKEN / FRP_PORT 提供
        os.system(f"mefrpc -t {os.getenv('FRP_TOKEN', '')} -p {os.getenv('FRP_PORT', '')}")


    @app.get("/Gomoku")
    def Gomoku(request:Request):
        return templates.TemplateResponse(request,"Gomoku.html",{"request":request})

    @app.post("/api/create_gomoku")
    def create_gomoku(request: Request):
        pass

    @app.post("/api/choose_ai_model")
    def choose_ai_model(request: Request, model_name: str=Body(...)):
        pass

    @app.get("/BingSiteAuth.xml")
    def verify(request:Request):
        return FileResponse(path="BingSiteAuth.xml")
    app.include_router(data_spawn_router)
    app.include_router(file_router)
    app.include_router(ai_router)
    app.include_router(login_router)
    app.include_router(settings_router)
    app.include_router(broadcast_router)
    app.include_router(user_admin_router)
    if __name__=="__main__":
        #f=threading.Thread(target=startfrp)
        #f.start()
        uvicorn.run(app,reload=False,host="0.0.0.0",port=8000)
except Exception as e:
    print(f"发生错误！\n 错误信息：{e}")
    os.system("pause")
    
