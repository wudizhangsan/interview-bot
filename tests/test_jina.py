from schema.system_config import load_system_config
from tools.jina import fetch_url, search_keyword

config = load_system_config("config/system_config.json")

async def test_fetch_url():
    assert "Jina" in await fetch_url("https://jina.ai/")

async def test_search_keyword():
    assert len(await search_keyword(["jina", "openai"])) > 0
    assert isinstance(await search_keyword(["jina", "openai"]), list)