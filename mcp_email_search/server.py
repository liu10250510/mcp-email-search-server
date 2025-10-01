#!/usr/bin/env python3
"""Email Search MCP Server - Main server implementation using FastMCP."""

import asyncio
import logging
import os
import sys
from typing import List, Optional, Dict, Any
import json

from dotenv import load_dotenv
from fastmcp import FastMCP

# Add parent directory to path for imports
from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

from mcp_email_search.types import EmailSearchParams, EmailSearchResult, EmailDetails, EmailClassificationResult, EmailMoveResult
from mcp_email_search.services.yahoo import YahooService

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


# Email Classification Prompt Templates
CLASSIFICATION_PROMPTS = {
    "categories": {
        "job_applications": "Job application emails and responses from employers (excluding LinkedIn alerts)",
        "hotel_airline_bookings": "Hotel and airline booking confirmations, itineraries, and travel-related emails (excluding promotions)",
        "bank": "Bank statements, transaction alerts, and financial notifications",
        "shopping_receipts": "Shopping receipts, order confirmations, and purchase notifications (excluding promotions)",
        "friends_emails": "Personal emails from friends and family",
        "linkedin_notifications": "LinkedIn job alerts, connection requests, and message notifications",
        "promotions": "Promotional emails, newsletters, marketing emails, and subscription emails",
        "hockey_team": "Hockey team communications from TeamSnap, Markham Majors, and related hockey activities",
        "unknown": "Emails that don't fit into the above categories"
    },
    
    "classification_prompt": """You are an expert email classifier. Analyze the following email and classify it into one of these categories, and have to be in the EXACT class shown below.:

CATEGORIES:
1. job_applications - Job application emails and responses from employers (excluding LinkedIn alerts)
2. hotel_airline_bookings - Hotel and airline booking confirmations, itineraries, and travel-related emails (excluding promotions)
3. bank - Bank statements, transaction alerts, and financial notifications
4. shopping_receipts - Shopping receipts, order confirmations, and purchase notifications (excluding promotions)
5. friends_emails - Personal emails from friends and family
6. linkedin_notifications - LinkedIn job alerts, connection requests, and message notifications
7. promotions - Promotional emails, newsletters, marketing emails, and subscription emails
8. hockey_team - Hockey team communications from TeamSnap, Markham Majors, and related hockey activities
9. unknown - Emails that don't fit into the above categories

EMAIL TO CLASSIFY:
Subject: {subject}
From: {sender}
Date: {date}
Message-ID: {message_id}
Content: {content}

CLASSIFICATION INSTRUCTIONS:
- Read the email content carefully
- Consider the sender domain and email patterns
- For hockey_team: Look for TeamSnap, Markham Majors, hockey schedules, team communications
- For job_applications: Exclude LinkedIn alerts, focus on direct employer communications
- For shopping_receipts: Exclude promotional content, focus on actual purchase confirmations
- Choose the most appropriate single category
- Provide a confidence score from 0.0 to 1.0

Respond in this exact JSON format:
{
    "category": "category_name",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why this email fits this category"
},


INSTRUCTIONS:
- Look at subject, sender, and content
- Choose the BEST matching category
- hockey_team: TeamSnap emails, Markham Majors team communications
- job_applications: Direct employer emails (exclude LinkedIn)
- shopping_receipts: Order confirmations, tracking (exclude marketing)

For each email, provide:
- category (exact name from list above)
- confidence (0.0 to 1.0)
- reasoning (brief explanation)"""
}

@app.resource("prompt://email-classification")
async def get_classification_prompt() -> str:
    """Get the email classification prompt."""
    return CLASSIFICATION_PROMPTS["classification_prompt"]


