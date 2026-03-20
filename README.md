# Reddit + VADER Sentiment Analysis Integration MCP Server

This is an MCP (Model Context Protocol) server that combines Reddit API integration (PRAW) with VADER sentiment analysis to provide comprehensive sentiment monitoring of Reddit discussions. It uses D402 payment protocol for secure access control.

## Features

- 🔧 **MCP Protocol**: Built on the Model Context Protocol for seamless AI integration
- 📊 **Reddit Integration**: Uses PRAW (Python Reddit API Wrapper) for fetching posts and comments
- 💭 **VADER Sentiment**: Specialized sentiment analysis for social media text
- 💳 **D402 Payment Protocol**: Uses HTTP 402 payment protocol for secure access
- 🔍 **Advanced Search**: Keyword filtering and subreddit search capabilities
- 📈 **Comprehensive Metrics**: Detailed sentiment distribution and statistics
- 🐳 **Docker Support**: Easy deployment with Docker and Docker Compose
- ⚡ **Async Operations**: Built with FastMCP for efficient async handling
- 🎯 **Production Ready**: Optimized for production environments

## Available Tools

This server provides the following tools for Reddit sentiment analysis:

### 1. `analyze_subreddit_sentiment`
Analyze sentiment of posts in a subreddit with optional keyword filtering.

**Parameters:**
- `subreddit_name` (string): Name of the subreddit (without r/)
- `keywords` (string, optional): Comma-separated keywords to filter posts
- `limit` (integer): Maximum number of posts to analyze (max 100, default: 25)
- `time_filter` (string): Time filter (hour, day, week, month, year, all, default: day)
- `sort_by` (string): Sort method (hot, new, top, rising, default: hot)

**Returns:**
- Posts with sentiment analysis and overall sentiment metrics

**Payment:** 0.00002 tokens per request

### 2. `search_and_analyze_reddit_sentiment`
Search for posts in a subreddit using keywords and analyze their sentiment.

**Parameters:**
- `subreddit_name` (string): Name of the subreddit (without r/)
- `query` (string): Search query/keywords
- `limit` (integer): Maximum number of posts to analyze (max 100, default: 25)
- `time_filter` (string): Time filter (hour, day, week, month, year, all, default: month)
- `sort_by` (string): Sort method (relevance, hot, top, new, comments, default: relevance)

**Returns:**
- Search results with sentiment analysis

**Payment:** 0.00002 tokens per request

### 3. `analyze_post_comments_sentiment`
Get comments from a Reddit post and analyze their sentiment.

**Parameters:**
- `post_id` (string): Reddit post ID
- `limit` (integer): Maximum number of comments to analyze (default: 50)
- `sort_by` (string): Sort method (top, best, new, controversial, old, qa, default: top)

**Returns:**
- Comments with sentiment analysis and overall sentiment metrics

**Payment:** 0.000015 tokens per request

### 4. `get_api_info`
Get information about the Reddit + VADER Integration service and its status.

**Returns:**
- Service information, authentication status, and available endpoints

**Payment:** 0.000005 tokens per request

## Installation

### Using Docker (Recommended)

1. Clone this repository:
   ```bash
   git clone https://github.com/Traia-IO/reddit-vader-sentiment-analysis-integration-mcp-server.git
   cd reddit-vader-sentiment-analysis-integration-mcp-server
   ```

2. Set your environment variables:
   ```bash
   export SERVER_ADDRESS="your-iatp-wallet-address"
   export MCP_OPERATOR_PRIVATE_KEY="your-operator-key"
   ```

3. Run with Docker:
   ```bash
   ./run_local_docker.sh
   ```

### Using Docker Compose

1. Create a `.env` file with your configuration:
   ```env
   SERVER_ADDRESS=your-iatp-wallet-address
   MCP_OPERATOR_PRIVATE_KEY=your-operator-key
   PORT=8000
   LOG_LEVEL=INFO
   D402_TESTING_MODE=false
   FACILITATOR_URL=https://facilitator.example.com
   ```

2. Start the server:
   ```bash
   docker-compose up
   ```

### Manual Installation

1. Install dependencies using `uv`:
   ```bash
   uv pip install -e .
   ```

2. Run the server:
   ```bash
   SERVER_ADDRESS="your-iatp-wallet-address" uv run python -m server
   ```

## Usage

### Health Check

Test if the server is running:
```bash
python mcp_health_check.py
```

### Using with CrewAI

```python
from traia_iatp.mcp.traia_mcp_adapter import create_mcp_adapter

# Connect to the MCP server with payment
with create_mcp_adapter(
    url="http://localhost:8000/mcp/"
) as tools:
    # Use the tools
    for tool in tools:
        print(f"Available tool: {tool.name}")
        
    # Example: Analyze subreddit sentiment
    result = await tool.analyze_subreddit_sentiment(
        subreddit_name="cryptocurrency",
        keywords="bitcoin,btc",
        limit=25,
        sort_by="hot"
    )
    print(f"Analyzed {result['posts_analyzed']} posts")
    print(f"Overall sentiment: {result['overall_sentiment']}")
    
    # Example: Search and analyze sentiment
    result = await tool.search_and_analyze_reddit_sentiment(
        subreddit_name="Bitcoin",
        query="price prediction",
        limit=20
    )
    print(f"Found {result['posts_analyzed']} matching posts")
    
    # Example: Analyze post comments
    result = await tool.analyze_post_comments_sentiment(
        post_id="abc123",
        limit=50,
        sort_by="top"
    )
    print(f"Analyzed {result['comments_analyzed']} comments")
```

## Example Responses

