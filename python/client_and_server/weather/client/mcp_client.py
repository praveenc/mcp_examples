import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path

import nest_asyncio
from anthropic import AnthropicBedrock
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

nest_asyncio.apply()

load_dotenv(".env")

MODEL = os.getenv("MODEL")
MAX_TOKENS = os.getenv("MAX_TOKENS")


class MCPChatBot:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.anthropic = AnthropicBedrock(aws_region="us-west-2")
        self.available_tools: list[dict] = []
        self.available_prompts = []
        self.sessions = {}

    async def process_query(self, query):
        messages = [{"role": "user", "content": query}]

        while True:
            response = self.anthropic.messages.create(
                max_tokens=int(MAX_TOKENS),
                model=MODEL,
                tools=self.available_tools,
                messages=messages,
            )
            assistant_content = []
            has_tool_use = False

            for content in response.content:
                if content.type == "text":
                    print(content.text)
                    assistant_content.append(content)
                elif content.type == "tool_use":
                    has_tool_use = True
                    assistant_content.append(content)
                    messages.append({"role": "assistant", "content": assistant_content})

                    # Get session and call tool
                    session = self.sessions.get(content.name)
                    if not session:
                        print(f"Tool '{content.name}' not found.")
                        break

                    result = await session.call_tool(
                        content.name,
                        arguments=content.input,
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": content.id,
                                    "content": result.content,
                                },
                            ],
                        },
                    )

            # Exit loop if no tool was used
            if not has_tool_use:
                break

    async def chat_loop(self):
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        # print("Use @folders to see available topics")
        # print("Use @<topic> to search papers in that topic")
        # print("Use /prompts to list available prompts")
        # print("Use /prompt <name> <arg1=value1> to execute a prompt")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if not query:
                    continue

                if query.lower() == "quit":
                    break

                await self.process_query(query)

            except Exception as e:
                print(f"\nError: {e!s}")

    async def cleanup(self):
        await self.exit_stack.aclose()

    async def connect_to_server(self, server_name, server_config):
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params),
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write),
            )
            await session.initialize()

            try:
                # List available tools
                response = await session.list_tools()
                for tool in response.tools:
                    self.sessions[tool.name] = session
                    self.available_tools.append(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema,
                        },
                    )

            except Exception as e:
                print(f"Error {e}")

        except Exception as e:
            print(f"Error connecting to {server_name}: {e}")

    async def connect_to_servers(self):
        try:
            with Path.open("server_config.json") as file:
                data = json.load(file)
            servers = data.get("mcpServers", {})
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server config: {e}")
            raise


async def main():
    chatbot = MCPChatBot()
    try:
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
