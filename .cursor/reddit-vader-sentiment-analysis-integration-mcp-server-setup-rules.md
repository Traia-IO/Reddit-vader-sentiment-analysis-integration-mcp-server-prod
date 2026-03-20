# Reddit + VADER Sentiment Analysis Integration MCP Server Implementation Guide

You are working on the Reddit Vader Sentiment Analysis Integration MCP (Model Context Protocol) server. This server has been updated to support the D402 payment protocol.

## D402 Payment Protocol Integration

This server uses the D402 payment protocol for HTTP 402 payment handling. The payment middleware is configured in `server.py` using:

- `D402PaymentMiddleware` from `traia_iatp.d402.starlette_middleware`
- `@require_payment_for_tool` decorator for each tool
- Payment configuration extracted from tool decorators

### Key Files Updated

- `pyproject.toml`: Updated to use `traia-iatp>=0.1.66` for D402 support
- `server.py`: Should use `@require_payment_for_tool` decorator on all tools
- `env.example`: Contains D402 payment protocol configuration variables
- `Dockerfile`: Updated to support local IATP package for development
- `docker-compose.yml`: Includes D402 payment protocol environment variables
- `run_local_docker.sh`: Generates Ethereum accounts for local testing

### Environment Variables

Required for D402 payment protocol:
- `SERVER_ADDRESS`: Payment address (IATP wallet contract)
- `MCP_OPERATOR_PRIVATE_KEY`: Operator signing key
- `D402_TESTING_MODE`: Skip facilitator for testing (default: false)
- `D402_FACILITATOR_URL`: Payment facilitator URL
- `NETWORK`: Blockchain network (default: sepolia)

### Tool Implementation Pattern

All tools should follow this pattern:

```python
@mcp.tool()
@require_payment_for_tool(
    price=TokenAmount(
        amount="10000000000000",  # Price in token units
        asset=TokenAsset(
            address="0x3e17730bb2ca51a8D5deD7E44c003A2e95a4d822",
            decimals=6,
            network="sepolia",
            eip712=EIP712Domain(
                name="IATPWallet",
                version="1"
            )
        )
    ),
    description="Tool description"
)
async def tool_name(
    context: Context,
    # tool parameters
) -> Dict[str, Any]:
    """Tool docstring"""
    # Payment already verified by @require_payment_for_tool decorator
    api_key = get_active_api_key(context)
    # Tool implementation
```

### Testing

1. Run the server locally:
   ```bash
   ./run_local_docker.sh
   ```

2. Use the health check script:
   ```bash
   python mcp_health_check.py
   ```

3. Test with CrewAI:
   ```python
   from traia_iatp.mcp.traia_mcp_adapter import create_mcp_adapter
   
   with create_mcp_adapter(
       url="http://localhost:8000/mcp/"
   ) as tools:
       for tool in tools:
           print(f"Tool: {tool.name}")
   ```

### Important Notes

- All tools must use the `@require_payment_for_tool` decorator
- Payment verification is handled automatically by the middleware
- Use `get_active_api_key(context)` to get the API key from the payment context
- The server uses FastMCP with D402 payment middleware wrapper
