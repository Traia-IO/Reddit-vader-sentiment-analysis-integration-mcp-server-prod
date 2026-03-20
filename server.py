#!/usr/bin/env python3
"""
Reddit + VADER Sentiment Analysis Integration MCP Server - FastMCP with D402 Transport Wrapper

Uses FastMCP from official MCP SDK with D402MCPTransport wrapper for HTTP 402.

Architecture:
- FastMCP for tool decorators and Context objects
- D402MCPTransport wraps the /mcp route for HTTP 402 interception
- Proper HTTP 402 status codes (not JSON-RPC wrapped)
- Combines Reddit API integration (PRAW) with VADER sentiment analysis

Environment Variables:
- SERVER_ADDRESS: Payment address (IATP wallet contract)
- MCP_OPERATOR_PRIVATE_KEY: Operator signing key
- D402_TESTING_MODE: Skip facilitator (default: false)
"""

import os
import logging
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime

import praw
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
import uvicorn

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('reddit_vader_integration_mcp')

# FastMCP from official SDK
from mcp.server.fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

# D402 payment protocol - using Starlette middleware
from traia_iatp.d402.starlette_middleware import D402PaymentMiddleware
from traia_iatp.d402.mcp_middleware import require_payment_for_tool, get_active_api_key
from traia_iatp.d402.payment_introspection import extract_payment_configs_from_mcp
from traia_iatp.d402.types import TokenAmount, TokenAsset, EIP712Domain

# Configuration
STAGE = os.getenv("STAGE", "MAINNET").upper()
PORT = int(os.getenv("PORT", "8000"))
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS")
if not SERVER_ADDRESS:
    raise ValueError("SERVER_ADDRESS required for payment protocol")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")  # Server's fallback secret (for internal_api_key)
if not REDDIT_CLIENT_ID:
    logger.warning(f"⚠️  REDDIT_CLIENT_ID not set - payment required for all requests")

# Initialize VADER sentiment analyzer (no API key needed - local library)
analyzer = SentimentIntensityAnalyzer()

logger.info("="*80)
logger.info(f"Reddit + VADER Sentiment Analysis Integration MCP Server (FastMCP + D402 Wrapper)")
logger.info(f"API: Reddit API (PRAW) + VADER Sentiment")
logger.info(f"Payment: {SERVER_ADDRESS}")
logger.info(f"Client ID: {'✅' if REDDIT_CLIENT_ID else '❌ Payment required'}")
logger.info(f"Client Secret: {'✅ (fallback)' if REDDIT_CLIENT_SECRET else '❌ Payment required (user must provide)'}")
logger.info("="*80)

# Create FastMCP server
mcp = FastMCP("Reddit + VADER Sentiment Analysis Integration MCP Server", host="0.0.0.0")

logger.info(f"✅ FastMCP server created")
logger.info(f"✅ VADER sentiment analyzer initialized")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_reddit_client(client_secret: str) -> praw.Reddit:
    """
    Create a PRAW Reddit client using credentials.
    
    IMPORTANT: Always creates client (even with bad/empty credentials).
    This matches Serper/NewsAPI pattern where API calls are attempted regardless.
    Failures happen during API call (not at client creation), allowing middleware
    to intercept 401 errors and convert to 402 for payment settlement.
    
    Args:
        client_secret: Reddit client secret (from get_active_api_key - handles user/server fallback)
    
    Uses server's REDDIT_CLIENT_ID from environment.
    User agent follows Reddit format: "web:reddit-vader-sentiment-analysis-integration-mcp-server:1.0.0 (by /u/traia-mcp)"
    
    Returns:
        praw.Reddit client (always, even with bad credentials)
    """
    # Use server's client_id (from environment), fallback to empty string
    client_id = REDDIT_CLIENT_ID or ""
    
    # User agent follows Reddit's required format: <platform>:<app ID>:<version> (by /u/<username>)
    user_agent = "web:reddit-vader-sentiment-analysis-integration-mcp-server:1.0.0 (by /u/traia-mcp)"
    
    # ALWAYS create client (like Serper/NewsAPI always make requests)
    # Let PRAW fail during API call, not at creation time
    # This allows middleware to intercept 401 → convert to 402
    logger.info(f"Creating Reddit client with client_id: {client_id[:10] if client_id else '(empty)'}...")
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret or "",
        user_agent=user_agent
    )


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

