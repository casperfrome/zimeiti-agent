from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import Base, SessionLocal, engine
from .db_migrations import run_startup_migrations
from .routers import bgms, copywrites, image_sets, prompts, settings, videos
from .seed import seed_if_empty
from .services.storage import UPLOAD_ROOT, ensure_upload_dirs


# StaticFiles 在 mount 时校验目录是否存在，必须在 app 构造前就把目录建出来
ensure_upload_dirs()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="短视频文案管理系统", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(copywrites.router, prefix="/api/copywrites", tags=["copywrites"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["prompts"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(image_sets.router, prefix="/api/image-sets", tags=["image_sets"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(bgms.router, prefix="/api/bgms", tags=["bgms"])

# 资源文件挂载：前端通过 /media/{relpath} 直接拉取上传/生成的图片/音视频
app.mount("/media", StaticFiles(directory=str(UPLOAD_ROOT)), name="media")


@app.get("/api/health")
def health():
    return {"status": "ok"}
