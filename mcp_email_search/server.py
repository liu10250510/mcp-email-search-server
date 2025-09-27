#!/usr/bin/env python3
"""Email Search MCP Server - Main server implementation using FastMCP."""

import asyncio
import logging
import os
import sys
from typing import List

from dotenv import load_dotenv
from fastmcp import FastMCP

from .types import EmailSearchParams, EmailSearchResult, EmailDetails
from .services.yahoo import YahooService

# Load environment variables
load_dotenv()

# Configure logging to stderr to avoid stdout pollution
logging.basicConfig(
    level=logging.WARNING,  # Reduce log level to avoid interfering with MCP
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP app
app = FastMCP("email-search-agent")

# Initialize email service
yahoo_service = YahooService()


@app.tool()
async def search_emails(
    keywords: str,
    provider: str = "yahoo",
    date_from: str = None,
    date_to: str = None,
    max_results: int = 10,
    include_attachments: bool = False,
) -> str:
    """
    Search emails across Gmail and/or Yahoo accounts using keywords and date filters.
    
    Args:
        keywords: Keywords to search for in email content, subject, or sender
        provider: Email provider to search - only "yahoo" supported (default: "yahoo")
        date_from: Start date in YYYY-MM-DD format (optional)
        date_to: End date in YYYY-MM-DD format (optional)
        max_results: Maximum number of results to return (1-50, default: 10)
        include_attachments: Whether to include emails with attachments (default: False)
    
    Returns:
        Formatted string containing search results
    """
    try:
        # Validate and create search parameters
        search_params = EmailSearchParams(
            keywords=keywords,
            provider=provider,
            date_from=date_from,
            date_to=date_to,
            max_results=min(max_results, 50),
            include_attachments=include_attachments,
        )
        
        results: List[EmailSearchResult] = []
        errors: List[str] = []
        
        # Search Yahoo emails
        try:
            results = await yahoo_service.search_emails(search_params)
        except Exception as e:
            error_msg = f"Yahoo search failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # Sort results by date (newest first)
        results.sort(key=lambda x: x.date, reverse=True)
        
        # Limit results
        limited_results = results[:search_params.max_results]
        
        # Format response
        response_text = f"Found {len(limited_results)} emails"
        
        if errors:
            response_text += f" (with {len(errors)} error(s): {', '.join(errors)})"
        
        response_text += f"""

Search Parameters:
- Keywords: "{search_params.keywords}"
- Provider: {search_params.provider}
- Date Range: {search_params.date_from or "any"} to {search_params.date_to or "any"}
- Max Results: {search_params.max_results}
- Include Attachments: {search_params.include_attachments}

Results:
"""
        
        if limited_results:
            for i, email in enumerate(limited_results, 1):
                response_text += f"""
{i}. [{email.provider.upper()}] {email.subject}
   From: {email.sender}
   Date: {email.date.strftime("%Y-%m-%d %H:%M")}
   Preview: {email.snippet}
   {"📎 Has attachments" if email.has_attachments else ""}
   ---"""
        else:
            response_text += "\nNo emails found matching your search criteria."
            
            if not errors:
                response_text += "\n\nTry:\n- Using different keywords\n- Expanding the date range\n- Checking if your email accounts are properly configured"
        
        return response_text
        
    except Exception as e:
        error_message = f"Error searching emails: {str(e)}"
        logger.error(error_message)
        return error_message


@app.tool()
async def get_email_details(email_id: str, provider: str) -> str:
    """
    Get detailed content of a specific email by ID.
    
    Args:
        email_id: The unique ID of the email to retrieve
        provider: Email provider - only "yahoo" supported
    
    Returns:
        Formatted string containing detailed email information
    """
    try:
        if provider != "yahoo":
            return "Error: Only 'yahoo' provider is supported"
        
        email_details: EmailDetails = await yahoo_service.get_email_details(email_id)
        
        response_text = f"""Email Details [{provider.upper()}]:

Subject: {email_details.subject}
From: {email_details.sender}
To: {', '.join(email_details.recipients)}
Date: {email_details.date.strftime("%Y-%m-%d %H:%M:%S %Z")}
{f"Attachments: {', '.join(email_details.attachments)}" if email_details.attachments else "No attachments"}

Content:
{email_details.body}"""
        
        return response_text
        
    except Exception as e:
        error_message = f"Error retrieving email details: {str(e)}"
        logger.error(error_message)
        return error_message


@app.tool()
async def check_email_config() -> str:
    """
    Check the configuration status of email accounts.
    
    Returns:
        Status information about email account configurations
    """
    status = {
        "yahoo": "Not configured",
    }
    
    # Check Yahoo connection
    try:
        await yahoo_service.check_connection()
        status["yahoo"] = "Connected"
    except Exception as e:
        status["yahoo"] = f"Error: {str(e)}"
    
    response_text = f"""Email Account Configuration Status:

Yahoo: {status["yahoo"]}

Required Environment Variables:
- YAHOO_EMAIL: {"✓ Set" if os.getenv("YAHOO_EMAIL") else "✗ Missing"}
- YAHOO_APP_PASSWORD: {"✓ Set" if os.getenv("YAHOO_APP_PASSWORD") else "✗ Missing"}

Setup Instructions:
1. Generate app password at https://login.yahoo.com/account/security
2. Set the environment variables in your .env file"""
    
    return response_text


if __name__ == "__main__":
    # Run the FastMCP server
    app.run()