@mcp.tool()
@require_payment_for_tool(
    price=TokenAmount(
        amount="20",  # 0.00002 tokens
        asset=TokenAsset(
            address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            decimals=6,
            network="arbitrum_one",
            eip712=EIP712Domain(
                name="IATPWallet",
                version="1"
            )
        )
    ),
    description="Analyze sentiment of posts in a subreddit with optional keyword filtering"
)
async def analyze_subreddit_sentiment(
    context: Context,
    subreddit_name: str,
    keywords: Optional[str] = None,
    limit: int = 25,
    time_filter: str = "day",
    sort_by: str = "hot"
) -> Dict[str, Any]:
    """
    Analyze sentiment of posts in a subreddit, optionally filtered by keywords.
    
    Args:
        context: MCP context (auto-injected by framework, not user-provided)
        subreddit_name: Name of the subreddit (without r/)
        keywords: Optional comma-separated keywords to filter posts
        limit: Maximum number of posts to analyze (max 100)
        time_filter: Time filter for posts (hour, day, week, month, year, all)
        sort_by: Sort method (hot, new, top, rising)
        
    Returns:
        Dictionary with sentiment analysis results for subreddit posts
    """
    # Payment already verified by @require_payment_for_tool decorator
    # Get API key using helper (handles request.state fallback)
    client_secret = get_active_api_key(context)
    
    # Always create client (even with bad credentials) - matches Serper/NewsAPI pattern
    # Failures happen during API call, allowing middleware to intercept 401 → 402
    reddit = create_reddit_client(client_secret)
    
    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        # Get posts based on sort method
        if sort_by == "hot":
            posts = subreddit.hot(limit=limit)
        elif sort_by == "new":
            posts = subreddit.new(limit=limit)
        elif sort_by == "top":
            posts = subreddit.top(time_filter=time_filter, limit=limit)
        elif sort_by == "rising":
            posts = subreddit.rising(limit=limit)
        else:
            posts = subreddit.hot(limit=limit)
        
        # Filter posts by keywords if provided
        if keywords:
            keyword_list = [k.strip().lower() for k in keywords.split(',')]
            filtered_posts = []
            for post in posts:
                post_text = f"{post.title} {post.selftext}".lower()
                if any(keyword in post_text for keyword in keyword_list):
                    filtered_posts.append(post)
            posts = filtered_posts
        
        # Analyze sentiment of posts
        posts_data = []
        overall_sentiment = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "total_compound": 0
        }
        
        for post in posts:
            # Combine title and body for sentiment analysis
            text_for_analysis = f"{post.title} {post.selftext}"
            
            # Analyze sentiment using VADER
            sentiment_scores = analyzer.polarity_scores(text_for_analysis)
            
            # Determine sentiment category
            compound_score = sentiment_scores['compound']
            if compound_score >= 0.05:
                sentiment_category = "positive"
                overall_sentiment["positive"] += 1
            elif compound_score <= -0.05:
                sentiment_category = "negative"
                overall_sentiment["negative"] += 1
            else:
                sentiment_category = "neutral"
                overall_sentiment["neutral"] += 1
            
            overall_sentiment["total_compound"] += compound_score
            
            posts_data.append({
                "id": post.id,
                "title": post.title,
                "author": str(post.author) if post.author else "[deleted]",
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "num_comments": post.num_comments,
                "created_utc": post.created_utc,
                "url": post.url,
                "selftext": post.selftext[:500] if post.selftext else "",
                "subreddit": str(post.subreddit),
                "permalink": f"https://reddit.com{post.permalink}",
                "sentiment_analysis": {
                    "scores": sentiment_scores,
                    "category": sentiment_category
                }
            })
        
        # Calculate overall sentiment metrics
        total_posts = len(posts_data)
        if total_posts > 0:
            avg_compound = overall_sentiment["total_compound"] / total_posts
            sentiment_distribution = {
                "positive_percentage": round((overall_sentiment["positive"] / total_posts) * 100, 2),
                "negative_percentage": round((overall_sentiment["negative"] / total_posts) * 100, 2),
                "neutral_percentage": round((overall_sentiment["neutral"] / total_posts) * 100, 2)
            }
        else:
            avg_compound = 0
            sentiment_distribution = {"positive_percentage": 0, "negative_percentage": 0, "neutral_percentage": 0}
        
        return {
            "status": "success",
            "subreddit": subreddit_name,
            "keywords_filter": keywords,
            "sort_by": sort_by,
            "time_filter": time_filter,
            "posts_analyzed": total_posts,
            "posts": posts_data,
            "overall_sentiment": {
                "positive_count": overall_sentiment["positive"],
                "negative_count": overall_sentiment["negative"],
                "neutral_count": overall_sentiment["neutral"],
                "average_compound_score": round(avg_compound, 4),
                "dominant_sentiment": max(overall_sentiment, key=lambda k: overall_sentiment[k] if k != "total_compound" else 0),
                "sentiment_distribution": sentiment_distribution
            }
        }
    except Exception as e:
        logger.error(f"Error in analyze_subreddit_sentiment: {e}")
        return {"error": f"Failed to analyze subreddit sentiment: {str(e)}"}


