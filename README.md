# Email Search and Reorganizing MCP Server

A Model Context Protocol (MCP) server that enables AI agents to search, retrieve, and classify emails from Yahoo accounts using keywords, time filters, and intelligent email classification with flexible single or bulk email reorganizing processing options.

## Features

- 🔍 **Email Search**: Yahoo Mail support with comprehensive search capabilities
- 📁 **Folder Management**: Search specific folders (INBOX, Sent, Drafts) or all folders
- 📅 **Date range filtering**: Search emails within specific time periods  
- 🔑 **Keyword search**: Search in subject, body, and sender fields
- 📎 **Attachment filtering**: Find emails with or without attachments
- 🎯 **Email Classification**: Intelligent email classification workflow with flexible processing options
- 📤 **Email Movement**: Move emails to classified folders based on content analysis
- 📊 **Bulk Operations**: Process multiple emails with confidence-based filtering
- 🔐 **Secure authentication**: App Passwords for Yahoo
- 🛡️ **Privacy-focused**: All processing happens locally
- 🔒 **Message-ID System**: Reliable email identification using RFC-compliant Message-IDs

## Email Classification Workflow

The server provides a comprehensive email classification system that works with AI agents:

### How It Works

1. **Search & Retrieve**: Find emails using search tools
2. **Prepare for Analysis**: Use `get_email_for_classification` to format email content
3. **AI Classification**: AI agent analyzes email content and determines category
4. **Move Emails**: Use classification tools to move emails to appropriate folders

### Classification Tools

#### Step 1: Prepare Email for Classification
**Tool:** `get_email_for_classification`
- Retrieves email content formatted for AI analysis
- Shows available classification categories  
- Returns email details (subject, sender, content preview)
- Provides guidance for next steps

#### Step 2: Move Emails (Choose One Approach)

**Option A: Single Email Movement**
**Tool:** `move_email_thread`
- Moves one email at a time to its classified folder
- Validates category selection against available categories
- Creates classification folders automatically if they don't exist
- Returns success/failure status
- **Best for**: Processing individual emails or small batches

**Option B: Bulk Email Movement**
**Tool:** `bulk_move_emails_by_classification`
- Processes multiple email classifications at once
- Accepts JSON array of email classifications with confidence scores
- Confidence-based filtering (default minimum: 0.7)
- Comprehensive reporting with success/error/skipped counts
- **Best for**: Processing many emails efficiently after AI batch analysis

### Typical Workflow Examples

#### Approach A: Single Email Processing
```
1. User: "Find emails from last week about job applications"
   → Uses search_emails tool

2. User: "Prepare email MSG-ID-123@yahoo.com for classification"
   → Uses get_email_for_classification tool
   → Returns formatted email content and available categories

3. AI analyzes the email content and determines it's a job application

4. User: "Move this email to job_applications category"
   → Uses move_email_thread tool
   → Email is moved to job_applications folder
```

#### Approach B: Bulk Email Processing
```
1. User: "Find all unread emails from this month"
   → Uses search_emails tool
   → Returns list of emails with Message-IDs

2. User: "Prepare these 10 emails for classification"
   → Uses get_email_for_classification for each email

3. AI analyzes all emails and creates bulk classification JSON

4. User: "Process this bulk classification"
   → Uses bulk_move_emails_by_classification tool
   → All emails moved to appropriate folders with confidence filtering
```

### Classification Categories

The system supports 9 predefined categories:
- **job_applications**: Job application emails and employer responses
- **hotel_airline_bookings**: Travel bookings and itineraries  
- **bank**: Bank statements and financial notifications
- **shopping_receipts**: Order confirmations and purchase receipts
- **friends_emails**: Personal emails from friends and family
- **linkedin_notifications**: LinkedIn alerts and notifications
- **promotions**: Marketing emails and newsletters
- **hockey_team**: TeamSnap and Markham Majors team communications
- **unknown**: Emails that don't fit other categories

## Tools Available

### Core Search Tools

#### `search_emails`
Search emails from Yahoo accounts using keywords and filters.

**Parameters:**
- `keywords` (string): Keywords to search for in email content, subject, or sender
- `provider` (string): Email provider to search - "yahoo"
- `date_from` (string, optional): Start date in YYYY-MM-DD format
- `date_to` (string, optional): End date in YYYY-MM-DD format  
- `max_results` (int): Maximum results to return, 1-50 (default: 10)
- `include_attachments` (bool): Whether to include emails with attachments (default: false)
- `folder` (string): Email folder to search - "INBOX", "Sent", "Drafts", or "ALL" for all folders (default: "INBOX")

#### `get_email_details`
Get detailed content of a specific email by Message-ID.

**Parameters:**
- `email_id` (string): The unique Message-ID of the email to retrieve
- `provider` (string): Email provider - "yahoo"
- `folder` (string, optional): Email folder to search in (default: "INBOX")

#### `list_email_folders`
List all available email folders in your Yahoo account.

**Returns:** List of folder names that can be used in search operations.

