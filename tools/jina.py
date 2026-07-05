import re
from typing import List, Optional

import requests
import traceback
import asyncio
from schema.system_config import load_system_config
from schema.url import SearchResult
config = load_system_config("config/system_config.json")


async def search_keyword(keywords: List[str]) -> List[SearchResult]:
    try:
        url = "https://s.jina.ai/?q=" + "+".join(keywords)
        headers = {
            "Authorization": "Bearer " + config.jina_key,
            "X-Respond-With": "no-content"
        }

        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'  # 强制设置编码为 UTF-8
        results_list = []
        blocks = response.text.split("\n\n")

        for block in blocks:
            if not block.strip():
                continue

            title_match = re.search(r'Title:\s*(.*)', block)
            url_match = re.search(r'URL Source:\s*(.*)', block)
            desc_match = re.search(r'Description:\s*(.*)', block)

            if title_match and url_match and desc_match:
                results_list.append(
                    SearchResult(
                        title=title_match.group(1).strip(),
                        url=url_match.group(1).strip(),
                        description=desc_match.group(1).strip()
                    )
                )

        return results_list
    except Exception as e:
        traceback.print_exc()
        return []

async def fetch_url(url: str) -> str:
    try:
        url = "https://r.jina.ai/" + url
        headers = {
            "Authorization": "Bearer " + config.jina_key
        }

        response = requests.get(url, headers=headers)
        return response.text
    except Exception as e:
        traceback.print_exc()
        return ""

if __name__ == "__main__":
    # print(asyncio.run(fetch_url("https://jina.ai/")))

    result = asyncio.run(search_keyword(["大模型应用开发", "工作"]))
    for x in result:
        print(x)