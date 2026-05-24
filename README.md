# 文案 Studio — 短视频脚本工作台

本地单用户的 Web 端短视频生产工作台，覆盖文案生成、配图生成、视频合成全流程。

- **后端**：FastAPI + SQLAlchemy 2.0 + SQLite，通过 `openai` SDK 兼容 DeepSeek / Kimi，通过 DashScope SDK 接入通义万相文生图与 CosyVoice 配音
- **前端**：React 18 + TypeScript + Vite + Tailwind CSS + Framer Motion，草绿调色 + iOS 风交互
- **数据**：SQLite 自动落在 `backend/data/app.db`，上传资源落在 `backend/data/uploads/`

## 功能总览

### 内容生产

| 入口 | 路由 | 说明 |
|---|---|---|
| 所有文案 | `/` | 卡片列表，显示最近更新时间、Token 总消耗，支持删除 |
| 新建文案 | `/copywrites/new` | 输入描述 → 选模型与 Prompt → 流式生成 → 自动保存（支持联网搜索、重新生成） |
| 图片生成 | `/images` | 基于已有文案，通过本地 Ollama 拆分为分镜 prompts → 调通义万相批量生图 → 查看/管理图片集 |
| 视频合成 | `/videos` | 选择图片集 + BGM + 配音参数 → CosyVoice TTS（自动倍速校准到目标时长）→ 裁剪图片统一画幅 → 拼接轮播视频 → MP4 下载 |

### 文案编辑

| 入口 | 路由 | 说明 |
|---|---|---|
| 文案详情 | `/copywrites/:id` | 自由编辑标题/正文 / AI 润色（弹出层预览后采用）/ 手动保存落库 / 版本历史与 Token 消耗明细 |

### 素材库

| 入口 | 路由 | 说明 |
|---|---|---|
| BGM | `/bgms` | 上传背景音乐文件，管理曲库，合成时选择 |

### AI 配置

| 入口 | 路由 | 说明 |
|---|---|---|
| Prompt | `/prompts` | 按「文案生成 / 文案润色 / 文生图分镜」Tab 维护多套 Prompt，可设默认 |
| 模型与 Key | `/models` | 维护 Provider 接入信息（API Key / Base URL），管理按用途（对话 / 文生图 / TTS / 分镜）分类的可用模型，设全局默认 |

## 快速启动

需要两个终端，分别跑后端和前端。

### 1. 后端（端口 8000）

首次启动前可复制 `.env.example` 并配置 `DEEPSEEK_API_KEY`。留空也可以，之后在「模型与 Key」页面手动填写。

