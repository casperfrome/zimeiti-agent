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

    if db.query(Model).count() == 0:
        db.add_all([
            Model(provider_key="deepseek", model_id="deepseek-v4-flash",
                  display_name="DeepSeek V4 Flash", is_default=True),
            Model(provider_key="deepseek", model_id="deepseek-v4-pro",
                  display_name="DeepSeek V4 Pro", is_default=False),
            Model(provider_key="kimi", model_id="kimi-k2-0711-preview",
                  display_name="Kimi K2 Preview", is_default=False),
            Model(provider_key="kimi", model_id="moonshot-v1-32k",
                  display_name="Moonshot V1 32k", is_default=False),
            Model(provider_key="kimi", model_id="moonshot-v1-128k",
                  display_name="Moonshot V1 128k", is_default=False),
        ])
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
