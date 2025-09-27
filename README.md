# Email Search MCP Server

A Model Context Protocol (MCP) server that enables AI agents to search and retrieve emails Yahoo accounts using keywords and time filters.

## Features

- 🔍 **Search:**: Yahoo Mail support
- 📅 **Date range filtering**: Search emails within specific time periods  
- 🔑 **Keyword search**: Search in subject, body, and sender fields
- 📎 **Attachment filtering**: Find emails with or without attachments
- 🔐 **Secure authentication**: App Passwords for Yahoo
- 🛡️ **Privacy-focused**: All processing happens locally

## Tools Available

### `search_emails`
Search emails from Yahoo accounts using keywords and filters.

**Parameters:**
- `keywords` (string): Keywords to search for in email content, subject, or sender
- `provider` (string): Email provider to search - "yahoo"
- `date_from` (string, optional): Start date in YYYY-MM-DD format
- `date_to` (string, optional): End date in YYYY-MM-DD format  
- `max_results` (int): Maximum results to return, 1-50 (default: 10)
- `include_attachments` (bool): Whether to include emails with attachments (default: false)

### `get_email_details`
Get detailed content of a specific email by ID.

**Parameters:**
- `email_id` (string): The unique ID of the email to retrieve
- `provider` (string): Email provider - "yahoo"

### `check_email_config`
Check the configuration status of email accounts and required environment variables.

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

- "Search for emails about 'meeting' from last week"
- "Find emails from john@company.com in December 2024"
- "Show me emails with attachments containing 'invoice'"
- "Search Gmail for emails about 'project alpha' from this month"
- "Get details of that email from Yahoo with ID xyz123"

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
- **"Failed to connect to Gmail/Yahoo"**: Check internet connection and credential validity

## Development

```bash
# Install in development mode
pip install -e .[dev]

# Run the server directly
python -m mcp_email_search.server

# Test with MCP Inspector
npx @modelcontextprotocol/inspector python -m mcp_email_search.server

# Format code
black mcp_email_search/
isort mcp_email_search/

# Type checking
mypy mcp_email_search/
```

## License

MIT License - see LICENSE file for details.