### Subreddit Sentiment Analysis
```json
{
  "status": "success",
  "subreddit": "cryptocurrency",
  "posts_analyzed": 25,
  "overall_sentiment": {
    "positive_count": 12,
    "negative_count": 5,
    "neutral_count": 8,
    "average_compound_score": 0.2145,
    "dominant_sentiment": "positive",
    "sentiment_distribution": {
      "positive_percentage": 48.00,
      "negative_percentage": 20.00,
      "neutral_percentage": 32.00
    }
  },
  "posts": [
    {
      "id": "abc123",
      "title": "Bitcoin reaches new high",
      "score": 1234,
      "sentiment_analysis": {
        "scores": {
          "neg": 0.0,
          "neu": 0.4,
          "pos": 0.6,
          "compound": 0.7
        },
        "category": "positive"
      }
    }
  ]
}
```

## Reddit Authentication

This server requires Reddit API credentials. You can provide them in two ways:

### Option 1: Via Authorization Header (Recommended)
Format: `client_id:client_secret:user_agent`
```
Authorization: Bearer your_client_id:your_client_secret:MyApp/1.0
```

### Option 2: Via Custom Headers (Legacy)
```
X-Reddit-Client-ID: your_client_id
X-Reddit-Client-Secret: your_client_secret
X-Reddit-User-Agent: MyApp/1.0
```

To get Reddit API credentials:
1. Go to https://www.reddit.com/prefs/apps
2. Create a new application (script type)
3. Note your client_id and client_secret

## Payment Protocol

This server uses the D402 payment protocol (HTTP 402) for access control:

- **Payment Required**: All tool calls require payment verification
- **Token-based**: Uses blockchain tokens for payment (Sepolia testnet by default)
- **Facilitator**: Payments are processed through a facilitator service
- **Testing Mode**: Can be disabled for development using `D402_TESTING_MODE=true`
- **Dual Mode**: Supports both payment and Reddit API authentication

### Payment Configuration

Set the following environment variables:

- `SERVER_ADDRESS`: Your IATP wallet contract address (required)
- `MCP_OPERATOR_PRIVATE_KEY`: Operator signing key for payment verification (required)
- `FACILITATOR_URL`: Payment facilitator URL (required unless testing mode is enabled)
- `D402_TESTING_MODE`: Set to "true" to bypass facilitator for testing (default: false)
- `NETWORK`: Blockchain network (default: sepolia)

## Development

### Testing the Server

1. Start the server locally
2. Run the health check: `python mcp_health_check.py`
3. Test individual tools using the CrewAI adapter

### Adding New Tools

To add new tools, edit `server.py` and:

1. Add `@mcp.tool()` and `@require_payment_for_tool()` decorated functions
2. Update this README with the new tools
3. Update `deployment_params.json` with the tool names in the capabilities array
4. Update `endpoints.json` with the new endpoint documentation

## Deployment

### Deployment Configuration

The `deployment_params.json` file contains the deployment configuration for this MCP server:

```json
{
  "github_url": "https://github.com/Traia-IO/reddit-vader-sentiment-analysis-integration-mcp-server",
  "mcp_server": {
    "name": "reddit-vader-integration-mcp",
    "description": "Combines Reddit API integration (PRAW) with VADER sentiment analysis to provide comprehensive sentiment monitoring of Reddit discussions around crypto topics and other subjects. Uses D402 payment protocol for access control.",
    "server_type": "streamable-http",
    "requires_api_key": true,
    "capabilities": [
      "analyze_subreddit_sentiment",
      "search_and_analyze_reddit_sentiment",
      "analyze_post_comments_sentiment",
      "get_api_info"
    ],
    "payment_protocol": "402"
  }
}
```

**Important**: Always update the `capabilities` array when you add or remove tools!

### Google Cloud Run

This server is designed to be deployed on Google Cloud Run. The deployment will:

1. Build a container from the Dockerfile
2. Deploy to Cloud Run with the specified configuration
3. Expose the `/mcp` endpoint for client connections

## Environment Variables

- `PORT`: Server port (default: 8000)
- `STAGE`: Environment stage (default: MAINNET, options: MAINNET, TESTNET)
- `LOG_LEVEL`: Logging level (default: INFO)
- `SERVER_ADDRESS`: Payment address (IATP wallet contract) - **required for D402 payment protocol**
- `MCP_OPERATOR_PRIVATE_KEY`: Operator signing key for payment protocol - **required**
- `D402_TESTING_MODE`: Skip facilitator for testing (default: false)
- `FACILITATOR_URL`: Payment facilitator URL - **required if testing mode is disabled**
- `D402_FACILITATOR_API_KEY`: API key for facilitator service (optional)
- `NETWORK`: Blockchain network (default: sepolia)

## Features & Capabilities

### Reddit Integration (PRAW)
- Fetch posts from any public subreddit
- Search posts with keywords
- Get post comments with various sort options
- Support for all Reddit sorting methods (hot, new, top, rising, etc.)
- Time-based filtering (hour, day, week, month, year, all)

### VADER Sentiment Analysis
- Specialized for social media text
- Returns compound, positive, negative, and neutral scores
- Categorizes sentiment as positive, negative, or neutral
- Optimized for informal text and emoticons

### Comprehensive Metrics
- Overall sentiment distribution
- Average compound scores
- Dominant sentiment identification
- Percentage breakdowns
- Per-post/comment sentiment details

## Troubleshooting

1. **Server not starting**: Check Docker logs with `docker logs <container-id>`
2. **Payment errors**: Ensure SERVER_ADDRESS and MCP_OPERATOR_PRIVATE_KEY are set correctly
3. **Reddit API errors**: Verify your Reddit credentials are valid
4. **Connection errors**: Ensure the server is running on the expected port
5. **Tool errors**: Check the server logs for detailed error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement new tools or improvements
4. Update the README, deployment_params.json, and endpoints.json
5. Submit a pull request

## License

[MIT License](LICENSE)
