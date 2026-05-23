# 短视频文案管理系统

本地单用户的 Web 端短视频文案工作台。

- **后端**：FastAPI + SQLAlchemy 2.0 + SQLite，通过 `openai` SDK 同时兼容 DeepSeek 与 Kimi
- **前端**：React + TypeScript + Vite + Tailwind + Framer Motion，草绿调色 + iOS 风交互
- **数据**：SQLite 自动落在 `backend/data/app.db`

## 快速启动

需要两个终端，分别跑后端和前端。

### 1. 后端（端口 8000）

首次启动前可复制 `.env.example` 并在环境变量中配置 `DEEPSEEK_API_KEY`。如果不配置，DeepSeek provider 会以空 Key 初始化，之后可在「模型与 Key」页面手动填写。

```bash
cd backend
"D:/PythonVEnv/FirstVEnv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

首次启动会自动建表并写入 seed 数据：

- DeepSeek + Kimi 两家 provider
- 5 个模型，默认 `deepseek-v4-flash`
- 文案生成 / 文案润色两条默认 system prompt

接口文档：<http://127.0.0.1:8000/docs>

### 2. 前端（端口 5173）

```bash
cd frontend
npm install   # 首次
npm run dev
```

浏览器打开 <http://localhost:5173>。Vite 已配置 `/api` 反向代理到 8000，无需额外设置。

## 功能地图

| 入口 | 说明 |
|---|---|
| 所有文案 | 卡片列表，点击进入编辑 |
| 新建文案 | 输入描述 → 选择模型与 Prompt → 流式生成 → 自动保存 |
| 文案详情 | 手动编辑 / AI 润色（预览后采用） / 保存 |
| Prompt | 按功能 Tab 维护多套提示词，可设默认 |
| 模型与 Key | 维护 provider 接入信息和可用模型，可设全局默认 |
| 图片生成 | 占位，敬请期待 |

## 关键约定

- 所有 AI 调用走 SSE 流式响应（`text/event-stream`），事件 `delta` 是增量文本，`done` 表示结束（generate 会附带新文案 id），`error` 报错。
- 文案润色不自动落库，需用户手动点保存。
- 默认 prompt / 默认模型不可删除，需先把别的设为默认。
- API Key 仅本地 SQLite 存储，前端展示时会自动 mask。

## 文件结构

```
backend/
  app/
    main.py / config.py / db.py / models.py / schemas.py
    ai_client.py        # openai SDK 统一封装
    seed.py             # 首次启动 seed
    routers/copywrites.py | prompts.py | settings.py
  run.py
frontend/
  src/
    api/         # 后端调用封装 + SSE
    components/  # Layout / Modal / Select / Toast / Spinner
    pages/       # CopywritesList / CopywriteNew / CopywriteDetail / PromptsManager / ModelsManager / ImagesPlaceholder
    theme tokens 在 tailwind.config.js 的 colors.sage
```
