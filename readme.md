# Rain of Tea

一个基于 **FastAPI + SQLModel + Jinja2** 的个人网站后端与前端。

> **项目继承关系**：本项目是 **firefly** 项目的**继承与延续版本**，在其基础上重构并面向开源维护。

> 提示：本项目仍在开发中，代码可能存在未完成功能与潜在的稳定性 / 安全问题，请勿直接用于生产环境。

## 功能特性

- 用户注册 / 登录 / 会话管理
- 多模型 AI 对话：支持 DeepSeek（V4 Flash / V4 Pro，可开启深度思考）与 OpenAI 模型切换
- 多套聊天提示词（persona）可选
- 用户管理 / 封禁（含限时封禁）
- 系统广播
- 代码 / 文件上传下载
- 内网穿透（FRP）可选支持

## 环境要求

- Python 3.10+
- 可用的 DeepSeek / OpenAI API Key

## 安装

```bash
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，并填写你自己的配置：

```bash
cp .env.example .env
# 编辑 .env，至少填写 DEEPSEEK_APIKEY 与 SECRET_KEY
```

| 变量 | 说明 | 是否必填 |
| --- | --- | --- |
| `DEEPSEEK_APIKEY` | DeepSeek API Key | 是 |
| `OPENAI_APIKEY` | OpenAI API Key | 否 |
| `SECRET_KEY` | 会话签名密钥，请用足够长的随机字符串 | 是 |
| `FTP_PATH` | 文件上传根目录 | 否（默认 `./ftp`） |
| `FRP_TOKEN` / `FRP_PORT` | 内网穿透（FRP）参数 | 否 |

## 运行

```bash
python main.py
```

服务默认监听 `0.0.0.0:8000`，浏览器访问 `http://localhost:8000`。

## 项目结构

```
main.py                 # 入口，装配路由并启动服务
config.py               # 模型配置、数据库、提示词、应用实例
database.db             # 运行时数据库（不提交到仓库）
script/                 # 各功能路由
templates/              # Jinja2 前端页面与静态资源
```

## 免责声明

- 本项目仅供学习交流使用。
- 运行 / 部署本项目的安全责任由使用者自行承担。

## License

尚未选择开源许可证。

## 作者
stdCharly  
RainyTeal
