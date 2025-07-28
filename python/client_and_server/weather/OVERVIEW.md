# Weather MCP Example – Project Overview

This repository demonstrates a **minimal yet complete** Model-Context-Protocol (MCP) setup comprising:

1. **An MCP server** exposing two weather-related *tools* (`get_alerts`, `get_forecast`).
2. **An MCP client / chatbot** that dynamically discovers those tools and calls them through Anthropic’s function-calling interface.

Everything is wired through the **stdio transport**, so no network sockets are required – the client spawns the server as a subprocess and exchanges JSON-RPC messages over STDIN/STDOUT.

---
## 1. Directory structure

```text
python/weather/
│
├── client/                # Stand-alone CLI chatbot
│   ├── .env               # Model + token limits
│   ├── mcp_client.py      # Main client implementation
│   ├── __init__.py
│   └── server_config.json # Configuration for MCP servers
│
├── server/                # MCP server implementation
│   ├── __init__.py
│   ├── weather_server.py  # FastMCP server + tool definitions
│   └── utils/
│       └── weather_utils.py  # Shared async helpers
│
├── pyproject.toml         # Poetry-style metadata + deps (uses `uv` under the hood)
├── README.md              # High-level project read-me
└── OVERVIEW.md            # ← **this file**
```

---
## 2. MCP *tool* lifecycle

| Phase | Server (FastMCP) | Client | Notes |
|-------|------------------|--------|-------|
| **Registration** | Decorate an `async def` with `@mcp.tool` → FastMCP introspects the signature & docstring. | After `session.initialize()` the client calls `session.list_tools()` to fetch metadata. | Tool input schema is auto-derived from the type-hints. |
| **Invocation** | FastMCP waits for a `tool.invoke` JSON-RPC request. | Anthropic replies with a `tool_use` block; the client maps `tool.name` to the correct session and calls `session.call_tool(...)`. | Both requests / responses are *async*; httpx is used under the hood for I/O. |
| **Result** | Returns `str` (or any serialisable JSON) to the client. | The client forwards the result back to Anthropic via a `tool_result` message so the model can continue chatting. | |

---
## 3. Server internals (`server/weather_server.py`)

```mermaid
flowchart TD
    subgraph Server Process
        A[FastMCP("Weather")] --> B[get_alerts]
        A --> C[get_forecast]
    end
```

### 3.1 Constants
* `NWS_API_BASE` – base URL for the US National Weather Service API. All requests are built on top of this path.

### 3.2 `get_alerts(state: str) -> str`
* Builds the URL `/alerts/active/area/{state}`.
* Delegates HTTP call to `utils.get_weather_data`.
* Each GeoJSON *feature* is formatted via `utils.format_alert` and concatenated.

### 3.3 `get_forecast(latitude: float, longitude: float) -> str`
* First hits `/points/{lat},{lon}` to resolve the *forecast* URL.
* Second request fetches the 7-day / 12-hour period forecast.
* Only the **next 5 periods** are returned to keep responses concise.

### 3.4 Bootstrapping

```python
if __name__ == "__main__":
    mcp.run(transport="stdio")  # blocks forever
```

Running with `transport="stdio"` makes the file perfectly suited for spawning by another process (our client). No additional CLI wrapper is required.

---
## 4. Shared utilities (`server/utils/weather_utils.py`)

| Helper | Purpose |
|--------|---------|
| `async get_weather_data(url)` | Thin wrapper around **httpx.AsyncClient** with logging, timeout, error handling, and proper *User-Agent* header. |
| `format_alert(feature)` | Extracts `event`, `areaDesc`, `severity`, `description`, and `instruction` into a human-readable multi-line string. |

Both helpers are synchronous-safe: server code awaits them inside each tool.

---
## 5. Client internals (`client/mcp_client.py`)

### 5.1 `MCPChatBot.__init__`
* Creates an `AsyncExitStack` to manage all async contexts.
* Configures **AnthropicBedrock** (AWS region `us-west-2`).
* Pre-allocates: `available_tools`, `sessions` (tool→ClientSession).

### 5.2 Server discovery
* `connect_to_servers()` opens `server_config.json`. Each entry is a *StdioServerParameters* dict with the **command** to launch.
* For each server:
  1. `stdio_client()` spawns the process.
  2. A `ClientSession` is initialised.
  3. `list_tools()` response is cached so subsequent queries need no extra RTT.

### 5.3 Chat loop
* Reads user input → `Anthropic.messages.create()` with the aggregated `tools` list.
* Handles streamed `content` blocks. When a `tool_use` block appears it **synchronously calls** the remote tool and sends the `tool_result`.
* Continues until the assistant no longer issues tool calls.

### 5.4 Environment & limits
`.env` provides two vars consumed on import time:
* `MODEL` – e.g. `anthropic.claude-3-sonnet-20240229-v1:0`.
* `MAX_TOKENS` – max output tokens per Anthropic call.

---
## 6. How to run locally

```bash
# 1️⃣  Install UV and create virtual environment
pip install uv
uv venv
# Activate virtual environment
source .venv/bin/activate

# 2️⃣  Export required env vars
cp client/.env.example client/.env  # or edit manually

# 3️⃣  Start the chatbot – it will auto-spawn the server via stdio
uv run client/mcp_client.py
```

*You can also spawn the server manually for debugging:* `uv run server/weather_server.py` (then interact with it using `mcp` CLI).

---
## 7. Extending the example

1. **Add a new tool**
   * Define `async def your_tool(...)` in `weather_server.py`.
   * Decorate with `@mcp.tool(name=..., description=...)`.
2. **Client picks it up automatically** on next run – no code change required.
3. For non-stdio transport (WebSocket, HTTP/2, etc.) replace `mcp.run(transport="stdio")` accordingly and update `server_config.json`.

---
## 8. Key takeaways

* **Tools are first-class citizens**: the only API surface exposed by the server.
* **Type-hints ⇨ JSON schema**: FastMCP auto-generates the `input_schema` sent to LLMs.
* **Async all the way down** ensures the server remains responsive even with slow upstream APIs.
* The architecture is **LLM-agnostic** – swap Anthropic for OpenAI, Gemini, etc. by replacing the `anthropic` block.