@mcp.tool()
@require_payment_for_tool(
    price=TokenAmount(
        amount="20",  # 0.00002 tokens
        asset=TokenAsset(
            address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            decimals=6,
            network="arbitrum_one",
            eip712=EIP712Domain(
                name="IATPWallet",
                version="1"
            )
        )
    ),
    description="Search for posts in a subreddit and analyze their sentiment"
)
async def search_and_analyze_reddit_sentiment(
    context: Context,
    subreddit_name: str,
    query: str,
    limit: int = 25,
    time_filter: str = "month",
    sort_by: str = "relevance"
) -> Dict[str, Any]:
    """
    Search for posts in a subreddit using keywords and analyze their sentiment.
    
    Args:
        context: MCP context (auto-injected by framework, not user-provided)
        subreddit_name: Name of the subreddit (without r/)
        query: Search query/keywords
        limit: Maximum number of posts to analyze (max 100)
        time_filter: Time filter for posts (hour, day, week, month, year, all)
        sort_by: Sort method (relevance, hot, top, new, comments)
        
    Returns:
        Dictionary with search results and sentiment analysis
    """
    # Payment already verified by @require_payment_for_tool decorator
    # Get API key using helper (handles request.state fallback)
    client_secret = get_active_api_key(context)
    
    # Always create client (even with bad credentials) - matches Serper/NewsAPI pattern
    # Failures happen during API call, allowing middleware to intercept 401 → 402
    reddit = create_reddit_client(client_secret)
    
    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        # Search for posts
        search_results = subreddit.search(
            query=query,
            limit=limit,
            time_filter=time_filter,
            sort=sort_by
        )
        
        # Analyze sentiment of search results
        posts_data = []
        overall_sentiment = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "total_compound": 0
        }
        
        for post in search_results:
            # Combine title and body for sentiment analysis
            text_for_analysis = f"{post.title} {post.selftext}"
            
            # Analyze sentiment using VADER
            sentiment_scores = analyzer.polarity_scores(text_for_analysis)
            
            # Determine sentiment category
            compound_score = sentiment_scores['compound']
            if compound_score >= 0.05:
                sentiment_category = "positive"
                overall_sentiment["positive"] += 1
            elif compound_score <= -0.05:
                sentiment_category = "negative"
                overall_sentiment["negative"] += 1
            else:
                sentiment_category = "neutral"
                overall_sentiment["neutral"] += 1
            
            overall_sentiment["total_compound"] += compound_score
            
            posts_data.append({
                "id": post.id,
                "title": post.title,
                "author": str(post.author) if post.author else "[deleted]",
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "num_comments": post.num_comments,
                "created_utc": post.created_utc,
                "url": post.url,
                "selftext": post.selftext[:500] if post.selftext else "",
                "subreddit": str(post.subreddit),
                "permalink": f"https://reddit.com{post.permalink}",
                "sentiment_analysis": {
                    "scores": sentiment_scores,
                    "category": sentiment_category
                }
            })
        
        # Calculate overall sentiment metrics
        total_posts = len(posts_data)
        if total_posts > 0:
            avg_compound = overall_sentiment["total_compound"] / total_posts
            sentiment_distribution = {
                "positive_percentage": round((overall_sentiment["positive"] / total_posts) * 100, 2),
                "negative_percentage": round((overall_sentiment["negative"] / total_posts) * 100, 2),
                "neutral_percentage": round((overall_sentiment["neutral"] / total_posts) * 100, 2)
            }
        else:
            avg_compound = 0
            sentiment_distribution = {"positive_percentage": 0, "negative_percentage": 0, "neutral_percentage": 0}
        
        return {
            "status": "success",
            "subreddit": subreddit_name,
            "query": query,
            "sort_by": sort_by,
            "time_filter": time_filter,
            "posts_analyzed": total_posts,
            "posts": posts_data,
            "overall_sentiment": {
                "positive_count": overall_sentiment["positive"],
                "negative_count": overall_sentiment["negative"],
                "neutral_count": overall_sentiment["neutral"],
                "average_compound_score": round(avg_compound, 4),
                "dominant_sentiment": max(overall_sentiment, key=lambda k: overall_sentiment[k] if k != "total_compound" else 0),
                "sentiment_distribution": sentiment_distribution
            }
        }
    except Exception as e:
        logger.error(f"Error in search_and_analyze_reddit_sentiment: {e}")
        return {"error": f"Failed to search and analyze Reddit sentiment: {str(e)}"}


