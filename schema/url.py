import pandas as pd
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str = Field(..., description="搜索结果标题")
    url: str = Field(..., description="搜索结果链接")
    description: str = Field(..., description="搜索结果描述")


if __name__ == "__main__":
    urls = [
        SearchResult(title="1", url="1", description="1"),
        SearchResult(title="2", url="1", description="1"),
        SearchResult(title="3", url="1", description="1"),
    ]
    df = pd.DataFrame([x.model_dump() for x in urls])
    print(df)
