# 文案 Studio — 短视频生产工作台

本地单用户的 Web 端短视频一站式生产工具，覆盖文案生成、分镜配图、视频合成全流程。

- **后端**：FastAPI + SQLAlchemy 2.0 + SQLite，通过 `openai` SDK 兼容 DeepSeek / Kimi，通过 DashScope SDK 接入通义万相文生图与 CosyVoice 配音
- **前端**：React 18 + TypeScript + Vite + Tailwind CSS + Framer Motion，鼠尾草绿调色 + iOS 风交互
- **数据**：SQLite 落在 `backend/data/app.db`，上传与生成资源落在 `backend/data/uploads/`

---

## 功能总览

### 内容生产

| 页面 | 路由 | 说明 |
|---|---|---|
| 所有文案 | `/` | 卡片列表，显示最近更新时间、Token 总消耗，支持删除 |
| 新建文案 | `/copywrites/new` | 输入描述 → 选模型与 Prompt → SSE 流式生成 → 自动保存（支持联网搜索、重新生成） |
| 图片生成 | `/images` | 选择已有文案 → Ollama 分镜拆分 → 通义万相并发批量生图 → 预览/管理图片集，支持单张重新生成 |
| 视频合成 | `/videos` | 选择图片集 + BGM + 配音参数 → CosyVoice TTS（自动倍速校准）→ 裁剪统一画幅 → 拼接轮播 → 字幕烧录 → GPU 加速编码 → MP4 下载 |

### 文案编辑

| 页面 | 路由 | 说明 |
|---|---|---|
| 文案详情 | `/copywrites/:id` | 自由编辑标题/正文 / AI 润色（弹出层预览后采用）/ 手动保存 / 版本历史与 Token 消耗明细 |

### 素材库

| 页面 | 路由 | 说明 |
|---|---|---|
| BGM 曲库 | `/bgms` | 上传背景音乐，自动解析时长，合成时选择 |

### AI 配置

| 页面 | 路由 | 说明 |
|---|---|---|
| Prompt | `/prompts` | 按「文案生成 / 文案润色 / 文生图分镜」Tab 维护多套 Prompt，可设默认 |
| 模型与 Key | `/models` | 维护 Provider 接入信息（API Key / Base URL），管理按用途（对话 / 文生图 / TTS / 分镜）分类的模型，设全局默认 |

---

## 快速启动

需要两个终端，分别跑后端和前端。

### 1. 后端（端口 8000）

首次启动前可复制 `.env.example` 并配置 `DEEPSEEK_API_KEY`，留空也可以，之后在「模型与 Key」页面手动填写。

```bash
cd backend
"D:/PythonVEnv/FirstVEnv/Scripts/python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

也可使用快捷入口：

```bash
cd backend
"D:/PythonVEnv/FirstVEnv/Scripts/python.exe" run.py
```

首次启动自动建表并写入 seed 数据：

**Provider**

| Provider | 用途 |
|---|---|
| DeepSeek | 文案生成 / 润色（chat） |
| Kimi (Moonshot) | 文案生成 / 润色（chat） |
| 阿里云百炼 (DashScope) | 文生图 + CosyVoice TTS |
| Ollama (本地) | 分镜拆分（默认 Qwen3 8B） |

**预置模型**

| 用途 | 模型 |
|---|---|
| 对话（chat） | DeepSeek V3 Flash / V3 0324、Kimi K2、Moonshot V1 8K/32K/128K |
| 文生图（image） | 通义万相 2.0 Turbo（默认）、2.1 Turbo/Plus、2.2 Flash、2.6 |
| TTS（tts） | CosyVoice V3 Flash（默认）、V3 Plus、V3.5 Flash、V3.5 Plus、V2 |
| 分镜拆分（prompt_split） | Qwen3 8B（Ollama） |

**预置 Prompt**：文案生成 / 文案润色 / 文生图分镜 三条 System Prompt。

接口文档：<http://127.0.0.1:8000/docs>

### 2. 前端（端口 5173）

```bash
cd frontend
npm install   # 首次
npm run dev
```

浏览器打开 <http://localhost:5173>。Vite 已配置 `/api` 代理到 8000，`/media` 代理到静态资源。

---

## 关键特性

### AI 对话（文案生成 / 润色）
- 全部调用走 SSE 流式响应（`text/event-stream`）；事件类型：`delta`（增量文本）、`done`（含新文案 id）、`error`、`usage`（Token + 费用）、`search`（联网搜索状态）
- 生成结束后自动落库为一条新文案并跳转详情页
- 润色流结束后自动保存为 `polish` 版本并记录 Token 消耗

### 联网搜索
- 默认开启，底层走 DuckDuckGo HTML 搜索，结果注入 AI 上下文
- 支持本地代理（`127.0.0.1:10808`），直连失败自动回退
- 前端显示搜索开启 / 运行中 / 失败状态

### 费用估算
- DeepSeek V3 Flash / V3 Pro 按官方公开定价计算（输入缓存命中/未命中 + 输出）
- 非 DeepSeek 模型仅展示 Token 用量，不估算费用
- Token 消耗持久化到数据库，在列表卡片和版本历史中展示

### 版本追踪
- 每次 AI 生成、AI 润色、手动保存均写入 `copywrite_versions`
- 来源标记：`initial` / `user_edit` / `polish`
- AI 生成版本自动记录 Provider、模型、输入/输出/缓存 Token、费用

### 图片生成
- 通过本地 Ollama（默认 `qwen3:8b`）将文案拆分为多个分镜 prompts
- 并发调用阿里云通义万相（DashScope `ImageSynthesis`）批量生图，最多 4 路并发
- 支持多模型、多画幅尺寸、prompt_extend、负向提示词、种子参数
- 图片集状态追踪：`pending` → `running` → `done` / `failed` / `partial`
- 支持对单张失败图片单独重新生成（`POST /api/image-sets/{sid}/items/{item_id}/regenerate`）

### 视频合成
- **TTS 配音**：首次按 1.0 倍速合成；若时长超出容差（0.75 s）则自动计算 `speech_rate` 校准到目标时长；支持 CosyVoice V2 / V3 / V3.5，含音色兼容性校验
- **字幕烧录**：按句子切割文案，按时长比例分配字幕段，`TextClip` 叠加到视频底部；支持自定义字体颜色（`#RRGGBB`）、描边颜色、字号（留空自动按画幅比例计算）
- **图片预处理**：`ImageOps.fit` 统一裁剪/缩放到选定画幅（人像 9:16 / 横屏 16:9 / 方形 1:1）
- **GPU 加速编码**：自动检测 NVIDIA NVENC、AMD AMF、Intel QSV；无 GPU 则回退 `libx264`；编码器与编码耗时落库（`codec_used` / `encoding_duration`）
- **实时帧进度**：`FrameProgressLogger` 在编码阶段推送逐帧进度，前端进度条实时更新
- **全链路 SSE**：阶段事件 `prepare_images` → `tts` → `build`（含帧进度）→ `done`（含视频时长、编码器）

