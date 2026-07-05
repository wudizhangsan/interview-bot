"""知识库管理路由"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.kb_service import (
    KBGenerator,
    delete_kb,
    list_topics,
    load_kb,
    save_kb,
    validate_topic_name,
)
from schema.question import QuestionItem
from tools.file_parser import parse_file

router = APIRouter(prefix="/api/kb", tags=["知识库管理"])
kb_generator = KBGenerator()


@router.get("/topics", summary="列出所有知识点及其题目数量")
async def get_topics():
    """返回 {topic_name: question_count, ...}"""
    return list_topics()


@router.get("/topics/{topic_name}", summary="获取某个知识点的所有题目")
async def get_topic(topic_name: str):
    if not validate_topic_name(topic_name):
        raise HTTPException(status_code=400, detail="知识点名称包含非法字符")

    try:
        data = load_kb(topic_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"知识点 '{topic_name}' 不存在")

    return {"topic": topic_name, "questions": data}


@router.post("/topics", summary="创建知识点：上传 PDF/text → 生成 Q&A → 保存")
async def create_topic(
    topic_name: str = Form(...),
    text: str = Form(default=""),
    file: UploadFile = File(default=None),
):
    if not validate_topic_name(topic_name):
        raise HTTPException(
            status_code=400,
            detail="知识点名称只允许中文、字母、数字、下划线和短横线",
        )

    # 从 text 或上传文件中提取内容
    content = text.strip()
    if file and file.filename:
        try:
            suffix = Path(file.filename).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            parsed = await parse_file(tmp_path)
            content = parsed.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}")
        finally:
            if "tmp_path" in locals():
                import os
                os.unlink(tmp_path)

    if not content:
        raise HTTPException(status_code=400, detail="请提供文本内容或上传文件")

    # 生成 Q&A
    try:
        questions: list[QuestionItem] = await kb_generator.generate(topic_name, content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成题目失败: {e}")

    if not questions:
        raise HTTPException(status_code=500, detail="生成题目失败，结果为空")

    # 保存到 assert/kb/
    save_kb(topic_name, questions)

    return {
        "topic": topic_name,
        "question_count": len(questions),
        "questions": [
            {"question": q.question, "answer": q.answer} for q in questions
        ],
    }


@router.delete("/topics/{topic_name}", summary="删除知识点")
async def remove_topic(topic_name: str):
    if not validate_topic_name(topic_name):
        raise HTTPException(status_code=400, detail="知识点名称包含非法字符")

    if not delete_kb(topic_name):
        raise HTTPException(status_code=404, detail=f"知识点 '{topic_name}' 不存在")

    return {"message": f"知识点 '{topic_name}' 已删除"}
