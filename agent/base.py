import asyncio
import uuid

from agents import set_default_openai_api, set_tracing_disabled
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, SQLiteSession

from schema.system_config import load_system_config

set_default_openai_api("chat_completions")
set_tracing_disabled(True)

config = load_system_config("config/system_config.json")


class BaseAgent:
    def __init__(self):
        self.agent = Agent(
            name="",
            model=config.default_model,
            instructions="你好",
        )

        self.session = SQLiteSession(str(uuid.uuid4()))

    async def run(self, input: str):
        result = await Runner.run(self.agent, input, session=self.session)
        return result.final_output

    async def run_streamed(self, input: str):
        result = Runner.run_streamed(self.agent, input, session=self.session)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                yield event.data.delta


async def main():
    agent = BaseAgent()

    result = await agent.run("你好")
    print(result)

    async for chunk in agent.run_streamed("我的上一句是什么？"):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    asyncio.run(main())