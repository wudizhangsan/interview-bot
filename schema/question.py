from pydantic import BaseModel


class QuestionItem(BaseModel):
    question: str
    answer: str


class QuestionList(BaseModel):
    questions: list[QuestionItem]
