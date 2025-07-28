# 🌤️ Weather MCP Server & Client 🇺🇸

A Model Context Protocol (MCP) implementation for US weather data, featuring both a command-line interface and a modern Streamlit web application. This project demonstrates how to build MCP servers and clients that provide weather alerts, forecasts, and geocoding services using the National Weather Service API.

## 🚀 Features

### Weather MCP Server

- **Weather Alerts**: Get active weather alerts for any US state
- **Weather Forecasts**: Retrieve detailed forecasts for specific coordinates
- **Geocoding**: Convert city names to latitude/longitude coordinates
- **Async Support**: Built with FastMCP for high-performance async operations
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

### Client Applications

- **CLI Client**: Interactive command-line weather chatbot
- **Streamlit Web App**: Modern web interface with chat functionality
- **AI-Powered**: Uses Anthropic's Claude for natural language understanding
- **Tool Chaining**: Automatically chains geocoding → forecast requests

## 📋 Prerequisites

- **Python 3.12+** (required)
- **uv** package manager ([astral.sh/uv](https://astral.sh/uv))
- **AWS credentials** configured for Anthropic Bedrock access
- **Internet connection** for weather data and geocoding

## 🛠️ Installation

### 1. Clone and Navigate to weather

```bash
git clone https://github.com/praveenc/mcp_examples.git
cd mcp_examples/python/client_and_server/weather
```

### 2. Install uv Package Manager

**Install uv package manager**

```bash
pip install uv
```

### 3. Create and Activate Virtual Environment

```bash
# Create virtual environment
cd mcp_examples/python/client_and_server/weather
uv venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
# .venv\Scripts\activate
```

### 4. Install Dependencies

```bash
uv sync
```

### 5. Configure Environment

The project includes a [`.env.example`](client/.env.example) file in the [`client/`](client/) directory with default settings:

```bash
# copy .env.example to .env
cd client
mv .env.example .env
```

**Optional:** You can modify the model or token limits in [`client/.env`](client/.env) if needed.

```text
# client/.env
MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
MAX_TOKENS=4096
```

### 6. Configure AWS Credentials

Ensure AWS credentials are configured for Anthropic Bedrock:

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2
```

### 7. Update Server Configuration

Edit [`client/server_config.json`](client/server_config.json) to match your installation path:
```json
{
    "mcpServers": {
        "weather": {
            "command": "uv",
            "args": [
                "--directory",
                "/your/absolute/path/to/weather/server",
                "run",
                "weather_server.py"
            ]
        }
    }
}
```

**Note:** You can add more MCP servers by adding them to [`client/server_config.json`](client/server_config.json). Each server needs a unique name and appropriate command/args configuration.

## 🚀 Usage

### Option 1: Streamlit Web Application (Recommended)

The Streamlit app acts as an MCP client, connecting to the weather MCP server to provide a modern chat interface.

1. **Start the Streamlit app:**
   ```bash
   cd client
   uv run streamlit run app.py
   ```

2. **Open your browser** to `http://localhost:8501`

3. **Try these example queries:**
   - "What are the weather alerts in California?"
   - "Show me the forecast for San Francisco"
   - "Get me latitude and longitude for New York City"
   - "Weather forecast for 40.7128, -74.0060"

### Option 2: Command Line Interface

The CLI client is another MCP client that provides an interactive command-line interface.

1. **Start the MCP CLI client:**
   ```bash
   cd client
   uv run mcp_client.py
   ```

2. **Interactive chat:** Type your weather questions and press Enter

3. **Exit:** Type 'quit', 'exit', or press Ctrl+C

### Option 3: Direct Server Testing

**Test the MCP server directly:**
```bash
cd server
uv run weather_server.py
```

## 🔧 Available Tools

The weather MCP server provides three main tools:

### 1. `get_alerts`
**Description:** Get active weather alerts for a US state
**Parameters:**
- `state` (string): Two-letter state code (e.g., "CA", "TX", "FL")

**Example:**
```
"Show me weather alerts for California"
→ Uses get_alerts with state="CA"
```

### 2. `get_forecast`
**Description:** Get weather forecast for specific coordinates
**Parameters:**
- `latitude` (float): Latitude coordinate
- `longitude` (float): Longitude coordinate

**Example:**
```
"Weather forecast for 37.7749, -122.4194"
→ Uses get_forecast with lat=37.7749, lon=-122.4194
```

### 3. `get_lat_long`
**Description:** Convert city names to coordinates
**Parameters:**
- `place` (string): US city name (e.g., "San Francisco", "New York")

**Example:**
```
"Get coordinates for Seattle"
→ Uses get_lat_long with place="Seattle"
```

## 🔄 Tool Chaining

The AI automatically chains tools for complex requests:

```
User: "What's the forecast for San Francisco?"

1. get_lat_long("San Francisco") → 37.7749, -122.4194
2. get_forecast(37.7749, -122.4194) → Detailed forecast
```

## 📁 Project Structure

```
weather/
├── README.md                 # This file
├── OVERVIEW.md              # Technical overview
├── pyproject.toml           # Dependencies and project config
├── uv.lock                  # Locked dependencies
├── .env                     # Environment variables (create this)
│
├── server/                  # MCP Server
│   ├── __init__.py
│   ├── weather_server.py    # Main server implementation
│   └── weather_server.log   # Server logs
│
└── client/                  # MCP Clients
    ├── __init__.py
    ├── app.py              # Streamlit web application
    ├── mcp_client.py       # CLI client
    └── server_config.json  # MCP server configuration
```

## 🐛 Troubleshooting

### Common Issues

**1. "MCP client not initialized"**
- Check that `server_config.json` has the correct absolute path
- Ensure uv is installed and in PATH
- Verify the server directory exists

**2. "AWS credentials not found"**
- Configure AWS credentials for Bedrock access
- Check AWS region is set to us-west-2 or supported region
- Verify IAM permissions for Bedrock

**3. "Geocoding request timed out"**
- Check internet connection
- The geocode.xyz API may be temporarily unavailable
- Try with different city names

**4. "Tool not found on any server"**
- Restart the Streamlit app
- Check server logs in `server/weather_server.log`
- Verify server is running properly

### Debug Mode

**Enable detailed logging:**
```bash
# Check server logs
tail -f server/weather_server.log

# Run with debug output
STREAMLIT_LOGGER_LEVEL=debug streamlit run client/app.py
```

## 🔒 Security Notes

- **API Keys**: Never commit `.env` files to version control
- **AWS Credentials**: Use IAM roles when possible
- **Network**: The server makes requests to external APIs (weather.gov, geocode.xyz)
- **Logging**: Sensitive data is not logged, but check logs before sharing

## 🌐 Data Sources

- **Weather Data**: [National Weather Service API](https://api.weather.gov)
- **Geocoding**: [geocode.xyz](https://geocode.xyz)
- **AI Processing**: Anthropic Claude via AWS Bedrock

## 📝 Example Queries

### Weather Alerts
```
"Are there any weather alerts in Texas?"
"Show me active alerts for FL"
"Weather warnings in California?"
```

### Weather Forecasts
```
"What's the forecast for San Francisco?"
"Weather forecast for 40.7128, -74.0060"
"Tell me the weather for Seattle"
```

### Geocoding
```
"Get me coordinates for New York City"
"What's the latitude and longitude of Miami?"
"Find coordinates for Denver, Colorado"
```

### Complex Queries
```
"What's the weather like in Los Angeles and are there any alerts for California?"
"Give me the forecast for Chicago and show any alerts for Illinois"
```

## 🤝 Contributing

This is an example MCP implementation. Feel free to:
- Add more weather data sources
- Implement additional tools (radar, historical data)
- Improve error handling and user experience
- Add more sophisticated geocoding

## 📄 License

See the main MCP repository for license information.

---

**Happy weather tracking! 🌤️**