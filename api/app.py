"""FastAPI 应用入口"""

import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.kb_routes import router as kb_router
from api.interview_routes import router as interview_router
from tools.file_parser import parse_file


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：确保知识库目录存在
    from api.kb_service import ensure_kb_dir
    ensure_kb_dir()
    yield
    # 关闭时：无需清理


app = FastAPI(
    title="AI Interview Pilot API",
    description="AI 面试助手 — 知识库管理 + 面试流程接口",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS —— 开发阶段允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(kb_router)
app.include_router(interview_router)


@app.get("/")
async def root():
    return {"message": "AI Interview Pilot API", "version": "0.1.0"}


@app.post("/api/parse-file", summary="解析上传的简历文件（PDF/DOCX）")
async def upload_parse(file: UploadFile = File(...)):
    """上传 PDF 或 DOCX 文件，解析后返回纯文本内容"""
    if file.filename is None:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    suffix = {"application/pdf": ".pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"}.get(
        file.content_type or "", ""
    )
    if not suffix:
        # fallback: 从文件名推断
        _, ext = file.filename.rsplit(".", 1)
        suffix = f".{ext.lower()}"

    if suffix not in (".pdf", ".docx"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 DOCX 文件")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = await parse_file(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败: {e}")
    finally:
        import os
        os.unlink(tmp_path)

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件解析后内容为空")

    return {"text": text.strip()}
