"""Type definitions for email search functionality."""

from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class EmailSearchParams(BaseModel):
    """Parameters for email search."""
    
    keywords: str = Field(description="Keywords to search for in email content, subject, or sender")
    provider: Literal["yahoo"] = Field(
        default="yahoo", 
        description="Email provider to search in - only Yahoo supported"
    )
    date_from: Optional[str] = Field(
        default=None, 
        description="Start date in YYYY-MM-DD format"
    )
    date_to: Optional[str] = Field(
        default=None, 
        description="End date in YYYY-MM-DD format"
    )
    max_results: int = Field(
        default=10, 
        ge=1, 
        le=50, 
        description="Maximum number of results to return (1-50)"
    )
    include_attachments: bool = Field(
        default=False, 
        description="Whether to include emails with attachments"
    )
    folder: Optional[str] = Field(
        default="INBOX", 
        description="Email folder to search in (e.g., 'INBOX', 'Sent', 'Drafts', 'ALL' for all folders)"
    )


class EmailSearchResult(BaseModel):
    """Result of an email search."""
    
    id: str = Field(description="Unique email ID")
    subject: str = Field(description="Email subject")
    sender: str = Field(description="Email sender")
    recipients: List[str] = Field(description="Email recipients")
    date: datetime = Field(description="Email date")
    snippet: str = Field(description="Email preview snippet")
    has_attachments: bool = Field(description="Whether email has attachments")
    provider: Literal["gmail", "yahoo"] = Field(description="Email provider")
    folder: str = Field(description="Email folder name")


class EmailDetails(EmailSearchResult):
    """Detailed email information."""
    
    body: str = Field(description="Full email body content")
    attachments: Optional[List[str]] = Field(
        default=None, 
        description="List of attachment filenames"
    )


class EmailClassificationResult(BaseModel):
    """Result of email classification."""
    
    email_id: str = Field(description="Unique email ID")
    category: Literal[
        "job_applications", 
        "hotel_airline_bookings", 
        "shopping_receipts", 
        "friends_emails", 
        "linkedin_notifications", 
        "promotions", 
        "hockey_team", 
        "unknown"
    ] = Field(description="Classification category")
    confidence: float = Field(
        ge=0.0, 
        le=1.0, 
        description="Confidence score for classification (0.0 to 1.0)"
    )
    reasoning: Optional[str] = Field(
        default=None, 
        description="Brief explanation of the classification"
    )


class EmailMoveResult(BaseModel):
    """Result of email move operation."""
    
    email_id: str = Field(description="Unique email ID")
    source_folder: str = Field(description="Source folder name")
    destination_folder: str = Field(description="Destination folder name")
    success: bool = Field(description="Whether the move was successful")
    error_message: Optional[str] = Field(
        default=None, 
        description="Error message if move failed"
    )