@mcp.tool()
@require_payment_for_tool(
    price=TokenAmount(
        amount="15000000000000",  # 0.000015 tokens
        asset=TokenAsset(
            address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            decimals=6,
            network="arbitrum_one",
            eip712=EIP712Domain(
                name="IATPWallet",
                version="1"
            )
        )
    ),
    description="Get comments from a Reddit post and analyze their sentiment"
)
async def analyze_post_comments_sentiment(
    context: Context,
    post_id: str,
    limit: int = 50,
    sort_by: str = "top"
) -> Dict[str, Any]:
    """
    Get comments from a Reddit post and analyze their sentiment.
    
    Args:
        context: MCP context (auto-injected by framework, not user-provided)
        post_id: Reddit post ID
        limit: Maximum number of comments to analyze
        sort_by: Sort method (top, best, new, controversial, old, qa)
        
    Returns:
        Dictionary with post comments and sentiment analysis
    """
    # Payment already verified by @require_payment_for_tool decorator
    # Get API key using helper (handles request.state fallback)
    client_secret = get_active_api_key(context)
    
    # Always create client (even with bad credentials) - matches Serper/NewsAPI pattern
    # Failures happen during API call, allowing middleware to intercept 401 → 402
    reddit = create_reddit_client(client_secret)
    
    try:
        submission = reddit.submission(id=post_id)
        
        # Set comment sort order
        submission.comment_sort = sort_by
        
        # Get comments
        submission.comments.replace_more(limit=0)  # Remove "load more comments" links
        
        # Analyze sentiment of comments
        comments_data = []
        overall_sentiment = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "total_compound": 0
        }
        
        for comment in submission.comments.list()[:limit]:
            if not comment.body or not comment.body.strip():
                continue
                
            # Analyze sentiment using VADER
            sentiment_scores = analyzer.polarity_scores(comment.body)
            
            # Determine sentiment category
            compound_score = sentiment_scores['compound']
            if compound_score >= 0.05:
                sentiment_category = "positive"
                overall_sentiment["positive"] += 1
            elif compound_score <= -0.05:
                sentiment_category = "negative"
                overall_sentiment["negative"] += 1
            else:
                sentiment_category = "neutral"
                overall_sentiment["neutral"] += 1
            
            overall_sentiment["total_compound"] += compound_score
            
            comments_data.append({
                "id": comment.id,
                "body": comment.body[:1000] if comment.body else "",
                "author": str(comment.author) if comment.author else "[deleted]",
                "score": comment.score,
                "created_utc": comment.created_utc,
                "permalink": f"https://reddit.com{comment.permalink}",
                "parent_id": comment.parent_id,
                "is_submitter": comment.is_submitter,
                "sentiment_analysis": {
                    "scores": sentiment_scores,
                    "category": sentiment_category
                }
            })
        
        # Calculate overall sentiment metrics
        total_comments = len(comments_data)
        if total_comments > 0:
            avg_compound = overall_sentiment["total_compound"] / total_comments
            sentiment_distribution = {
                "positive_percentage": round((overall_sentiment["positive"] / total_comments) * 100, 2),
                "negative_percentage": round((overall_sentiment["negative"] / total_comments) * 100, 2),
                "neutral_percentage": round((overall_sentiment["neutral"] / total_comments) * 100, 2)
            }
        else:
            avg_compound = 0
            sentiment_distribution = {"positive_percentage": 0, "negative_percentage": 0, "neutral_percentage": 0}
        
        return {
            "status": "success",
            "post_id": post_id,
            "post_title": submission.title,
            "sort_by": sort_by,
            "comments_analyzed": total_comments,
            "comments": comments_data,
            "overall_sentiment": {
                "positive_count": overall_sentiment["positive"],
                "negative_count": overall_sentiment["negative"],
                "neutral_count": overall_sentiment["neutral"],
                "average_compound_score": round(avg_compound, 4),
                "dominant_sentiment": max(overall_sentiment, key=lambda k: overall_sentiment[k] if k != "total_compound" else 0),
                "sentiment_distribution": sentiment_distribution
            }
        }
    except Exception as e:
        logger.error(f"Error in analyze_post_comments_sentiment: {e}")
        return {"error": f"Failed to analyze post comments sentiment: {str(e)}"}


