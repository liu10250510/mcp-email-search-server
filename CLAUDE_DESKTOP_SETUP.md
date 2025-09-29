# Claude Desktop Integration Setup

## Step 1: Locate Your Claude Desktop Configuration

The Claude Desktop configuration file is located at:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

## Step 2: Add Email Search Agent Configuration

1. Open the Claude Desktop configuration file in a text editor
2. If the file doesn't exist, create it with the content below
3. If the file exists, merge the `email-search-agent` configuration into your existing `mcpServers` section

### Configuration to Add:

```json
{
  "mcpServers": {
    "email-search-agent": {
      "command": "python",
      "args": ["-m", "mcp_email_search.server"],
      "cwd": "/Users/lucy/projects/mcp_email_search",
      "env": {
        "PYTHONPATH": "/Users/lucy/projects/mcp_email_search"
      }
    }
  }
}
```

### If You Already Have Other MCP Servers:

```json
{
  "mcpServers": {
    "your-existing-server": {
      "command": "...",
      "args": ["..."]
    },
    "email-search-agent": {
      "command": "python",
      "args": ["-m", "mcp_email_search.server"],
      "cwd": "/Users/lucy/projects/mcp_email_search",
      "env": {
        "PYTHONPATH": "/Users/lucy/projects/mcp_email_search"
      }
    }
  }
}
```

## Step 3: Restart Claude Desktop

After saving the configuration file, completely quit and restart Claude Desktop for the changes to take effect.

## Step 4: Test the Integration

Once Claude Desktop restarts, you can test the email search agent by asking Claude to:

- "Search my emails for messages about meetings from last week"
- "Check my email configuration status"
- "Find emails from john@example.com in the last month"
- "Search my Yahoo emails for messages with attachments"

## Available Tools:

1. **search_emails**: Search emails with keywords, date filters, and provider selection
2. **get_email_details**: Get full content of a specific email by ID
3. **check_email_config**: Verify email account setup and credentials

## Troubleshooting:

1. **Server not starting**: Check that your Python environment is activated and all dependencies are installed
2. **No emails found**: Verify your `.env` file has the correct credentials
3. **Connection errors**: Test the server manually with `python test_mcp_yahoo.py`

## Environment Variables Required:

Make sure your `.env` file in the project directory contains:

```
# Yahoo IMAP credentials
YAHOO_EMAIL=your_yahoo_email@yahoo.com
YAHOO_APP_PASSWORD=your_yahoo_app_password
```