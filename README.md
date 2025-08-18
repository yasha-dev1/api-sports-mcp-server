# API-Sports MCP Server

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.0.0-green)](https://github.com/anthropics/mcp)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Tests](https://github.com/yasha-dev1/api-sports-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/yasha-dev1/api-sports-mcp-server/actions)

A Model Context Protocol (MCP) server that provides seamless integration with [API-Sports](https://api-sports.io/) football data API. This server enables AI assistants like Claude to access comprehensive football statistics, fixtures, team information, and more through standardized MCP tools.

## Features

- **Teams Search**: Search and retrieve detailed team information
- **Fixtures Management**: Get match fixtures with comprehensive filtering options
- **Team Statistics**: Access detailed team performance statistics
- **Smart Caching**: Intelligent caching system to optimize API usage
- **Rate Limiting**: Built-in rate limiting to respect API quotas
- **Comprehensive Logging**: Structured logging with loguru for debugging and monitoring
- **Type Safety**: Full type hints with Pydantic models
- **Async Support**: Built on async/await for optimal performance

## Demo
![Claude Sport Api Demo](docs/Claude-Sport-Api-Demo.gif)

## Installation

### Prerequisites

- Python 3.10 or higher
- API-Sports API key (get one at [api-sports.io](https://api-sports.io/))

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yasha-dev1/api-sports-mcp-server.git
cd api-sports-mcp-server

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Running the Server

### Transport Options

The server supports two transport mechanisms:
- **STDIO** (default): For local development and Claude Desktop
- **HTTP/Streamable**: For cloud deployment and easier debugging

### Command Line

#### STDIO Transport (Default)
```bash
# Run as a module
python -m mcp_server_api_sports

# Or use the installed script (after pip install -e .)
mcp-server-api-sports

# Or use the standalone script for development
python run_server.py
```

#### HTTP Transport
```bash
# Using FastMCP (recommended)
mcp-server-api-sports-fastmcp

# Using low-level API
mcp-server-api-sports-http

# Or directly with Python
python -m mcp_server_api_sports.server_fastmcp --http
```

### Docker Deployment

#### Quick Start with Docker Compose

1. **Create `.env` file** with your API key:
```env
API_SPORTS_API_KEY=your_api_key_here
```

2. **Run with Docker Compose**:
```bash
# Development mode (with live code reload)
docker-compose -f docker-compose.dev.yml up

# Production mode
docker-compose up -d

# View logs
docker-compose logs -f api-sports-mcp
```

3. **Access the server**:
- HTTP endpoint: `http://localhost:8080/mcp`
- Health check: `http://localhost:8080/health`

#### Build and Run with Docker

```bash
# Build the image
docker build -t api-sports-mcp-server .

# Run the container
docker run -d \
  -p 8080:8080 \
  -e API_SPORTS_API_KEY=your_api_key \
  --name api-sports-mcp \
  api-sports-mcp-server
```

#### Production Deployment

For production, use the production compose file:
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# This includes:
# - Nginx reverse proxy
# - Resource limits
# - Volume persistence
# - Health checks
```

### IntelliJ IDEA / PyCharm

For IntelliJ IDEA or PyCharm, you have several options:

1. **Run Configuration using run_server.py** (Recommended for debugging):
   - Right-click on `run_server.py` in the project explorer
   - Select "Run 'run_server'"
   - This script handles imports correctly for IDE debugging

2. **Module Run Configuration**:
   - Go to Run → Edit Configurations
   - Add a new Python configuration
   - Set "Module name" to: `mcp_server_api_sports`
   - Set working directory to project root
   - Add environment variable: `API_SPORTS_API_KEY=your_key`

3. **HTTP Server Configuration**:
   - Go to Run → Edit Configurations
   - Add a new Python configuration
   - Set "Module name" to: `mcp_server_api_sports.server_fastmcp`
   - Set "Parameters" to: `--http`
   - Set working directory to project root
   - Add environment variable: `API_SPORTS_API_KEY=your_key`

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your API key:

```env
# Required
API_SPORTS_API_KEY=your_api_key_here

# Optional (defaults shown)
API_SPORTS_BASE_URL=https://v3.football.api-sports.io
LOG_LEVEL=INFO
CACHE_ENABLED=true
RATE_LIMIT_CALLS_PER_MINUTE=30
RATE_LIMIT_CALLS_PER_DAY=100
```

### Claude Desktop Configuration

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "api-sports": {
      "command": "python",
      "args": ["-m", "mcp_server_api_sports.server"],
      "env": {
        "API_SPORTS_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Available Tools

### 1. teams_search

Search for football teams with various filters.

**Parameters:**
- `id` (integer): Team ID
- `name` (string): Team name
- `league` (integer): League ID
- `season` (integer): Season year (YYYY)
- `country` (string): Country name
- `code` (string): 3-letter team code
- `venue` (integer): Venue ID
- `search` (string): Search string (min 3 characters)

**Example Usage:**
```
Search for Manchester United:
- By name: teams_search(name="Manchester United")
- By ID: teams_search(id=33)
- In Premier League 2023: teams_search(league=39, season=2023)
```

### 2. fixtures_get

Retrieve football fixtures (matches) with comprehensive filtering.

**Parameters:**
- `id` (integer): Fixture ID
- `ids` (string): Multiple fixture IDs (delimiter "-")
- `live` (string): "all" or league IDs for live fixtures
- `date` (string): Date in YYYY-MM-DD format
- `league` (integer): League ID
- `season` (integer): Season year (YYYY)
- `team` (integer): Team ID
- `last` (integer): Last N matches (max 99)
- `next` (integer): Next N matches (max 99)
- `from` (string): Start date (YYYY-MM-DD)
- `to` (string): End date (YYYY-MM-DD)
- `round` (string): Round name
- `status` (string): Match status (NS, FT, etc.)
- `venue` (integer): Venue ID
- `timezone` (string): Timezone for dates

**Example Usage:**
```
Get fixtures for a team:
- Next 5 matches: fixtures_get(team=33, next=5)
- On specific date: fixtures_get(date="2024-01-15")
- Live matches: fixtures_get(live="all")
```

### 3. team_statistics

Get comprehensive statistics for a team in a specific league and season.

**Required Parameters:**
- `league` (integer): League ID
- `season` (integer): Season year (YYYY)
- `team` (integer): Team ID

**Optional Parameters:**
- `date` (string): Date for statistics snapshot (YYYY-MM-DD)

**Example Usage:**
```
Get Manchester United's Premier League 2023 stats:
team_statistics(league=39, season=2023, team=33)
```

## Usage Examples

### With Claude Desktop

Once configured, you can ask Claude:

- "Find information about Real Madrid"
- "Show me the next 5 matches for Liverpool"
- "Get Manchester United's statistics for the 2023 Premier League season"
- "What matches are happening today?"
- "Show me Arsenal's recent form"

### Programmatic Usage

```python
import asyncio
from mcp_server_api_sports.services import ApiSportsService, CacheService
from mcp_server_api_sports.tools import TeamsTool, FixturesTool

async def main():
    # Initialize services
    api_service = ApiSportsService()
    cache_service = CacheService()
    
    # Create tools
    teams_tool = TeamsTool(api_service, cache_service)
    
    # Search for a team
    result = await teams_tool.search_teams(name="Barcelona")
    print(result)

asyncio.run(main())
```

## API Response Format

All tools return JSON responses with consistent structure:

```json
{
  "teams": [...],  // or "fixtures", "statistics"
  "count": 10,
  "request_id": "uuid-here"
}
```

Error responses:

```json
{
  "error": "Error message",
  "request_id": "uuid-here"
}
```

## Caching

The server implements intelligent caching to reduce API calls:

- **Teams**: Cached for 24 hours
- **Completed Fixtures**: Cached permanently
- **Upcoming Fixtures**: Cached for 1 hour
- **Statistics**: Cached for 1 hour
- **Live Fixtures**: Not cached

Cache can be disabled by setting `CACHE_ENABLED=false` in your `.env` file.

## Rate Limiting

Built-in rate limiting protects against exceeding API quotas:

- Configurable calls per minute/day
- Automatic retry with exponential backoff
- Queue system for burst requests
- Graceful handling of rate limit errors

## Logging

Comprehensive logging powered by loguru:

- Structured JSON or text format
- Automatic log rotation
- Performance metrics
- Request tracing with IDs
- Separate error log file

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcp_server_api_sports

# Run specific test file
pytest tests/test_tools/test_teams.py
```

### Linting and Type Checking

```bash
# Run linting
ruff check mcp_server_api_sports tests

# Run type checking
mypy mcp_server_api_sports

# Format code
black mcp_server_api_sports tests
isort mcp_server_api_sports tests
```

### Project Structure

```
api-sports-mcp-server/
├── mcp_server_api_sports/
│   ├── __init__.py
│   ├── server.py           # Main MCP server
│   ├── config.py           # Configuration management
│   ├── logger.py           # Loguru logging setup
│   ├── services/
│   │   ├── api_sports_service.py  # API client
│   │   └── cache_service.py       # Caching layer
│   ├── tools/
│   │   ├── teams.py        # Teams tool
│   │   ├── fixtures.py     # Fixtures tool
│   │   └── statistics.py   # Statistics tool
│   └── models/
│       └── api_models.py   # Pydantic models
├── tests/
│   ├── conftest.py         # Test fixtures
│   ├── test_service.py     # Service tests
│   └── test_tools/         # Tool tests
└── pyproject.toml          # Project configuration
```

## Troubleshooting

### Common Issues

1. **API Key Error**: Ensure your API key is correctly set in the environment
2. **Rate Limiting**: Adjust `RATE_LIMIT_CALLS_PER_MINUTE` if hitting limits
3. **Cache Issues**: Clear cache by restarting the server or disable with `CACHE_ENABLED=false`
4. **Connection Errors**: Check your internet connection and API-Sports service status

### Debug Mode

Enable debug logging for more details:

```env
LOG_LEVEL=DEBUG
LOG_FORMAT=text  # Easier to read for debugging
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- [API-Sports](https://api-sports.io/) for providing the football data API
- [Anthropic MCP](https://github.com/anthropics/mcp) for the Model Context Protocol
- [Loguru](https://github.com/Delgan/loguru) for excellent logging capabilities

## Support

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/yasha-dev1/api-sports-mcp-server/issues)
- Check the [API-Sports documentation](https://api-sports.io/documentation/football/v3)
- Review the [MCP documentation](https://github.com/anthropics/mcp)
