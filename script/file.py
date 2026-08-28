import os
import shutil
from fastapi import FastAPI, Request, Form, Body,APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from config import ftp_path,templates,name_to_bk
file_router=APIRouter()
@file_router.get("/download")
def download_page(request: Request):
    if not request.session.get("uuid"):
        return RedirectResponse("/login", status_code=303)
    theme_name = request.session.get("bk", "淡青")
    bg_url = name_to_bk.get(theme_name, "/static/bg.png")
    return templates.TemplateResponse(request, "download.html", {"request": request, "theme_class":"theme-light" if theme_name == "淡青" else "","bg_url":bg_url})

@file_router.post("/api/dir")
def list_dir(request: Request, path: str=Body(...)):
    path = os.path.abspath(ftp_path+path)
    if( not os.path.abspath(ftp_path) == path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if not os.path.exists(path):
        return JSONResponse({"error": "路径不存在"}, status_code=404)
    if not os.path.isdir(path):
        return JSONResponse({"error": "不是目录"}, status_code=400)
    entries = os.listdir(path)
    entries.sort(key=lambda x: (( '.' in x), x.lower()))
    return JSONResponse({"success": True, "path": path, "entries": entries})
 
@file_router.get("/api/download")
def download_file(request: Request, path: str):
    path = os.path.abspath(ftp_path+path)
    if( not os.path.abspath(ftp_path) == path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if not os.path.exists(path):
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    if not os.path.isfile(path):
        return JSONResponse({"error": "不是文件"}, status_code=400)
    return FileResponse(
        path=os.path.abspath(path),
        filename=os.path.basename(path),
        media_type="application/zip"
    ) 

@file_router.post("/api/open_file")
def open_file(request: Request, path: str=Body(...)):
    path = os.path.abspath(ftp_path+path)   
    if( not os.path.abspath(ftp_path) == path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if not os.path.exists(path):
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    if not os.path.isfile(path):
        return JSONResponse({"error": "不是文件"}, status_code=400)
    return FileResponse(
        path=os.path.abspath(path),
        filename=os.path.basename(path)
    )

@file_router.post("/api/mkdir")
def create_directory(request: Request, path: str=Body(...),name:str=Body(...)):
    path = os.path.abspath(ftp_path+path+"/"+name)
    if( not os.path.abspath(ftp_path) == path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if os.path.exists(path):
        return JSONResponse({"error": "目录已存在"}, status_code=400)
    os.makedirs(path)
    return JSONResponse({"success": True, "message": "目录创建成功"}, status_code=200)

@file_router.post("/api/delete")
def delete_entry(request: Request, path: str=Body(...),name:str=Body(...)):
    path = os.path.abspath(ftp_path+path+"/"+name)
    if( not os.path.abspath(ftp_path) == path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if not os.path.exists(path):
        return JSONResponse({"error": "路径不存在"}, status_code=404)
    if os.path.isfile(path):
        os.remove(path)
        return JSONResponse({"success": True, "message": "文件删除成功"}, status_code=200)
    elif os.path.isdir(path):
        shutil.rmtree(path)
        return JSONResponse({"success": True, "message": "目录删除成功"}, status_code=200)
    else:
        return JSONResponse({"error": "未知错误"}, status_code=500)
    
@file_router.post("/api/rename")
def rename_entry(request: Request, path: str=Body(...), name: str=Body(...), new_name: str=Body(...)):
    old_path = os.path.abspath(ftp_path+path+"/"+name)
    new_path = os.path.abspath(ftp_path+path+"/"+new_name)
    if( not os.path.abspath(ftp_path) == old_path[0:len(os.path.abspath(ftp_path))] or not os.path.abspath(ftp_path) == new_path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if not os.path.exists(old_path):
        return JSONResponse({"error": "路径不存在"}, status_code=404)
    if os.path.exists(new_path):
        return JSONResponse({"error": "新名称已存在"}, status_code=400)
    os.rename(old_path, new_path)
    return JSONResponse({"success": True, "message": "重命名成功"}, status_code=200)

@file_router.post("/api/upload")
def upload_file(request: Request, path: str=Body(...), file: UploadFile=File(...)):
    path = os.path.abspath(ftp_path+path)
    if( not os.path.abspath(ftp_path) == path[0:len(os.path.abspath(ftp_path))]):
        return JSONResponse({"error": "非法路径"}, status_code=400)
    if not os.path.exists(path):
        return JSONResponse({"error": "路径不存在"}, status_code=404)
    if not os.path.isdir(path):
        return JSONResponse({"error": "不是目录"}, status_code=400) 
    file_path = os.path.join(path, file.filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    return JSONResponse({"success": True, "message": "文件上传成功"}, status_code=200)