@mcp.tool()
@require_payment_for_tool(
    price=TokenAmount(
        amount="5",  # 0.000005 tokens (lower price for info)
        asset=TokenAsset(
            address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            decimals=6,
            network="arbitrum_one",
            eip712=EIP712Domain(
                name="IATPWallet",
                version="1"
            )
        )
    ),
    description="Get information about the Reddit + VADER Sentiment Analysis Integration service"
)
async def get_api_info(context: Context) -> Dict[str, Any]:
    """
    Get information about the Reddit + VADER Sentiment Analysis Integration service.
    
    Args:
        context: MCP context (auto-injected by framework, not user-provided)
    
    Returns:
        Dictionary containing API information and status
    """
    # Payment already verified by @require_payment_for_tool decorator
    # Get API key using helper (handles request.state fallback)
    client_secret = get_active_api_key(context)
    
    # Always create client (even with bad credentials) - matches Serper/NewsAPI pattern
    # Failures happen during API call, allowing middleware to intercept 401 → 402
    reddit = create_reddit_client(client_secret)
    auth_status = "authenticated" if reddit else "not authenticated"
    
    return {
        "status": "ready",
        "auth_status": auth_status,
        "api_name": "Reddit + VADER Sentiment Analysis Integration",
        "api_url": "https://www.reddit.com/dev/api/",
        "documentation": "https://praw.readthedocs.io/en/stable/",
        "description": "Combines Reddit API integration (PRAW) with VADER sentiment analysis to provide comprehensive sentiment monitoring of Reddit discussions around crypto topics and other subjects.",
        "authentication": "Reddit API credentials required (client_id, client_secret, user_agent)",
        "required_headers": [
            "X-Reddit-Client-ID",
            "X-Reddit-Client-Secret", 
            "X-Reddit-User-Agent (optional, defaults to Traia-Reddit-VADER-MCP-Server/1.0)"
        ],
        "available_endpoints": [
            "analyze_subreddit_sentiment",
            "search_and_analyze_reddit_sentiment",
            "analyze_post_comments_sentiment",
            "get_api_info"
        ],
        "features": [
            "Reddit post and comment fetching using PRAW",
            "VADER sentiment analysis for social media text",
            "Keyword filtering and search capabilities",
            "Comprehensive sentiment metrics and distribution",
            "Support for multiple subreddits and time filters"
        ]
    }


# ============================================================================
# APPLICATION SETUP WITH STARLETTE MIDDLEWARE
# ============================================================================

