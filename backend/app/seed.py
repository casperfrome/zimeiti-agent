from sqlalchemy.orm import Session

from .config import SEED_DEEPSEEK_KEY
from .models import Model, Provider, SystemPrompt

GENERATE_PROMPT = (
    "你是一位擅长抖音、小红书短视频文案的爆款编剧。"
    "根据用户描述生成一条 80-150 字的口播文案，要求："
    "开头 3 秒抓眼球、节奏明快、口语化、结尾带行动召唤。"
    "直接输出文案正文，不要加任何说明或前缀。"
)

POLISH_PROMPT = (
    "你是一位资深短视频文案编辑。"
    "在保持原意和长度大致不变的前提下，把下面这条文案润色得更有节奏感、更口语化、钩子更强。"
    "直接输出润色后的文案正文，不要加任何说明或前缀。"
)

# 来自 backend/tests/wanx_text_to_image_workflow.py 已验证可用的分镜 prompt
IMAGE_PROMPT_SPLIT_PROMPT = """
你是专业短视频分镜和文生图提示词工程师。

任务：
把用户输入的一大段中文文案拆成若干个适合文生图模型生成画面的提示词。

硬性输出要求：
1. 只输出 JSON，不要输出 Markdown、解释、注释、代码块或多余文本。
2. JSON 顶层结构必须是：
   {"prompts":[{"index":1,"prompt":"..."}]}
3. index 从 1 开始递增，必须是整数。
4. prompt 必须是中文，可以包含少量英文摄影术语。
5. 每条 prompt 必须小于等于 750 个中文字符，给图像模型 800 字限制留余量。
6. 每条 prompt 描述一个可直接生成的静态画面，不要写镜头运动、转场、配音或字幕。
7. 每条 prompt 都要包含主体、环境、动作/状态、构图、光线、风格、画幅氛围。
8. 不要生成任何政治、色情、血腥、侵权角色或真实名人相关内容。

风格偏好：
电影感，真实摄影，高细节，情绪清晰，画面干净，适合短视频分镜。
""".strip()


# 文生图模型（DashScope 通义万相），数据来自阿里云官方文档（2026-05 已确认）
IMAGE_MODELS = [
    ("wanx2.0-t2i-turbo",  "通义万相 2.0 Turbo",       True),
    ("wanx2.1-t2i-turbo",  "通义万相 2.1 Turbo",       False),
    ("wanx2.1-t2i-plus",   "通义万相 2.1 Plus",        False),
    ("wan2.2-t2i-flash",   "通义万相 2.2 Flash",       False),
    ("wan2.6-t2i",         "通义万相 2.6",              False),
]

# CosyVoice 模型（DashScope）
TTS_MODELS = [
    ("cosyvoice-v3-flash",   "CosyVoice V3 Flash", True),
    ("cosyvoice-v3-plus",    "CosyVoice V3 Plus",  False),
    ("cosyvoice-v3.5-flash", "CosyVoice V3.5 Flash", False),
    ("cosyvoice-v3.5-plus",  "CosyVoice V3.5 Plus",  False),
    ("cosyvoice-v2",         "CosyVoice V2",       False),
]


def seed_if_empty(db: Session) -> None:
    if db.query(Provider).count() == 0:
        db.add_all([
            Provider(
                provider_key="deepseek",
                display_name="DeepSeek",
                api_key=SEED_DEEPSEEK_KEY,
                base_url="https://api.deepseek.com/v1",
            ),
            Provider(
                provider_key="kimi",
                display_name="Kimi (Moonshot)",
                api_key="",
                base_url="https://api.moonshot.cn/v1",
            ),
        ])
        db.commit()

    # 增量补 alibaba / ollama，幂等
    if db.get(Provider, "alibaba") is None:
        db.add(Provider(
            provider_key="alibaba",
            display_name="阿里云百炼 DashScope",
            api_key="",
            base_url="https://dashscope.aliyuncs.com",
        ))
        db.commit()
    if db.get(Provider, "ollama") is None:
        db.add(Provider(
            provider_key="ollama",
            display_name="本地 Ollama",
            api_key="",
            base_url="http://127.0.0.1:11434",
        ))
        db.commit()

    if db.query(Model).count() == 0:
        db.add_all([
            Model(provider_key="deepseek", model_id="deepseek-v4-flash",
                  display_name="DeepSeek V4 Flash", purpose="chat", is_default=True),
            Model(provider_key="deepseek", model_id="deepseek-v4-pro",
                  display_name="DeepSeek V4 Pro", purpose="chat", is_default=False),
            Model(provider_key="kimi", model_id="kimi-k2-0711-preview",
                  display_name="Kimi K2 Preview", purpose="chat", is_default=False),
            Model(provider_key="kimi", model_id="moonshot-v1-32k",
                  display_name="Moonshot V1 32k", purpose="chat", is_default=False),
            Model(provider_key="kimi", model_id="moonshot-v1-128k",
                  display_name="Moonshot V1 128k", purpose="chat", is_default=False),
        ])
        db.commit()

    # 增量补 image / tts / prompt_split 模型，幂等
    existing_image = {
        m.model_id for m in db.query(Model).filter(Model.purpose == "image").all()
    }
    for model_id, display_name, is_default in IMAGE_MODELS:
        if model_id not in existing_image:
            db.add(Model(
                provider_key="alibaba",
                model_id=model_id,
                display_name=display_name,
                purpose="image",
                is_default=is_default,
            ))
    db.commit()

    existing_tts = {
        m.model_id for m in db.query(Model).filter(Model.purpose == "tts").all()
    }
    for model_id, display_name, is_default in TTS_MODELS:
        if model_id not in existing_tts:
            db.add(Model(
                provider_key="alibaba",
                model_id=model_id,
                display_name=display_name,
                purpose="tts",
                is_default=is_default,
            ))
    db.commit()

    if db.query(Model).filter(Model.purpose == "prompt_split").count() == 0:
        db.add(Model(
            provider_key="ollama",
            model_id="qwen3:8b",
            display_name="Qwen3 8B (Ollama)",
            purpose="prompt_split",
            is_default=True,
        ))
        db.commit()

    if db.query(SystemPrompt).count() == 0:
        db.add_all([
            SystemPrompt(
                function_key="copywrite_generate",
                name="默认 · 爆款口播",
                content=GENERATE_PROMPT,
                is_default=True,
            ),
            SystemPrompt(
                function_key="copywrite_polish",
                name="默认 · 节奏润色",
                content=POLISH_PROMPT,
                is_default=True,
            ),
        ])
        db.commit()

    # 增量补 image_prompt_split prompt
    if db.query(SystemPrompt).filter(
        SystemPrompt.function_key == "image_prompt_split"
    ).count() == 0:
        db.add(SystemPrompt(
            function_key="image_prompt_split",
            name="默认 · 文生图分镜",
            content=IMAGE_PROMPT_SPLIT_PROMPT,
            is_default=True,
        ))
        db.commit()