### Provider & 模型管理
- 支持任意 OpenAI 兼容 API，修改 Base URL 即可接入
- 模型按 `purpose` 分类（`chat` / `image` / `tts` / `prompt_split`），每种用途独立设默认
- 可动态添加 / 删除模型（模型 ID + 显示名 + 用途 + Provider）
- API Key 仅存本地 SQLite，前端自动 mask

### Prompt 管理
- 按功能键分 Tab：`copywrite_generate` / `copywrite_polish` / `image_prompt_split`
- 每功能可维护多套，调用时临时切换；默认 Prompt 不可删除

### BGM 管理
- 上传 MP3 等音频文件，自动解析时长（`moviepy.AudioFileClip`）
- 文件存储在 `uploads/bgm/`，通过 `/media/` 路由访问

---

## 资源文件

所有上传/生成资源统一存储在 `backend/data/uploads/`：

```
uploads/
  bgm/                  # BGM 音频
  image_sets/{id}/      # 各图片集生图结果（scene_001_01.png …）
  videos/{id}/          # 合成视频（video.mp4）、配音（voice.wav）、缩略图（thumbnail.jpg）
```

前端通过 `/media/{relpath}` 直接访问，Vite 开发服务器已配置反向代理。

---

## 文件结构

```
backend/
  app/
    main.py             # FastAPI 入口、路由注册、CORS、静态文件挂载
    config.py           # 路径、端口、环境变量
    db.py               # SQLAlchemy engine / session
    models.py           # ORM 模型（见下表）
    schemas.py          # Pydantic 请求/响应模型
    ai_client.py        # OpenAI SDK 封装、联网搜索、Token 费用计算
    seed.py             # 首次启动 seed 数据（含增量补 seed）
    routers/
      copywrites.py     # CRUD + AI 生成/润色 SSE 端点
      prompts.py        # SystemPrompt CRUD + 设默认
      settings.py       # Provider / Model CRUD + 设默认
      image_sets.py     # 图片集 CRUD + 分镜拆分 + 批量生成 SSE + 单张重生 SSE
      videos.py         # 视频 CRUD + 合成 SSE（4 阶段进度）
      bgms.py           # BGM 上传 / 列表 / 重命名 / 删除
    services/
      storage.py        # 资源路径工具、上传目录初始化
      image_gen.py      # Ollama 分镜拆分 + DashScope 文生图 + URL 下载
      video_synth.py    # CosyVoice TTS + GPU 编码器检测 + 字幕 + moviepy 合成
      sse.py            # SSE 事件推送工具
  run.py                # uvicorn 快捷入口
  data/                 # SQLite + uploads/

frontend/
  src/
    api/
      client.ts         # HTTP 封装 + SSE 流式读取器
      copywrites.ts
      prompts.ts
      settings.ts
      imageSets.ts
      videos.ts
      bgms.ts
      types.ts          # TypeScript 接口定义
      aiUsage.ts        # Token 用量 / 搜索状态格式化
    components/
      Layout.tsx         # 侧边栏导航（分组）+ 主内容区
      Modal.tsx
      Select.tsx
      Spinner.tsx
      Toast.tsx
    pages/
      CopywritesList.tsx
      CopywriteNew.tsx
      CopywriteDetail.tsx
      ImageSetWorkbench.tsx   # 分镜拆分 → 批量生图 → 预览/重生
      VideoSynthesizer.tsx    # 视频参数配置 + 实时进度 + 播放/下载
      BgmLibrary.tsx
      PromptsManager.tsx
      ModelsManager.tsx
    styles/index.css     # Tailwind + 自定义主题
    App.tsx              # 路由 + 页面切换动画
    main.tsx
```

**ORM 表一览**

| 表 | 说明 |
|---|---|
| `copywrites` | 文案主表 |
| `copywrite_versions` | 版本历史（含 Token 消耗字段） |
| `system_prompts` | System Prompt，按 `function_key` 分类 |
| `providers` | API Provider（API Key / Base URL） |
| `models` | 可用模型，按 `purpose` 分类 |
| `bgm_tracks` | BGM 音频文件元数据 |
| `image_sets` | 图片集（生成参数快照 + 状态） |
| `image_set_items` | 单张图片（场景索引、文件路径、状态） |
| `videos` | 视频合成记录（字幕样式、编码器、耗时等） |