@app.tool()
async def search_emails(
    keywords: str,
    provider: str = "yahoo",
    date_from: str = None,
    date_to: str = None,
    max_results: int = 10,
    include_attachments: bool = False,
    folder: str = "INBOX",
) -> str:
    """
    Search emails across Yahoo accounts using keywords and date filters.
    
    Args:
        keywords: Keywords to search for in email content, subject, or sender
        provider: Email provider to search - only "yahoo" supported (default: "yahoo")
        date_from: Start date in YYYY-MM-DD format (optional)
        date_to: End date in YYYY-MM-DD format (optional)
        max_results: Maximum number of results to return (1-50, default: 10)
        include_attachments: Whether to include emails with attachments (default: False)
        folder: Email folder to search in - "INBOX", "Sent", "Drafts", or "ALL" for all folders (default: "INBOX")
    
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
            folder=folder,
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
- Folder: {search_params.folder}
- Date Range: {search_params.date_from or "any"} to {search_params.date_to or "any"}
- Max Results: {search_params.max_results}
- Include Attachments: {search_params.include_attachments}

Results:
"""
        
        if limited_results:
            for i, email in enumerate(limited_results, 1):
                response_text += f"""
{i}. [{email.provider.upper()}/{email.folder}] {email.subject}
   Message-ID: {email.id}
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
async def list_email_folders() -> str:
    """
    List available email folders in Yahoo account.
    
    Returns:
        Formatted string containing list of available folders
    """
    try:
        folders = await yahoo_service.list_folders()
        
        response_text = "Available Email Folders:\n\n"
        for i, folder in enumerate(folders, 1):
            response_text += f"{i}. {folder}\n"
        
        response_text += "\nYou can use these folder names in the 'folder' parameter when searching emails."
        response_text += "\nUse 'ALL' to search across all folders."
        
        return response_text
        
    except Exception as e:
        error_message = f"Error listing folders: {str(e)}"
        logger.error(error_message)
        return error_message


@app.tool()
async def get_email_details(email_id: str, provider: str, folder: str = "INBOX") -> str:
    """
    Get detailed content of a specific email by ID.
    
    Args:
        email_id: The unique ID of the email to retrieve
        provider: Email provider - only "yahoo" supported
        folder: Email folder to search in (default: "INBOX")
    
    Returns:
        Formatted string containing detailed email information
    """
    try:
        if provider != "yahoo":
            return "Error: Only 'yahoo' provider is supported"
        
        email_details: EmailDetails = await yahoo_service.get_email_details(email_id, folder)
        
        response_text = f"""Email Details [{provider.upper()}/{email_details.folder}]:

Subject: {email_details.subject}
From: {email_details.sender}
To: {', '.join(email_details.recipients)}
Date: {email_details.date.strftime("%Y-%m-%d %H:%M:%S %Z")}
Message-ID: {email_details.id}
Folder: {email_details.folder}
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


# Helper functions for email operations
def _validate_provider(provider: str) -> str:
    """Validate email provider."""
    if provider != "yahoo":
        return "Error: Only 'yahoo' provider is supported"
    return ""

def _validate_category(category: str) -> str:
    """Validate email classification category."""
    valid_categories = [
        "job_applications", "hotel_airline_bookings", "bank", "shopping_receipts", 
        "friends_emails", "linkedin_notifications", "promotions", 
        "hockey_team", "unknown"
    ]
    
    if category not in valid_categories:
        return f"Error: Invalid category '{category}'. Valid categories are: {', '.join(valid_categories)}"
    return ""

def _get_valid_categories() -> List[str]:
    """Get list of valid classification categories."""
    return [
        "job_applications", "hotel_airline_bookings", "bank", "shopping_receipts", 
        "friends_emails", "linkedin_notifications", "promotions", 
        "hockey_team", "unknown"
    ]


# Email Classification and Movement Tools

@app.tool()
async def get_email_for_classification(
    email_id: str,
    source_folder: str = "INBOX", 
    provider: str = "yahoo"
) -> str:
    """
    Get email content formatted for classification analysis.
    
    Use this to retrieve email details before classifying and moving emails.
    
    Args:
        email_id: The unique Message-ID of the email
        source_folder: Source folder where email currently resides (default: "INBOX")
        provider: Email provider - only "yahoo" supported (default: "yahoo")
    
    Returns:
        Email details formatted for classification with category options
    """
    try:
        # Validate provider
        error = _validate_provider(provider)
        if error:
            return error
        
        # Get the email details
        email_details = await yahoo_service.get_email_details(email_id, source_folder)
        
        if not email_details:
            return f"No email found with Message-ID: {email_id}"
        
        # Format email for classification
        response_text = f"📧 Email Ready for Classification\n"
        response_text += f"{'='*50}\n\n"
        response_text += f"Message-ID: {email_id}\n"
        response_text += f"Subject: {email_details.subject}\n"
        response_text += f"From: {email_details.sender}\n"
        response_text += f"Date: {email_details.date.strftime('%Y-%m-%d %H:%M')}\n"
        response_text += f"Folder: {email_details.folder}\n\n"
        
        response_text += f"Content Preview:\n"
        response_text += f"{'-'*30}\n"
        response_text += f"{email_details.body[:600]}{'...' if len(email_details.body) > 600 else ''}\n"
        response_text += f"{'-'*30}\n\n"
        
        response_text += f"📋 Available Categories:\n"
        for i, category in enumerate(_get_valid_categories(), 1):
            response_text += f"  {i}. {category}\n"
        
        response_text += f"\n💡 Next Steps:\n"
        response_text += f"  1. Analyze the email content above\n"
        response_text += f"  2. Choose the best category from the list\n"
        response_text += f"  3. Use: bulk_move_emails_by_classification with single email JSON\n"
        response_text += f"     Example: [{{'\"email_id\"': '\"{email_id}\"', '\"category\"': '\"CATEGORY_NAME\"', '\"confidence\"': 1.0}}]\n"
        
        return response_text
        
    except Exception as e:
        error_message = f"Error preparing email for classification: {str(e)}"
        logger.error(error_message)
        return error_message


