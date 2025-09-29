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
    
    async def list_folders(self) -> List[str]:
        """List available email folders."""
        await self._connect()
        
        try:
            # Ensure connection is active
            if self.connection is None:
                return ["INBOX"]
                
            status, folders = self.connection.list()
            if status != "OK":
                return ["INBOX"]
            
            folder_names = []
            for folder in folders:
                # Parse folder name from IMAP response
                folder_str = folder.decode() if isinstance(folder, bytes) else folder
                # Extract folder name (format: '(\\HasNoChildren) "." "INBOX"')
                match = re.search(r'"([^"]*)"$', folder_str)
                if match:
                    folder_name = match.group(1)
                    folder_names.append(folder_name)
            
            return folder_names if folder_names else ["INBOX"]
            
        except Exception as e:
            logger.warning(f"Failed to list folders: {e}")
            return ["INBOX"]
        finally:
            await self._disconnect()
    
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
            # Determine which folders to search
            folders_to_search = []
            if params.folder == "ALL":
                # Search all folders - get list without disconnecting
                if self.connection is None:
                    await self._connect()
                try:
                    status, folders = self.connection.list()
                    if status == "OK" and folders:
                        for folder in folders:
                            folder_str = folder.decode() if isinstance(folder, bytes) else folder
                            match = re.search(r'"([^"]*)"$', folder_str)
                            if match:
                                folders_to_search.append(match.group(1))
                    if not folders_to_search:
                        folders_to_search = ["INBOX"]
                except Exception as e:
                    logger.warning(f"Failed to list folders during search: {e}")
                    folders_to_search = ["INBOX"]
            else:
                # Search specific folder (default is INBOX)
                folders_to_search = [params.folder or "INBOX"]
            
            all_email_results = []
            
            # Search each folder
            for folder in folders_to_search:
                try:
                    # Ensure connection is still active
                    if self.connection is None:
                        await self._connect()
                    
                    # Select folder
                    status, _ = self.connection.select(folder)
                    if status != "OK":
                        logger.warning(f"Could not select folder: {folder}")
                        continue
                    
                    # Build search criteria
                    search_criteria = []
                    
                    # Add keyword search (search in subject and body)
                    if params.keywords and params.keywords.strip():
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
                    
                    # Ensure connection is still active before search
                    if self.connection is None:
                        await self._connect()
                        status, _ = self.connection.select(folder)
                        if status != "OK":
                            continue
                    
                    status, message_ids = self.connection.search(None, search_query)
                    if status != "OK" or not message_ids[0]:
                        continue
                    
                    # Get message IDs and limit per folder to avoid timeout
                    ids = message_ids[0].split()
                    
                    # Limit emails per folder when searching all folders
                    folder_limit = params.max_results if params.folder != "ALL" else min(params.max_results, 20)
                    limited_ids = ids[-folder_limit:]  # Get most recent emails from this folder
                    
                    # Get details for each message
                    for msg_id in reversed(limited_ids):  # Reverse to get newest first
                        try:
                            # Break early if we have enough results across all folders
                            if len(all_email_results) >= params.max_results:
                                break
                                
                            email_result = await self._get_message_details(msg_id.decode(), snippet_only=True, folder=folder)
                            if email_result:
                                # Filter by attachments if requested
                                if params.include_attachments and not email_result.has_attachments:
                                    continue
                                all_email_results.append(email_result)
                        except Exception as e:
                            logger.warning(f"Failed to get details for message {msg_id} in folder {folder}: {e}")
                            continue
                            
                    # Break early if we have enough results
                    if len(all_email_results) >= params.max_results:
                        break
                            
                except Exception as e:
                    logger.warning(f"Failed to search folder {folder}: {e}")
                    continue
            
            # Sort all results by date (newest first) and limit
            all_email_results.sort(key=lambda x: x.date, reverse=True)
            return all_email_results[:params.max_results]
            
        except Exception as e:
            raise ValueError(f"Yahoo search failed: {str(e)}")
        finally:
            await self._disconnect()
    
    async def get_email_details(self, email_id: str, folder: str = "INBOX") -> EmailDetails:
        """Get detailed information about a specific email."""
        await self._connect()
        
        try:
            # Try the specified folder first
            folders_to_try = [folder] if folder != "ALL" else await self.list_folders()
            
            for folder_name in folders_to_try:
                try:
                    # Select folder
                    status, _ = self.connection.select(folder_name)
                    if status != "OK":
                        continue
                    
                    email_result = await self._get_message_details(email_id, snippet_only=False, folder=folder_name)
                    if email_result:
                        return email_result
                        
                except Exception as e:
                    logger.warning(f"Failed to get email {email_id} from folder {folder_name}: {e}")
                    continue
            
            raise ValueError("Email not found in any folder")
            
        except Exception as e:
            raise ValueError(f"Failed to get Yahoo email details: {str(e)}")
        finally:
            await self._disconnect()
    
    async def _get_message_details(self, message_id: str, snippet_only: bool = False, folder: str = "INBOX") -> Optional[EmailDetails]:
        """Get details for a specific message."""
        try:
            # Ensure connection is active
            if self.connection is None:
                return None
            
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
                folder=folder,
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