```bash
cd backend
"D:/PythonVEnv/FirstVEnv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

首次启动自动建表并写入 seed 数据：
- DeepSeek / Kimi / 阿里云百炼 / Ollama 四个 Provider
- 聊天模型（DeepSeek V4 Flash / Pro, Kimi K2, Moonshot）、文生图模型（通义万相 2.0~2.6）、TTS 模型（CosyVoice V2~V3.5）、分镜模型（Qwen3 8B）
- 文案生成 / 文案润色 / 文生图分镜 三条默认 System Prompt

也可使用 `run.py` 快捷启动：

```bash
cd backend
"D:/PythonVEnv/FirstVEnv/Scripts/python.exe" run.py
```

接口文档：<http://127.0.0.1:8000/docs>

### 2. 前端（端口 5173）

```bash
cd frontend
npm install   # 首次
npm run dev
```

浏览器打开 <http://localhost:5173>。Vite 已配置 `/api` 反向代理到 8000，同时代理 `/media` 资源路径。

## 关键特性

### AI 对话（文案生成/润色）
- 全部调用走 SSE 流式响应（`text/event-stream`），事件 `delta` 增量文本、`done` 结束（生成会附带新文案 id）、`error` 报错、`usage` Token 用量及费用、`search` 联网搜索状态
- 生成结束后自动落库为一条新文案并进入详情页
- 润色流结束后自动保存为 `polish` 版本，同时记录 Token 消耗

### 联网搜索
- 默认开启，底层走 DuckDuckGo HTML 搜索，自动注入搜索摘要到 AI 上下文中
- 支持通过本地代理（`127.0.0.1:10808`）翻墙，直连失败自动回退代理
- 前端展示搜索开启/启用/失败状态

### 费用估算
- DeepSeek V4 Flash / V4 Pro 按官方公开定价计算（输入缓存命中/未命中 + 输出）
- 价格数据内置于 `ai_client.py`，标注日期和活动折扣
- 非 DeepSeek 模型仅展示 Token 用量，不估算费用
- Token 消耗（输入/输出/总计/费用）持久化到数据库，在文案列表卡片和详情页的版本历史中展示

### 版本追踪
- 每次 AI 生成、AI 润色、手动保存均记录 `copywrite_versions`
- 标记来源：`initial` / `user_edit` / `polish`
- 每条 AI 生成的版本自动记录 Token 消耗（Provider、模型、输入/输出/缓存 Token、费用）

### 图片生成
- 选择已有文案，通过本地 Ollama（默认 `qwen3:8b`）拆分为多个分镜 prompts
- 调阿里云通义万相（DashScope ImageSynthesis）批量生图
- 支持多模型、多种画幅尺寸、prompt_extend、负向提示词、种子参数
- 图片集状态追踪（pending → running → done/failed/partial）

### 视频合成
- CosyVoice TTS 配音：首次按 1.0 倍速合成，若时长超出容差则自动计算 speech_rate 校准到目标时长
- 图片预处理：统一裁剪/缩放到选定画幅（人像 9:16 / 横屏 16:9 / 方形 1:1）
- moviepy 拼接图片轮播 + 配音 + BGM → 输出 H.264 MP4
- 前后端全链路 SSE 进度推送

### Provider & Model 管理
- 支持任意 OpenAI 兼容 API：修改 Base URL 即可接入
- 模型新增 `purpose` 字段（`chat` / `image` / `tts` / `prompt_split`），每种用途可独立设默认
- 可动态添加/删除模型（模型 ID + 显示名 + 用途）
- API Key 仅本地 SQLite 存储，前端展示自动 mask

### Prompt 管理
- 按功能键分 Tab（`copywrite_generate` / `copywrite_polish` / `image_prompt_split`）
- 每功能可维护多套，调用时临时切换
- 默认 Prompt 不可删除（需先设别的为默认）

### BGM 管理
- 上传 MP3 等音频文件，自动计算时长
- 文件统一存储在 `uploads/bgm/`，通过 `/media/` 路由访问

## 资源文件

上传/生成的资源文件统一存储在 `backend/data/uploads/`：
- `bgm/` — BGM 音频文件
- `image_sets/{id}/` — 各图片集的生图结果
- `videos/{id}/` — 合成的视频文件

前端通过 `/media/{relpath}` 直接访问，Vite 开发服务器已配置反向代理。

## 文件结构

```
backend/
  app/
    main.py           # FastAPI 入口、路由注册、CORS、静态文件挂载
    config.py         # 路径、端口、环境变量
    db.py             # SQLAlchemy engine / session
    models.py         # ORM: Copywrite / CopywriteVersion / SystemPrompt / Provider / Model / BgmTrack / ImageSet / ImageSetItem / Video
    schemas.py        # Pydantic 请求/响应模型
    ai_client.py      # OpenAI SDK 封装、联网搜索、Token 费用计算
    seed.py           # 首次启动 seed 数据（含增量补 seed）
    routers/
      copywrites.py   # CRUD + AI 生成/润色 SSE 端点
      prompts.py      # SystemPrompt CRUD + 设默认
      settings.py     # Provider / Model CRUD + 设默认（含 purpose 筛选）
      image_sets.py   # 图片集 CRUD + 分镜拆分 + 批量生成 SSE 端点
      videos.py       # 视频 CRUD + 合成启动 SSE 端点（进度推送）
      bgms.py         # BGM 上传 / 列表 / 重命名 / 删除
    services/
      storage.py      # 资源文件路径工具、上传目录初始化
      image_gen.py    # Ollama 分镜拆分 + DashScope 文生图 + URL 下载
      video_synth.py  # CosyVoice TTS + 图片预处理 + moviepy 视频合成
      sse.py          # SSE 事件推送工具函数
    run.py            # 快捷入口
    data/             # SQLite 文件 + uploads/ 资源目录
frontend/
  src/
    api/
      client.ts       # HTTP 封装 + SSE 流式读取器
      copywrites.ts   # 文案 CRUD
      prompts.ts      # Prompt CRUD
      settings.ts     # Provider / Model CRUD
      imageSets.ts    # 图片集 CRUD + 生成
      videos.ts       # 视频 CRUD + 合成
      bgms.ts         # BGM 管理
      types.ts        # TypeScript 接口定义（含 ImageSet / Video / BGM 类型）
      aiUsage.ts      # Token 用量 / 搜索状态的格式化
    components/
      Layout.tsx      # 侧边栏导航（分组布局）+ 主内容区
      Modal.tsx       # 通用弹出层
      Select.tsx      # 下拉选择器
      Spinner.tsx     # 加载动画
      Toast.tsx       # 轻提示
    pages/
      CopywritesList.tsx   # 文案列表
      CopywriteNew.tsx     # 新建 + AI 生成
      CopywriteDetail.tsx  # 编辑 + AI 润色
      ImageSetWorkbench.tsx  # 图片生成工作台（分镜 → 生图 → 预览）
      VideoSynthesizer.tsx   # 视频合成面板（参数配置 + 进度 + 播放）
      BgmLibrary.tsx         # BGM 曲库管理
      PromptsManager.tsx     # Prompt 管理
      ModelsManager.tsx      # 模型与 Key 管理（按用途 Tab 分组）
    styles/
      index.css       # Tailwind + 自定义主题
    App.tsx           # 路由 + 页面切换动画
    main.tsx          # React 入口
```
