"""Yahoo Mail service for email search functionality."""

import os
import logging
from typing import List, Optional
from datetime import datetime, timezone
import imaplib
import email
import email.utils
import email.message
from email.header import decode_header
import re

from ..types import EmailSearchParams, EmailSearchResult, EmailDetails

logger = logging.getLogger(__name__)


class YahooService:
    """Service for interacting with Yahoo Mail via IMAP."""
    
    def __init__(self) -> None:
        """Initialize Yahoo service."""
        self.connection: Optional[imaplib.IMAP4_SSL] = None
    
    async def check_connection(self) -> None:
        """Check if Yahoo connection is properly configured."""
        if not all([os.getenv("YAHOO_EMAIL"), os.getenv("YAHOO_APP_PASSWORD")]):
            raise ValueError(
                "Yahoo credentials not configured. "
                "Please set YAHOO_EMAIL and YAHOO_APP_PASSWORD environment variables."
            )
        
        try:
            await self._connect()
            # Test the connection
            self.connection.list()
            await self._disconnect()
        except Exception as e:
            raise ValueError(f"Failed to connect to Yahoo Mail: {str(e)}")
    
    async def _connect(self) -> None:
        """Connect to Yahoo Mail IMAP server."""
        if self.connection is not None:
            return
        
        try:
            self.connection = imaplib.IMAP4_SSL("imap.mail.yahoo.com", 993)
            self.connection.login(
                os.getenv("YAHOO_EMAIL", ""),
                os.getenv("YAHOO_APP_PASSWORD", "")
            )
        except Exception as e:
            raise ValueError(f"Failed to connect to Yahoo Mail: {str(e)}")
    
    async def _disconnect(self) -> None:
        """Disconnect from Yahoo Mail IMAP server."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except Exception:
                pass
            finally:
                self.connection = None
    
    async def search_emails(self, params: EmailSearchParams) -> List[EmailSearchResult]:
        """Search emails in Yahoo Mail."""
        await self._connect()
        
        try:
            # Select INBOX
            self.connection.select("INBOX")
            
            # Build search criteria
            search_criteria = []
            
            # Add keyword search (search in subject and body)
            if params.keywords:
                # IMAP search for keywords in subject or body
                search_criteria.append(f'OR SUBJECT "{params.keywords}" BODY "{params.keywords}"')
            
            # Add date filters
            if params.date_from:
                date_obj = datetime.strptime(params.date_from, "%Y-%m-%d")
                search_criteria.append(f'SINCE "{date_obj.strftime("%d-%b-%Y")}"')
            
            if params.date_to:
                date_obj = datetime.strptime(params.date_to, "%Y-%m-%d")
                search_criteria.append(f'BEFORE "{date_obj.strftime("%d-%b-%Y")}"')
            
            # Perform search
            search_query = " ".join(search_criteria) if search_criteria else "ALL"
            
            status, message_ids = self.connection.search(None, search_query)
            if status != "OK" or not message_ids[0]:
                return []
            
            # Get message IDs and limit results
            ids = message_ids[0].split()
            limited_ids = ids[-params.max_results:]  # Get most recent emails
            
            # Get details for each message
            email_results = []
            for msg_id in reversed(limited_ids):  # Reverse to get newest first
                try:
                    email_result = await self._get_message_details(msg_id.decode(), snippet_only=True)
                    if email_result:
                        # Filter by attachments if requested
                        if params.include_attachments and not email_result.has_attachments:
                            continue
                        email_results.append(email_result)
                except Exception as e:
                    logger.warning(f"Failed to get details for message {msg_id}: {e}")
                    continue
            
            return email_results
            
        except Exception as e:
            raise ValueError(f"Yahoo search failed: {str(e)}")
        finally:
            await self._disconnect()
    
    async def get_email_details(self, email_id: str) -> EmailDetails:
        """Get detailed information about a specific email."""
        await self._connect()
        
        try:
            # Select INBOX first
            self.connection.select("INBOX")
            
            email_result = await self._get_message_details(email_id, snippet_only=False)
            if not email_result:
                raise ValueError("Email not found")
            
            return email_result
            
        except Exception as e:
            raise ValueError(f"Failed to get Yahoo email details: {str(e)}")
        finally:
            await self._disconnect()
    
    async def _get_message_details(self, message_id: str, snippet_only: bool = False) -> Optional[EmailDetails]:
        """Get details for a specific message."""
        try:
            # Fetch message
            status, message_data = self.connection.fetch(message_id, "(RFC822)")
            if status != "OK" or not message_data[0]:
                return None
            
            # Parse email
            raw_email = message_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract headers
            subject = self._decode_header(email_message.get("Subject", "(No Subject)"))
            sender = self._decode_header(email_message.get("From", "Unknown"))
            to_header = self._decode_header(email_message.get("To", ""))
            recipients = [addr.strip() for addr in to_header.split(",") if addr.strip()]
            
            # Parse date
            date_str = email_message.get("Date", "")
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_str)
                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            except Exception:
                parsed_date = datetime.now(timezone.utc)
            
            # Extract body and attachments
            body = ""
            attachments = []
            
            if not snippet_only:
                body, attachments = self._extract_body_and_attachments(email_message)
            else:
                # Get a snippet for search results
                body = self._extract_text_snippet(email_message)
            
            return EmailDetails(
                id=message_id,
                subject=subject,
                sender=sender,
                recipients=recipients,
                date=parsed_date,
                snippet=body[:200] + ("..." if len(body) > 200 else ""),
                has_attachments=len(attachments) > 0,
                provider="yahoo",
                body=body if not snippet_only else body[:200] + ("..." if len(body) > 200 else ""),
                attachments=attachments if attachments else None
            )
            
        except Exception as e:
            logger.error(f"Error getting message details for {message_id}: {e}")
            return None
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header value."""
        if not header_value:
            return ""
        
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding, errors="ignore")
                    else:
                        decoded_string += part.decode("utf-8", errors="ignore")
                else:
                    decoded_string += part
            
            return decoded_string.strip()
        except Exception:
            return header_value
    
    def _extract_body_and_attachments(self, email_message: email.message.Message) -> tuple[str, List[str]]:
        """Extract body content and attachment names from email message."""
        body_parts = []
        attachments = []
        
        def process_part(part: email.message.Message) -> None:
            content_type = part.get_content_type()
            content_disposition = part.get_content_disposition()
            filename = part.get_filename()
            
            # Check for attachments
            if filename:
                attachments.append(filename)
            elif content_disposition == "attachment":
                # Attachment without filename
                attachments.append("unnamed_attachment")
            
            # Extract text content
            if content_type == "text/plain" and content_disposition != "attachment":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="ignore")
                        body_parts.append(text)
                except Exception:
                    pass
            elif content_type == "text/html" and not body_parts and content_disposition != "attachment":
                # Use HTML as fallback if no plain text
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html = payload.decode(charset, errors="ignore")
                        # Simple HTML tag removal
                        clean_text = re.sub(r"<[^>]+>", "", html)
                        body_parts.append(clean_text.strip())
                except Exception:
                    pass
        
        if email_message.is_multipart():
            for part in email_message.walk():
                process_part(part)
        else:
            process_part(email_message)
        
        return "\n".join(body_parts), attachments
    
    def _extract_text_snippet(self, email_message: email.message.Message) -> str:
        """Extract a text snippet from email message for search results."""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            return payload.decode(charset, errors="ignore")
                    except Exception:
                        continue
        else:
            if email_message.get_content_type() == "text/plain":
                try:
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        charset = email_message.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="ignore")
                except Exception:
                    pass
        
        return "Preview not available"