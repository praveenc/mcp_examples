import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path

import nest_asyncio
from anthropic import AnthropicBedrock
from dotenv import load_dotenv
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

nest_asyncio.apply()

# Environment variables will be loaded in main()


class MCPChatBot:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.anthropic = AnthropicBedrock(aws_region="us-west-2")
        self.available_tools: list[dict] = []
        self.available_prompts = []
        self.sessions = {}
        # Get environment variables
        self.model = os.getenv("MODEL")
        self.max_tokens = os.getenv("MAX_TOKENS")
        logger.info(f"Starting chatbot with model: {self.model}")

    async def process_query(self, query):
        messages = [{"role": "user", "content": query}]

        while True:
            response = self.anthropic.messages.create(
                max_tokens=int(self.max_tokens),
                model=self.model,
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
        print("\nMCP US Weather 🌤️ Chatbot Started!")
        print("Type your queries or 'quit' to exit.")

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
    # Load .env file
    load_dotenv(".env")

    # Get environment variables after loading .env
    # model = os.getenv("MODEL")
    # max_tokens = os.getenv("MAX_TOKENS")

    chatbot = MCPChatBot()
    try:
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    finally:
        logger.info("Cleaning up...")
        await chatbot.cleanup()


if __name__ == "__main__":
    # Check if .env file exists
    if not Path(".env").exists():
        logger.info("Please copy .env.example to .env file.")
        logger.error(".env file not found")
        exit(1)

    asyncio.run(main())
