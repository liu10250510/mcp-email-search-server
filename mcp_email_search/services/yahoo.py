"""Simplified Yahoo Mail service for email search and classification."""

import os
import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import imaplib
import email
import email.utils
import email.message
from email.header import decode_header
import re

# Add parent directory to path for imports
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))
from mcp_email_search.types import EmailSearchParams, EmailSearchResult, EmailDetails
import dotenv

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


class YahooService:
    """Simplified service for Yahoo Mail operations."""
    
    def __init__(self) -> None:
        """Initialize Yahoo service."""
        self.connection: Optional[imaplib.IMAP4_SSL] = None
    
    async def check_connection(self) -> None:
        """Check if Yahoo connection works."""
        if not all([os.getenv("YAHOO_EMAIL"), os.getenv("YAHOO_APP_PASSWORD")]):
            raise ValueError(
                "Yahoo credentials not configured. "
                "Please set YAHOO_EMAIL and YAHOO_APP_PASSWORD environment variables."
            )
        
        try:
            await self._connect()
            # Test basic operations
            self.connection.list()
            await self._disconnect()
        except Exception as e:
            raise ValueError(f"Failed to connect to Yahoo Mail: {str(e)}")
    
    async def search_emails(self, params: EmailSearchParams) -> List[EmailSearchResult]:
        """Search emails and return consistent IDs (optimized for speed)."""
        await self._connect()
        
        try:
            # Select folder
            folder = params.folder or "INBOX"
            status, _ = self.connection.select(folder)
            if status != "OK":
                raise ValueError(f"Could not select folder: {folder}")
            
            # For speed, limit search scope and use simple criteria
            search_criteria = []
            
            # Only add keyword search if it's not wildcard
            if params.keywords and params.keywords.strip() and params.keywords != "*":
                # Use simpler search - just subject for speed
                search_criteria.append(f'SUBJECT "{params.keywords}"')
            
            # Limit date range for faster search
            if params.date_from:
                try:
                    date_obj = datetime.strptime(params.date_from, "%Y-%m-%d")
                    search_criteria.append(f'SINCE "{date_obj.strftime("%d-%b-%Y")}"')
                except ValueError:
                    pass
            else:
                # If no date specified, search only recent emails
                recent_date = datetime.now() - timedelta(days=7)
                search_criteria.append(f'SINCE "{recent_date.strftime("%d-%b-%Y")}"')
            
            if params.date_to:
                try:
                    date_obj = datetime.strptime(params.date_to, "%Y-%m-%d")
                    date_obj += timedelta(days=1)
                    search_criteria.append(f'BEFORE "{date_obj.strftime("%d-%b-%Y")}"')
                except ValueError:
                    pass
            
            # Build search query
            search_query = " ".join(search_criteria) if search_criteria else "ALL"
            print(f"Search query: {search_query}")  # Debug info
            
            # Use simple UID search (skip SORT for speed)
            status, message_ids = self.connection.uid("search", None, search_query)
            
            if status != "OK" or not message_ids[0]:
                print("No messages found")
                return []
            
            uids = message_ids[0].split()
            print(f"Found {len(uids)} UIDs, processing first {params.max_results}")
            
            # Limit results for speed and reverse for newest first
            limited_uids = list(reversed(uids))[:params.max_results]
            
            # Batch fetch for better performance
            results = []
            for i, uid_bytes in enumerate(limited_uids):
                uid = uid_bytes.decode() if isinstance(uid_bytes, bytes) else str(uid_bytes)
                print(f"Processing email {i+1}/{len(limited_uids)}: UID {uid}")
                
                # Get basic email info quickly - Message-ID will be set by parser
                email_data = await self._get_email_by_uid_fast(uid, folder)
                if email_data:
                    # Store UID mapping for later use in moves (since Message-ID is unique identifier)
                    print(f"Found email with Message-ID: {email_data.id}")
                    results.append(email_data)
            
            print(f"Successfully processed {len(results)} emails")
            return results
            
        except Exception as e:
            raise ValueError(f"Search failed: {str(e)}")
        finally:
            await self._disconnect()
    
    async def _get_email_by_uid_fast(self, uid: str, folder: str) -> Optional[EmailSearchResult]:
        """Fast email fetch - only headers for search results."""
        try:
            # Fetch essential headers including Message-ID for speed
            status, message_data = self.connection.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
            if status != "OK" or not message_data[0]:
                return None
            
            # Parse headers quickly
            email_message = email.message_from_bytes(message_data[0][1])
            
            # Extract Message-ID (UUID) - this is the unique identifier
            message_id = email_message.get("Message-ID", "").strip("<>")
            if not message_id:
                # Fallback: generate a unique ID based on subject + sender + date
                subject_part = email_message.get("Subject", "")[:50]
                sender_part = email_message.get("From", "")[:50]
                date_part = email_message.get("Date", "")[:50]
                message_id = f"fallback_{hash(subject_part + sender_part + date_part)}"
            
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
            
            return EmailSearchResult(
                id=message_id,  # Use Message-ID as unique identifier
                subject=subject,
                sender=sender,
                recipients=recipients,
                date=parsed_date,
                snippet="[Loading snippet...]",  # Skip body for speed
                has_attachments=False,  # Skip attachment check for speed
                provider="yahoo",
                folder=folder
            )
            
        except Exception as e:
            logger.error(f"Error getting email by UID {uid}: {e}")
            return None
    
    async def get_email_details(self, message_id: str, folder: str = "INBOX") -> EmailDetails:
        """Get full email details using Message-ID."""
        await self._connect()
        
        try:
            # Search for email by Message-ID across specified folder
            # Try both with and without angle brackets as different servers handle them differently
            search_queries = [
                f'HEADER "Message-ID" "{message_id}"',
                f'HEADER "Message-ID" "<{message_id}>"'
            ]
            
            # Try to search in the specified folder first
            status, _ = self.connection.select(folder)
            if status == "OK":
                for search_query in search_queries:
                    status, message_ids = self.connection.uid("search", None, search_query)
                    if status == "OK" and message_ids[0]:
                        uids = message_ids[0].split()
                        if uids:
                            uid = uids[0].decode() if isinstance(uids[0], bytes) else str(uids[0])
                            email_data = await self._get_email_by_uid(uid, folder, snippet_only=False)
                            if email_data:
                                return email_data
            
            # If not found in specified folder, search in INBOX
            if folder != "INBOX":
                status, _ = self.connection.select("INBOX")
                if status == "OK":
                    for search_query in search_queries:
                        status, message_ids = self.connection.uid("search", None, search_query)
                        if status == "OK" and message_ids[0]:
                            uids = message_ids[0].split()
                            if uids:
                                uid = uids[0].decode() if isinstance(uids[0], bytes) else str(uids[0])
                                email_data = await self._get_email_by_uid(uid, "INBOX", snippet_only=False)
                                if email_data:
                                    return email_data
            
            raise ValueError(f"Could not find email with Message-ID: {message_id}")
            
        except Exception as e:
            raise ValueError(f"Failed to get email details: {str(e)}")
        finally:
            await self._disconnect()
    
    async def move_email(self, message_id: str, destination_folder: str) -> bool:
        """Move email to destination folder using Message-ID."""
        await self._connect()
        
        try:
            print(f"Moving email with Message-ID: {message_id} to folder: {destination_folder}")
            
            # Find the email by Message-ID across all folders
            # Try both with and without angle brackets as different servers handle them differently
            search_queries = [
                f'HEADER "Message-ID" "{message_id}"',
                f'HEADER "Message-ID" "<{message_id}>"'
            ]
            
            # Search in common folders to find the email
            folders_to_search = ["INBOX", "Sent", "Drafts", "Spam", "Trash"]
            source_folder = None
            uid = None
            
            for folder in folders_to_search:
                try:
                    print(f"Searching in folder: {folder}")
                    status, _ = self.connection.select(folder)
                    if status == "OK":
                        for search_query in search_queries:
                            status, message_ids = self.connection.uid("search", None, search_query)
                            if status == "OK" and message_ids[0]:
                                uids = message_ids[0].split()
                                if uids:
                                    uid = uids[0].decode() if isinstance(uids[0], bytes) else str(uids[0])
                                    source_folder = folder
                                    print(f"Found email in {folder} with UID: {uid}")
                                    break
                        if uid:  # If found, break outer loop too
                            break
                except Exception as e:
                    print(f"Error searching in folder {folder}: {e}")
                    continue
            
            if not uid or not source_folder:
                print(f"Could not find email with Message-ID: {message_id}")
                return False
            
            # Validate UID is numeric
            try:
                int(uid)
            except ValueError:
                print(f"Error: UID {uid} is not numeric")
                return False
            
            # Ensure destination folder exists
            await self._ensure_folder_exists(destination_folder)
            
            # Select source folder (may already be selected from search)
            print(f"Selecting source folder: {source_folder}")
            status, response = self.connection.select(source_folder)
            if status != "OK":
                print(f"Error selecting source folder {source_folder}: {response}")
                return False
            
            # Move email using UID method
            print(f"Copying UID {uid} to {destination_folder}")
            status, response = self.connection.uid("copy", uid, destination_folder)
            if status != "OK":
                print(f"UID COPY failed: {response}")
                return False
            
            print(f"Marking UID {uid} as deleted")
            status, response = self.connection.uid("store", uid, "+FLAGS", "\\Deleted")
            if status != "OK":
                print(f"UID STORE failed: {response}")
                return False
            
            # Expunge to complete the move
            print("Expunging deleted messages")
            self.connection.expunge()
            print(f"✅ Successfully moved email {message_id} to {destination_folder}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to move email {message_id}: {e}")
            logger.error(f"Failed to move email {message_id}: {e}")
            return False
        finally:
            await self._disconnect()
    
    async def create_classification_folders(self) -> List[str]:
        """Create folders for email classification."""
        folders = [
            "job_applications",
            "hotel_airline_bookings", 
            "bank",
            "shopping_receipts",
            "friends_emails",
            "linkedin_notifications",
            "promotions",
            "hockey_team",
            "unknown"
        ]
        
        await self._connect()
        
        try:
            created = []
            for folder in folders:
                await self._ensure_folder_exists(folder)
                created.append(folder)
            return created
        except Exception as e:
            logger.error(f"Failed to create folders: {e}")
            return []
        finally:
            await self._disconnect()
    
    async def list_folders(self) -> List[str]:
        """List available email folders in Yahoo account."""
        try:
            await self._connect()
            
            # Get list of folders from IMAP
            typ, folder_list = self.connection.list()
            if typ != 'OK':
                logger.error("Failed to list folders")
                return ["INBOX"]  # Return default folder on error
            
            folders = []
            for folder_bytes in folder_list:
                if folder_bytes:
                    # Parse folder name from IMAP response
                    folder_str = folder_bytes.decode('utf-8')
                    # Extract folder name (format: '(\\HasNoChildren) "/" "INBOX"')
                    parts = folder_str.split('"')
                    if len(parts) >= 3:
                        folder_name = parts[-2]  # Get the folder name
                        folders.append(folder_name)
            
            # Ensure we have at least basic folders
            if not folders:
                folders = ["INBOX", "Sent", "Drafts", "Trash"]
            
            return sorted(folders)
            
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            # Return common Yahoo folders as fallback
            return ["INBOX", "Sent", "Drafts", "Trash", "Spam"]
        finally:
            await self._disconnect()
    
    # Private helper methods
    
    async def _connect(self) -> None:
        """Connect to Yahoo IMAP."""
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
        """Disconnect from Yahoo IMAP."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except Exception:
                pass
            finally:
                self.connection = None
    
    async def _get_email_by_uid(self, uid: str, folder: str, snippet_only: bool = False) -> Optional[EmailSearchResult]:
        """Get email data by UID."""
        try:
            if snippet_only:
                # For search results, fetch headers including Message-ID and small body for speed
                status, message_data = self.connection.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] BODY.PEEK[1]<0.300>)")
            else:
                # For full details, fetch complete email
                status, message_data = self.connection.uid("fetch", uid, "(RFC822)")
                
            if status != "OK" or not message_data[0]:
                return None
            
            return self._parse_email_message(message_data[0][1], folder, snippet_only)
            
        except Exception as e:
            logger.error(f"Error getting email by UID {uid}: {e}")
            return None
    
    async def _get_email_by_sequence(self, sequence: str, folder: str, snippet_only: bool = False) -> Optional[EmailSearchResult]:
        """Get email data by sequence number (legacy support)."""
        try:
            # Fetch email by sequence number
            status, message_data = self.connection.fetch(sequence, "(RFC822)")
            if status != "OK" or not message_data[0]:
                return None
            
            return self._parse_email_message(message_data[0][1], folder, snippet_only)
            
        except Exception as e:
            logger.error(f"Error getting email by sequence {sequence}: {e}")
            return None
    
    def _parse_email_message(self, raw_email: bytes, folder: str, snippet_only: bool) -> Optional[EmailSearchResult]:
        """Parse raw email message into EmailSearchResult or EmailDetails."""
        try:
            email_message = email.message_from_bytes(raw_email)
            
            # Extract Message-ID (UUID) - this is the unique identifier
            message_id = email_message.get("Message-ID", "").strip("<>")
            if not message_id:
                # Fallback: generate a unique ID based on subject + sender + date
                subject_part = email_message.get("Subject", "")[:50]
                sender_part = email_message.get("From", "")[:50]
                date_part = email_message.get("Date", "")[:50]
                message_id = f"fallback_{hash(subject_part + sender_part + date_part)}"
            
            # Extract basic info
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
            
            # Extract body
            body = self._extract_body(email_message)
            
            # Check for attachments
            has_attachments = self._has_attachments(email_message)
            
            if snippet_only:
                # Return EmailSearchResult with Message-ID
                return EmailSearchResult(
                    id=message_id,  # Use Message-ID as unique identifier
                    subject=subject,
                    sender=sender,
                    recipients=recipients,
                    date=parsed_date,
                    snippet=body[:200] + ("..." if len(body) > 200 else ""),
                    has_attachments=has_attachments,
                    provider="yahoo",
                    folder=folder
                )
            else:
                # Return EmailDetails with Message-ID
                attachments = self._get_attachment_names(email_message) if has_attachments else None
                return EmailDetails(
                    id=message_id,  # Use Message-ID as unique identifier
                    subject=subject,
                    sender=sender,
                    recipients=recipients,
                    date=parsed_date,
                    snippet=body[:200] + ("..." if len(body) > 200 else ""),
                    has_attachments=has_attachments,
                    provider="yahoo",
                    folder=folder,
                    body=body,
                    attachments=attachments
                )
                
        except Exception as e:
            logger.error(f"Error parsing email message: {e}")
            return None
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header."""
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
    
    def _extract_body(self, email_message: email.message.Message) -> str:
        """Extract text body from email."""
        body_parts = []
        
        def extract_text(part):
            content_type = part.get_content_type()
            if content_type == "text/plain" and part.get_content_disposition() != "attachment":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        text = payload.decode(charset, errors="ignore")
                        body_parts.append(text)
                except Exception:
                    pass
        
        if email_message.is_multipart():
            for part in email_message.walk():
                extract_text(part)
        else:
            extract_text(email_message)
        
        return "\n".join(body_parts) if body_parts else "No text content"
    
    def _has_attachments(self, email_message: email.message.Message) -> bool:
        """Check if email has attachments."""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_filename() or part.get_content_disposition() == "attachment":
                    return True
        return False
    
    def _get_attachment_names(self, email_message: email.message.Message) -> List[str]:
        """Get list of attachment names."""
        attachments = []
        if email_message.is_multipart():
            for part in email_message.walk():
                filename = part.get_filename()
                if filename:
                    attachments.append(filename)
                elif part.get_content_disposition() == "attachment":
                    attachments.append("unnamed_attachment")
        return attachments
    
    async def _ensure_folder_exists(self, folder_name: str) -> None:
        """Ensure folder exists, create if needed."""
        try:
            # Check if folder exists
            status, folders = self.connection.list('""', folder_name)
            if status == "OK" and folders and folders[0]:
                return
            
            # Create folder
            status, _ = self.connection.create(folder_name)
            if status != "OK":
                logger.warning(f"Could not create folder {folder_name}")
                
        except Exception as e:
            logger.warning(f"Error ensuring folder {folder_name} exists: {e}")


if __name__ == "__main__":
    # Simple test when run directly
    import asyncio
    
    async def test():
        service = YahooService()
        try:
            print("Testing connection...")
            await service.check_connection()
            print("✅ Connection successful.")
            
            print("Searching recent emails (optimized for speed)...")
            search_params = EmailSearchParams(
                keywords="",  # No keyword search for speed
                provider="yahoo",
                folder="INBOX",
                date_from="2025-09-30",  # Just today/yesterday
                max_results=3  # Small number for testing
            )
            results = await service.search_emails(search_params)
            print(f"✅ Found {len(results)} emails.")
            
            for i, email in enumerate(results, 1):
                print(f"{i}. {email.subject} from {email.sender}")
                print(f"   Date: {email.date}")
                print(f"   Snippet: {email.snippet[:100]}...")
                print()
                
        except KeyboardInterrupt:
            print("\n⚠️ Test interrupted by user (Ctrl+C)")
        except Exception as e:
            print(f"❌ Error during test: {e}")
    
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("\n⚠️ Test stopped by user")