@app.tool()
async def prepare_emails_for_classification(
    message_ids: str,
    provider: str = "yahoo"
) -> str:
    """
    Prepare multiple emails for classification using their Message-IDs.
    
    Use this with Message-IDs from search results to batch prepare emails for classification.
    
    Args:
        message_ids: JSON array of Message-IDs as string, e.g., ["msg-123@example.com", "msg-456@example.com"]
        provider: Email provider - only "yahoo" supported (default: "yahoo")
    
    Returns:
        Formatted string containing all email details ready for classification
    """
    try:
        # Validate provider
        error = _validate_provider(provider)
        if error:
            return error
        
        # Parse Message-IDs
        try:
            ids = json.loads(message_ids)
        except json.JSONDecodeError as e:
            return f"❌ Error: Invalid JSON format for message_ids\n   Details: {str(e)}"
        
        if not isinstance(ids, list):
            return "❌ Error: message_ids must be a JSON array"
        
        if not ids:
            return "⚠️ No Message-IDs provided"
        
        response_text = f"📧 Batch Email Classification Preparation\n"
        response_text += f"{'='*60}\n\n"
        response_text += f"Processing {len(ids)} emails for classification...\n\n"
        
        emails_data = []
        errors = []
        
        # Get details for each email
        for i, email_id in enumerate(ids, 1):
            try:
                print(f"Processing email {i}/{len(ids)}: {email_id}")
                email_details = await yahoo_service.get_email_details(email_id, "INBOX")
                if email_details:
                    emails_data.append({
                        "email_id": email_id,
                        "subject": email_details.subject,
                        "sender": email_details.sender,
                        "date": email_details.date,
                        "body": email_details.body
                    })
                else:
                    errors.append(f"Could not find email: {email_id}")
            except Exception as e:
                errors.append(f"Error processing {email_id}: {str(e)}")
        
        # Format results
        if emails_data:
            response_text += f"✅ Successfully prepared {len(emails_data)} emails\n"
            if errors:
                response_text += f"⚠️ {len(errors)} errors occurred\n"
            response_text += f"\n📋 Available Categories:\n"
            for i, category in enumerate(_get_valid_categories(), 1):
                response_text += f"  {i}. {category}\n"
            
            response_text += f"\n📧 Email Details for Classification:\n"
            response_text += f"{'-'*60}\n"
            
            for i, email in enumerate(emails_data, 1):
                response_text += f"\n{i}. Message-ID: {email['email_id']}\n"
                response_text += f"   Subject: {email['subject']}\n"
                response_text += f"   From: {email['sender']}\n"
                response_text += f"   Date: {email['date'].strftime('%Y-%m-%d %H:%M')}\n"
                response_text += f"   Content: {email['body'][:300]}{'...' if len(email['body']) > 300 else ''}\n"
                response_text += f"   {'-'*40}\n"
            
            response_text += f"\n💡 Next Steps:\n"
            response_text += f"  1. Analyze the emails above\n"
            response_text += f"  2. Create classification JSON for bulk_move_emails_by_classification\n"
            response_text += f"  3. Example format:\n"
            response_text += f"     [\n"
            for i, email in enumerate(emails_data[:2]):  # Show first 2 as examples
                response_text += f"       {{\"email_id\": \"{email['email_id']}\", \"category\": \"CATEGORY_NAME\", \"confidence\": 0.9}}"
                if i < len(emails_data[:2]) - 1:
                    response_text += ","
                response_text += "\n"
            if len(emails_data) > 2:
                response_text += f"       ... (add entries for remaining {len(emails_data) - 2} emails)\n"
            response_text += f"     ]\n"
        else:
            response_text += f"❌ No emails could be prepared\n"
        
        if errors:
            response_text += f"\n⚠️ Errors:\n"
            for error in errors:
                response_text += f"  • {error}\n"
        
        return response_text
        
    except Exception as e:
        error_message = f"Error preparing emails for classification: {str(e)}"
        logger.error(error_message)
        return error_message


