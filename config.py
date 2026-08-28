import os
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
import sqlite3
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from sqlmodel import SQLModel, Field, create_engine, Session, select, JSON
if load_dotenv:
    load_dotenv()  # 从项目根目录 .env 读取环境变量
ftp_path = os.path.abspath(os.getenv("FTP_PATH", "ftp"))
#ftp_path=os.path.abspath("/www/wwwroot/default/firefly/ftp")
model_ds_v4_flash={
    "api_key": os.getenv("DEEPSEEK_APIKEY"),
    "model_name": "deepseek-v4-flash",
    "model_url": "https://api.deepseek.com/v1",
    "model_extra_body": {"thinking": {"type": "enabled"}},
    "reasoning_effort": "high"
}
model_ds_v4_flash_with_no_thinking={
    "api_key": os.getenv("DEEPSEEK_APIKEY"),
    "model_name": "deepseek-v4-flash",
    "model_url": "https://api.deepseek.com/v1",
    "model_extra_body": {"thinking": {"type": "disabled"}},
}
model_ds_v4_pro={
    "api_key": os.getenv("DEEPSEEK_APIKEY"),
    "model_name": "deepseek-v4-pro",
    "model_url": "https://api.deepseek.com/v1",
    "model_extra_body": {"thinking": {"type": "enabled"}},
    "reasoning_effort": "high"
}
model_ds_v4_pro_with_no_thinking={
    "api_key": os.getenv("DEEPSEEK_APIKEY"),
    "model_name": "deepseek-v4-pro",
    "model_url": "https://api.deepseek.com/v1",
    "model_extra_body": {"thinking": {"type": "disabled"}},
}
model_gpt={
    "api_key": os.getenv("OPENAI_APIKEY"),
    "model_name": "gpt-5.4-mini",
    "model_url": "https://api.openai.com/v1",
    "reasoning_effort": "high"
}

name_to_model={
    "deepseekV4Flash(深度思考)":model_ds_v4_flash,
    "deepseekV4Flash":model_ds_v4_flash_with_no_thinking,
    "deepseekV4Pro(深度思考)":model_ds_v4_pro,
    "deepseekV4pro":model_ds_v4_pro_with_no_thinking,
    "chatgpt":model_gpt,
}
using_model=model_ds_v4_pro_with_no_thinking

name_to_bk = {
    "黑白棕": "/static/bg.png",
    "淡青": "/static/bg_light.png",
}


prompt={
    "普通":
r"""
You are a helpful assistant.
""",
    "待填写":
r"""

""",
}
using_prompt=prompt["普通"]

class User(SQLModel, table=True):
    id: int = Field(default=None,primary_key=True)
    username: str= Field(index=True)
    password: str 
    uuid:str
    avatar: str = Field(default="")
    role: str = Field(default="user")
    theme: str = Field(default="淡青")
    banned: bool = Field(default=False)
    ban_until: str = Field(default="")
class ai_content(SQLModel,table=True):
    id:int=Field(default=None,primary_key=True)
    user_uuid:str
    talk_id:str
    talk_name:str
    message:list = Field(default=None, sa_type=JSON)

class Broadcast(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    title: str
    content: str
    created_at: str = Field(default="")

class BroadcastDismiss(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_uuid: str = Field(index=True)
    broadcast_id: int

engine = create_engine("sqlite:///database.db")
ai_engine = create_engine("sqlite:///ai_data.db")
SQLModel.metadata.create_all(engine)
SQLModel.metadata.create_all(ai_engine)

# ---- 轻量迁移：为旧库自动补充封禁相关列（幂等，列已存在则跳过） ----
def _migrate_ban_columns():
    con = sqlite3.connect("database.db")
    try:
        cur = con.cursor()
        cols = [row[1] for row in cur.execute("PRAGMA table_info(user)")]
        if "banned" not in cols:
            cur.execute("ALTER TABLE user ADD COLUMN banned BOOLEAN NOT NULL DEFAULT 0")
        if "ban_until" not in cols:
            cur.execute("ALTER TABLE user ADD COLUMN ban_until TEXT NOT NULL DEFAULT ''")
        con.commit()
    finally:
        con.close()

_migrate_ban_columns() 


app = FastAPI()
app.mount("/static", StaticFiles(directory="templates/static"), name="static")
templates = Jinja2Templates(directory="templates")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "please-set-a-strong-random-secret-key"),
)