#### `check_email_config`
Check the configuration status of email accounts and required environment variables.

### Email Classification Tools

#### `get_email_for_classification`
**Step 1:** Retrieve email content formatted for classification analysis.

**Parameters:**
- `email_id` (string): The unique Message-ID of the email
- `source_folder` (string, optional): Source folder where email resides (default: "INBOX")
- `provider` (string, optional): Email provider - "yahoo" (default: "yahoo")

**Returns:** Formatted email content with available categories and next steps.

#### `move_email_thread`
**Step 2:** Move a single email to its classified folder.

**Parameters:**
- `email_id` (string): The unique Message-ID of the email to move
- `category` (string): Classification category (must be exact name from available categories)
- `source_folder` (string, optional): Source folder where email resides (default: "INBOX")
- `provider` (string, optional): Email provider - "yahoo" (default: "yahoo")

**Returns:** Success/failure status message.

#### `bulk_move_emails_by_classification`
**Step 3:** Move multiple emails to their classified folders in batch.

**Parameters:**
- `email_classifications` (string): JSON array of email classifications:
  ```json
  [
    {"email_id": "msg-123@example.com", "category": "job_applications", "confidence": 0.9},
    {"email_id": "msg-456@example.com", "category": "shopping_receipts", "confidence": 0.8}
  ]
  ```
- `provider` (string, optional): Email provider - "yahoo" (default: "yahoo")
- `min_confidence` (float, optional): Minimum confidence threshold (default: 0.7)

**Returns:** Detailed status report with success/error/skipped counts.

### Classification Resource

#### `prompt://email-classification`
Provides the complete email classification prompt template for AI analysis.

**Returns:** Structured prompt with categories, instructions, and JSON response format.

## Setup Instructions

### 1. Installation

```bash
git clone <repository-url>
cd mcp_email_search
pip install -e .
```

### 2. Yahoo Setup (App Password)