def create_app_with_middleware():
    """
    Create Starlette app with d402 payment middleware.
    
    Strategy:
    1. Get FastMCP's Starlette app via streamable_http_app()
    2. Extract payment configs from @require_payment_for_tool decorators
    3. Add Starlette middleware with extracted configs
    4. Single source of truth - no duplication!
    """
    logger.info("🔧 Creating FastMCP app with middleware...")
    
    # Get FastMCP's Starlette app
    app = mcp.streamable_http_app()
    logger.info(f"✅ Got FastMCP Starlette app")
    
    # Extract payment configs from decorators (single source of truth!)
    tool_payment_configs = extract_payment_configs_from_mcp(mcp, SERVER_ADDRESS)
    logger.info(f"📊 Extracted {len(tool_payment_configs)} payment configs from @require_payment_for_tool decorators")
    
    # D402 Configuration
    facilitator_url = os.getenv("FACILITATOR_URL") or os.getenv("D402_FACILITATOR_URL")
    operator_key = os.getenv("MCP_OPERATOR_PRIVATE_KEY")
    network = os.getenv("NETWORK", "sepolia")
    testing_mode = os.getenv("D402_TESTING_MODE", "false").lower() == "true"
    
    # Log D402 configuration with prominent facilitator info
    logger.info("="*60)
    logger.info("D402 Payment Protocol Configuration:")
    logger.info(f"  Server Address: {SERVER_ADDRESS}")
    logger.info(f"  Network: {network}")
    logger.info(f"  Operator Key: {'✅ Set' if operator_key else '❌ Not set'}")
    logger.info(f"  Testing Mode: {'⚠️  ENABLED (bypasses facilitator)' if testing_mode else '✅ DISABLED (uses facilitator)'}")
    logger.info("="*60)
    
    if not facilitator_url and not testing_mode:
        logger.error("❌ FACILITATOR_URL required when testing_mode is disabled!")
        raise ValueError("Set FACILITATOR_URL or enable D402_TESTING_MODE=true")
    
    if facilitator_url:
        logger.info(f"🌐 FACILITATOR: {facilitator_url}")
        if "localhost" in facilitator_url or "127.0.0.1" in facilitator_url or "host.docker.internal" in facilitator_url:
            logger.info(f"   📍 Using LOCAL facilitator for development")
        else:
            logger.info(f"   🌍 Using REMOTE facilitator for production")
    else:
        logger.warning("⚠️  D402 Testing Mode - Facilitator bypassed")
    logger.info("="*60)
    
    # Add CORS middleware first (processes before other middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
        expose_headers=["mcp-session-id"],  # Expose custom headers to browser
    )
    logger.info("✅ Added CORS middleware (allow all origins, expose mcp-session-id)")
    
    # Add D402 payment middleware with extracted configs
    app.add_middleware(
        D402PaymentMiddleware,
        tool_payment_configs=tool_payment_configs,
        server_address=SERVER_ADDRESS,
        requires_auth=True,  # Extracts API keys + checks payment
        internal_api_key=REDDIT_CLIENT_SECRET,  # Server's internal Reddit secret (for Mode 2: paid access)
        testing_mode=testing_mode,
        facilitator_url=facilitator_url,
        facilitator_api_key=os.getenv("D402_FACILITATOR_API_KEY"),
        server_name="reddit-vader-sentiment-analysis-integration-mcp-server"  # MCP server ID for tracking
    )
    logger.info("✅ Added D402PaymentMiddleware")
    logger.info("   - Auth extraction: Enabled")
    logger.info("   - Dual mode: Reddit client_secret OR payment")
    
    # Add health check endpoint (bypasses middleware)
    @app.route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint for container orchestration."""
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "reddit-vader-sentiment-analysis-integration-mcp-server",
                "timestamp": datetime.now().isoformat()
            }
        )
    logger.info("✅ Added /health endpoint")
    
    return app

if __name__ == "__main__":
    logger.info("="*80)
    logger.info(f"Starting Reddit + VADER Sentiment Analysis Integration MCP Server")
    logger.info("="*80)
    logger.info("Architecture:")
    logger.info("  1. D402PaymentMiddleware intercepts requests")
    logger.info("     - Checks payment → HTTP 402 if missing")
    logger.info("  2. FastMCP processes valid requests with tool decorators")
    logger.info("  3. Tools use Reddit API (PRAW) + VADER for sentiment analysis")
    logger.info("="*80)
    
    # Create app with middleware
    app = create_app_with_middleware()
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