@app.tool()
async def bulk_move_emails_by_classification(
    email_classifications: str,
    provider: str = "yahoo",
    min_confidence: float = 0.7
) -> str:
    """
    Move emails to their classified folders (single email or batch).
    
    Use this for processing email classifications with confidence filtering.
    For single emails, pass a JSON array with one item.
    
    Args:
        email_classifications: JSON string with format:
                              [{"email_id": "msg-123@example.com", "category": "job_applications", "confidence": 0.9}, ...]
                              For single email: [{"email_id": "msg-123", "category": "job_applications", "confidence": 1.0}]
        provider: Email provider - only "yahoo" supported (default: "yahoo")
        min_confidence: Minimum confidence threshold for moving emails (default: 0.7)
    
    Returns:
        Detailed status report of move operation
    """
    try:
        # Validate provider
        provider_error = _validate_provider(provider)
        if provider_error:
            return provider_error
        
        # Parse and validate input JSON
        try:
            classifications = json.loads(email_classifications)
        except json.JSONDecodeError as e:
            return f"❌ Error: Invalid JSON format\n   Details: {str(e)}"
        
        if not isinstance(classifications, list):
            return "❌ Error: email_classifications must be a JSON array"
        
        if not classifications:
            return "⚠️ No email classifications provided"
        
        # Process classifications
        results = []
        counters = {"success": 0, "error": 0, "skipped": 0}
        valid_moves = []
        
        # Validate each classification
        for i, classification in enumerate(classifications, 1):
            try:
                # Check required fields
                if not all(key in classification for key in ["email_id", "category"]):
                    results.append(f"❌ Item {i}: Missing required fields (email_id, category)")
                    counters["error"] += 1
                    continue
                
                email_id = classification["email_id"]
                category = classification["category"]
                confidence = classification.get("confidence", 0.0)
                
                # Validate confidence threshold
                if confidence < min_confidence:
                    results.append(f"⚠️ Message-ID: {email_id}")
                    results.append(f"   → Skipped - Low confidence ({confidence:.2f} < {min_confidence})")
                    counters["skipped"] += 1
                    continue
                
                # Validate category
                category_error = _validate_category(category)
                if category_error:
                    results.append(f"❌ Message-ID: {email_id}")
                    results.append(f"   → Invalid category '{category}'")
                    counters["error"] += 1
                    continue
                
                # Add to valid moves
                valid_moves.append((email_id, category, confidence))
                
            except Exception as e:
                results.append(f"❌ Item {i}: Processing error - {str(e)}")
                counters["error"] += 1
        
        # Execute bulk moves
        if valid_moves:
            # Ensure classification folders exist
            await yahoo_service.create_classification_folders()
            
            # Process each move
            for email_id, category, confidence in valid_moves:
                try:
                    success = await yahoo_service.move_email(email_id, category)
                    if success:
                        results.append(f"✅ Message-ID: {email_id}")
                        results.append(f"   → Moved to: {category} (confidence: {confidence:.2f})")
                        counters["success"] += 1
                    else:
                        results.append(f"❌ Message-ID: {email_id}")
                        results.append(f"   → Failed to move to: {category}")
                        counters["error"] += 1
                except Exception as e:
                    results.append(f"❌ Message-ID: {email_id}")
                    results.append(f"   → Error moving to {category}: {str(e)}")
                    counters["error"] += 1
        
        # Format comprehensive response
        total = counters["success"] + counters["error"] + counters["skipped"]
        response_text = f"📊 Bulk Email Move Results\n"
        response_text += f"{'='*50}\n\n"
        response_text += f"📈 Summary:\n"
        response_text += f"  • Total processed: {total}\n"
        response_text += f"  • ✅ Successfully moved: {counters['success']}\n"
        response_text += f"  • ❌ Errors: {counters['error']}\n"
        response_text += f"  • ⚠️ Skipped (low confidence): {counters['skipped']}\n"
        response_text += f"  • 🎯 Confidence threshold: {min_confidence}\n\n"
        
        if results:
            response_text += f"� Detailed Results:\n"
            for result in results:
                response_text += f"  {result}\n"
        else:
            response_text += "No operations performed.\n"
        
        return response_text
        
    except Exception as e:
        error_message = f"Error in bulk move operation: {str(e)}"
        logger.error(error_message)
        return f"❌ {error_message}"


# Remaining functions...


if __name__ == "__main__":
    # Run the FastMCP server
    app.run()