1. Go to [Yahoo Account Security](https://login.yahoo.com/account/security)
2. Turn on 2-step verification if not already enabled
3. Generate an app password:
   - Click "Generate app password"
   - Select "Other app" and name it (e.g., "MCP Email Search")
   - Copy the generated password

### 3. Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env

# Yahoo credentials
YAHOO_EMAIL=your_yahoo_email@yahoo.com
YAHOO_APP_PASSWORD=your_yahoo_app_password_here
```

### 5. Claude Desktop Configuration

Add to your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "email-search": {
      "command": "python",
      "args": ["-m", "mcp_email_search.server"],
      "cwd": "/absolute/path/to/mcp_email_search"
    }
  }
}
```

Alternatively, if you installed the package:

```json
{
  "mcpServers": {
    "email-search": {
      "command": "mcp-email-search"
    }
  }
}
```

## Usage Examples

Once configured with Claude Desktop, you can use natural language commands:

### Basic Email Search
- "Search for emails about 'meeting' from last week"
- "Find emails from john@company.com in December 2024"
- "Show me emails with attachments containing 'invoice'"
- "List my email folders"
- "Check my email configuration status"

### Email Classification Workflow Examples

### Email Classification Workflow Examples

#### Single Email Classification (Option A)

**Use Case:** Processing individual emails or small batches

**1. Find and prepare email:**
```
User: "Search for unread emails from john@company.com"
User: "Prepare email MSG-ID-12345@yahoo.com for classification"
→ Returns: Email content and available categories
```

**2. AI analyzes and user moves:**
```
AI: Analyzes content and determines it's a job application
User: "Move this email to job_applications category"
→ Tool: move_email_thread
→ Result: Email moved to job_applications folder
```

#### Bulk Email Classification (Option B)

**Use Case:** Processing many emails efficiently

**1. Find and prepare multiple emails:**
```
User: "Search for all emails from this week containing 'order' or 'receipt'"
User: "Prepare these 15 emails for classification"
→ Returns: Content for all emails
```

**2. AI analyzes all and creates bulk classification:**
```
AI creates classification JSON:
[
  {"email_id": "msg1@example.com", "category": "shopping_receipts", "confidence": 0.92},
  {"email_id": "msg2@example.com", "category": "promotions", "confidence": 0.65},
  {"email_id": "msg3@example.com", "category": "job_applications", "confidence": 0.88}
]
```

**3. Bulk move with confidence filtering:**
```
User: "Process this bulk classification with minimum confidence 0.7"
→ Tool: bulk_move_emails_by_classification
→ Result: High-confidence emails moved, low-confidence skipped
```

#### When to Use Each Approach

**Use Single Email (Option A) when:**
- Processing 1-5 emails at a time
- Want immediate feedback on each email
- Learning the system or testing classifications
- Dealing with important emails requiring individual attention

**Use Bulk Processing (Option B) when:**
- Processing 10+ emails at once
- Want efficiency over individual control
- Have clear confidence thresholds
- Batch processing routine email cleanup
[
### Folder-Specific Search
- "Search my Sent folder for emails about 'project alpha'"
- "Find emails in my Archive folder from this month"
- "Search my Drafts folder for unsent emails"
- "Look for emails across all my folders containing 'important'"

## Message-ID System

The server uses RFC-compliant Message-ID headers for reliable email identification:

- **Unique Identification**: Each email has a unique Message-ID regardless of folder
- **Cross-Folder Tracking**: Find emails even when moved between folders
- **Reliable Operations**: Consistent email identification for classification workflows
- **Format**: Standard RFC format like `<unique-id@domain.com>` or `MSG-ID-timestamp@provider.com`

### Message-ID Features
- Automatic extraction from email headers
- Fallback generation for emails without Message-IDs
- Angle bracket handling for proper IMAP search
- Cross-folder email location and movement

## Folder Search Features

### Available Folder Options
- **INBOX** (default): Your main inbox folder
- **Sent**: Emails you've sent
- **Drafts**: Draft emails
- **Archive**: Archived emails
- **Trash**: Deleted emails
- **Custom folders**: Any custom folders you've created
- **ALL**: Search across all available folders

### Folder Search Examples
```python
# Search specific folder
search_emails(keywords="meeting", folder="Sent")

# Search all folders
search_emails(keywords="important", folder="ALL", max_results=20)

# List available folders
list_email_folders()
```

### Performance Notes
- Searching specific folders is faster than searching ALL folders
- When searching ALL folders, results are limited per folder to maintain performance
- Most recent emails are prioritized in search results

## Security & Privacy

- **Local Processing**: All email processing happens locally on your machine
- **Secure Authentication**: Uses industry-standard app passwords
- **Read-Only Access**: Only requests read permissions to your email accounts
- **No Data Storage**: Emails are not stored or cached by the server
- **Minimal Permissions**: Only accesses what's necessary for search functionality

## Troubleshooting

### Connection Issues

1. Run the configuration check:
   ```bash
   python -m mcp_email_search.server
   # Then in Claude: "Check email configuration"
   ```

2. Verify credentials are correctly set in `.env`

3. For Yahoo: Verify app password is correct and 2-factor authentication is enabled

### Common Errors

- **"Yahoo credentials not configured"**: Set YAHOO_EMAIL and YAHOO_APP_PASSWORD
- **"Failed to connect to Yahoo"**: Check internet connection and credential validity

## Testing

The project includes comprehensive tests to validate the email classification workflow:

```bash
# Run the comprehensive test suite
python test_reorganized_workflow.py
```

### Test Coverage
- ✅ Helper function validation (provider, category, valid categories)
- ✅ Yahoo service connection and folder operations
- ✅ Step 1 validation (email classification preparation)
- ✅ Step 2 validation (single email movement)
- ✅ Step 3 validation (bulk email operations)
- ✅ Search function validation
- ✅ Complete 3-step workflow integration

### Expected Test Output
```
🧪 Testing Reorganized Email Classification Workflow
============================================================
🔧 Testing Helper Functions...
✅ All helper functions passed!

📧 Testing Yahoo Service Connection...
✅ Yahoo service connection successful

🔍 Testing Step 1: get_email_for_classification...
✅ Step 1 validation passed

📤 Testing Step 2: move_email_thread...
✅ Step 2 validation passed

📊 Testing Step 3: bulk_move_emails_by_classification...
✅ Step 3 validation passed

🔎 Testing Email Search and Details...
✅ Search functions passed

🔄 Testing Complete Workflow Integration...
✅ Complete workflow integration passed

🎉 ALL TESTS COMPLETED SUCCESSFULLY!
```

## Development

```bash
# Install in development mode
pip install -e .[dev]

# Run the server directly
python -m mcp_email_search.server

# Test with MCP Inspector
npx @modelcontextprotocol/inspector python -m mcp_email_search.server

# Run comprehensive tests
python test_reorganized_workflow.py

# Format code
black mcp_email_search/
isort mcp_email_search/

# Type checking
mypy mcp_email_search/
```

## Architecture

### Project Structure
```
mcp_email_search/
├── __init__.py
├── server.py              # Main FastMCP server with 3-step classification workflow
├── types.py               # Type definitions and data models
└── services/
    ├── __init__.py
    └── yahoo.py            # Yahoo Mail service with Message-ID system
```

### Key Components

1. **FastMCP Server** (`server.py`):
   - Email search and retrieval tools
   - 3-step classification workflow
   - Helper validation functions
   - Classification prompt resource

2. **Yahoo Service** (`services/yahoo.py`):
   - IMAP connection management
   - Message-ID based email identification
   - Email search and movement operations
   - Folder management and creation

3. **Type System** (`types.py`):
   - EmailSearchParams, EmailSearchResult
   - EmailDetails, EmailClassificationResult
   - EmailMoveResult data models

4. **Testing** (`test_reorganized_workflow.py`):
   - Comprehensive workflow validation
   - Helper function testing
   - Service integration testing

## License

MIT License - see LICENSE file for details.
