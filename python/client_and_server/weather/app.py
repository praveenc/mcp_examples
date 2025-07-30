import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import nest_asyncio
import streamlit as st
from anthropic import AnthropicBedrock
from dotenv import load_dotenv
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

nest_asyncio.apply()
load_dotenv(".env")

MODEL = os.getenv("MODEL")
MAX_TOKENS = os.getenv("MAX_TOKENS")


class StreamlitMCPClient:
    """Streamlit-compatible MCP client with proper async context management."""

    def __init__(self):
        self.anthropic = AnthropicBedrock(aws_region="us-west-2")
        self.available_tools: list[dict[str, Any]] = []
        self.server_configs: dict[str, Any] = {}

    async def initialize_tools(self) -> None:
        """Initialize tool definitions using proper async context management."""
        try:
            config_path = Path("server_config.json")
            if not config_path.exists():
                st.error("server_config.json not found")
                return

            with Path.open("server_config.json") as file:
                data = json.load(file)

            servers = data.get("mcpServers", {})
            self.server_configs = servers

            # Get tool definitions using proper context management
            for server_name, server_config in servers.items():
                async with AsyncExitStack() as stack:
                    # Create server parameters
                    server_params = StdioServerParameters(**server_config)

                    # Create stdio transport using context manager
                    stdio_transport = await stack.enter_async_context(
                        stdio_client(server_params),
                    )
                    read, write = stdio_transport

                    # Create session using context manager
                    session = await stack.enter_async_context(
                        ClientSession(read, write),
                    )

                    # Initialize session
                    await session.initialize()

                    # Get tools
                    response = await session.list_tools()
                    for tool in response.tools:
                        self.available_tools.append(
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "input_schema": tool.inputSchema,
                            },
                        )

                    st.success(f"Loaded {len(response.tools)} tools from {server_name} MCP server.")
                # Context stack automatically cleans up when exiting

        except Exception as e:
            logger.error(f"Error initializing tools: {e}")
            st.error(f"Error initializing tools: {e}")
            raise

    async def process_query(self, query: str) -> str:
        """Process query with proper connection management for each tool call."""
        messages = [{"role": "user", "content": query}]
        response_text = ""

        try:
            while True:
                logger.info("Sending request to Anthropic...")
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
                        logger.info(f"Text content: {content.text}")
                        response_text += content.text + "\n\n"
                        assistant_content.append(content)

                    elif content.type == "tool_use":
                        logger.info(f"Tool use: {content.name} with {content.input}")
                        has_tool_use = True
                        assistant_content.append(content)

                        # Add assistant message before tool call
                        messages.append(
                            {"role": "assistant", "content": assistant_content},
                        )

                        # Execute tool with proper connection management
                        tool_result = await self._execute_tool(
                            content.name, content.input,
                        )

                        if tool_result["success"]:
                            response_text += (
                                f"🔧 **{content.name}**: {tool_result['content']}\n\n"
                            )

                            # Add tool result to messages
                            messages.append(
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": content.id,
                                            "content": tool_result["content"],
                                        },
                                    ],
                                },
                            )
                        else:
                            return f"{response_text}\n\n❌ {tool_result['error']}"

                # Exit if no tools were used
                if not has_tool_use:
                    logger.info("No tool use, exiting loop")
                    break
                logger.info("Tool used, continuing conversation loop")

            return (
                response_text.strip()
                if response_text.strip()
                else "No response generated."
            )

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return f"Error processing query: {e}"

    async def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call with proper async context management."""
        try:
            # Try each configured server to find the tool
            for server_name, server_config in self.server_configs.items():
                async with AsyncExitStack() as stack:
                    try:
                        # Create server parameters
                        server_params = StdioServerParameters(**server_config)

                        # Create stdio transport
                        stdio_transport = await stack.enter_async_context(
                            stdio_client(server_params),
                        )
                        read, write = stdio_transport

                        # Create session
                        session = await stack.enter_async_context(
                            ClientSession(read, write),
                        )

                        # Initialize session
                        await session.initialize()

                        # Check if this server has the tool
                        tools_response = await session.list_tools()
                        available_tool_names = [
                            tool.name for tool in tools_response.tools
                        ]

                        if tool_name in available_tool_names:
                            logger.info(
                                f"Found tool {tool_name} on server {server_name}",
                            )

                            # Execute the tool
                            result = await session.call_tool(
                                tool_name, arguments=arguments,
                            )
                            logger.info(f"Tool {tool_name} executed successfully")

                            return {"success": True, "content": result.content}

                    except Exception as server_error:
                        logger.error(f"Error with server {server_name}: {server_error}")
                        continue  # Try next server

                # Context automatically cleaned up here

            # If we get here, tool wasn't found on any server
            return {  # noqa: TRY300
                "success": False,
                "error": f"Tool '{tool_name}' not found on any server",
            }

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": f"Tool execution error: {e}"}


# Streamlit App
st.set_page_config(
    page_title="Weather Chatbot",
    page_icon="🌤️",
    layout="wide",
)

st.title("🌤️ US Weather Chatbot 🇺🇸")
st.caption("Ask me about weather alerts and forecasts for any location in the US!")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "mcp_client" not in st.session_state:
    st.session_state.mcp_client = None
    st.session_state.client_initialized = False

# Initialize MCP client only once
if not st.session_state.client_initialized:
    with st.spinner("Connecting to weather services..."):
        try:
            client = StreamlitMCPClient()

            # Run initialization in a separate event loop context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(client.initialize_tools())
            finally:
                loop.close()

            st.session_state.mcp_client = client
            st.session_state.client_initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            st.error(f"Failed to initialize MCP client: {e}")
            st.stop()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("Ask about weather alerts or forecasts..."):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})

    # Process query
    if st.session_state.mcp_client and st.session_state.client_initialized:
        with st.chat_message("assistant"), st.spinner("Processing..."):
            try:
                # Use a fresh event loop for each query
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    response = loop.run_until_complete(
                        st.session_state.mcp_client.process_query(prompt),
                    )
                finally:
                    loop.close()

                st.markdown(response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response},
                )

            except Exception as e:
                error_msg = f"Error: {e}"
                logger.error(f"Query processing error: {e}")
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg},
                )
    else:
        st.error("MCP client not available. Please refresh the page.")

# Sidebar
with st.sidebar:
    st.header("💡 Usage Examples")
    st.markdown("""
    **Weather Alerts:**
    - "Weather alerts in California?"
    - "Show alerts for TX"

    **Forecasts:**
    - "Forecast for San Francisco?"
    - "Weather at 40.7128, -74.0060"

    **Coordinates:**
    - "Get me latitude and longitude for San Francisco?"
    - "Get me latitude and longitude for New York City?"
    """)

    st.divider()

    st.header("🔧 MCP Servers")
    if st.session_state.client_initialized and st.session_state.mcp_client:
        # st.success("✅ Connected to MCP server")
        if st.session_state.mcp_client.server_configs:
            for server_name in st.session_state.mcp_client.server_configs:
                st.markdown(f"### {server_name} ✅ Connected")

            # Show available tools in an expander
            if st.session_state.mcp_client.available_tools:
                with st.expander("Available Weather Tools", expanded=False):
                    for tool in st.session_state.mcp_client.available_tools:
                        st.markdown(f"**{tool['name']}**: {tool['description']}")
        else:
            st.markdown("No MCP servers configured")
    else:
        st.markdown("MCP client not initialized")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()
