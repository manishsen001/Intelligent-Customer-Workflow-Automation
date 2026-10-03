# AI Workflow Automation System

A powerful, extensible AI-powered workflow automation system built with Python and Streamlit. Automate tasks, send emails, and manage reminders using natural language commands.

## Features

- 🤖 **AI Agent**: Understands natural language requests and selects appropriate workflows
- ⚙️ **Task Automation**: File operations, data processing, web scraping, API calls, script execution
- 📧 **Email Automation**: Send/receive emails, templates, bulk sending, attachments
- ⏰ **Reminders & Calendar**: One-time/recurring reminders, calendar events, background checker
- 🔐 **Secure**: Environment variables for all secrets, no hardcoded credentials
- 📱 **Modern UI**: Clean Streamlit interface with chat, forms, and dashboards
- 🪵 **Logging**: Comprehensive logging with file rotation
- 🧪 **Testable**: Modular design with factory functions for easy testing

## Project Structure

```
workflow_automation/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variable template
├── README.md             # This file
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   └── base_agent.py      # AI agent for task understanding
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── task_automation.py # File ops, data processing, web/API
│   │   ├── email_automation.py# Send/read emails, templates
│   │   └── reminder.py        # Reminders, calendar events
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py        # Configuration management
│   │   └── logging_config.py  # Logging setup
│   └── utils/
│       └── __init__.py
├── tests/
│   └── __init__.py
├── data/                   # Runtime data (created automatically)
│   ├── email_templates/
│   ├── scheduled_tasks.json
│   └── reminders.json
└── logs/                   # Application logs (created automatically)
    └── app.log
```

## Quick Start

### Prerequisites

- Python 3.10+ (tested on MacBook M1 with Python 3.11)
- OpenAI API key
- Email account with SMTP/IMAP access (Gmail recommended)

### Installation

1. **Clone/Navigate to the project:**
   ```bash
   cd /path/to/Workflow_Automation_System
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # venv\Scripts\activate   # On Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials:
   ```env
   # Required: OpenAI API key for AI agent
   OPENAI_API_KEY=sk-your-openai-api-key
   
   # Required for email automation
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   EMAIL_ADDRESS=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password  # Use App Password for Gmail
   
   # Optional
   OPENAI_MODEL=gpt-4o-mini
   LOG_LEVEL=INFO
   ```

   **Gmail Setup:** Enable 2FA and create an [App Password](https://support.google.com/accounts/answer/185833) for `EMAIL_PASSWORD`.

5. **Run the application:**
   ```bash
   streamlit run app.py
   ```

6. **Open in browser:** Navigate to `http://localhost:8501`

## Usage

### AI Chat Mode
Describe what you want in natural language:
- "Send an email to john@example.com about the meeting tomorrow at 2pm"
- "Set a reminder for 3pm today to call the client"
- "Read the latest 5 unread emails from my inbox"
- "Create a CSV file with sample data"
- "Scrape the headlines from https://news.ycombinator.com"

### Task Automation
- **File Operations**: Read, write, copy, move, delete, list files
- **Data Processing**: CSV, JSON, Excel read/write/transform
- **Web Scraping**: Extract data using CSS selectors
- **API Calls**: GET, POST, PUT, DELETE with custom headers/body
- **Script Execution**: Run Python scripts with arguments
- **Scheduler**: Cron-based task scheduling

### Email Automation
- Send single/bulk emails with HTML and attachments
- Read emails with filters (unseen, from, subject)
- Create and manage email templates
- CSV-based bulk sending

### Reminders
- One-time or recurring (daily, weekly, monthly, yearly)
- Calendar events with start/end times and location
- Background checker runs every 30 seconds
- Enable/disable/delete reminders

## Configuration

All settings in `src/config/settings.py` loaded from `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `OPENAI_MODEL` | Model to use | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Response creativity | `0.7` |
| `SMTP_SERVER` | SMTP server | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `EMAIL_ADDRESS` | Sender email | Required for email |
| `EMAIL_PASSWORD` | Email password/app password | Required for email |
| `DATABASE_URL` | Database URL | `sqlite:///workflow.db` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FILE` | Log file path | `logs/app.log` |
| `STREAMLIT_SERVER_PORT` | Streamlit port | `8501` |

## Development

### Run Tests
```bash
pytest tests/ -v
```

### Code Formatting
```bash
black src/ app.py
ruff check src/ app.py
```

### Type Checking
```bash
mypy src/
```

## Extending the System

### Adding New Workflow Types

1. Create new module in `src/workflows/`
2. Add workflow type to `WorkflowType` enum in `src/agents/base_agent.py`
3. Update `get_available_actions()` in `WorkflowAgent`
4. Add execution logic in `execute_workflow()` in `app.py`

### Adding New Agent Actions

1. Add action to `get_available_actions()` in the agent
2. Implement handler in corresponding workflow module
3. Add execution branch in `execute_workflow()`

## Troubleshooting

### Common Issues

**OpenAI API Error**
- Verify `OPENAI_API_KEY` in `.env`
- Check API key has credits/access

**Email Authentication Failed**
- Use App Password for Gmail (not regular password)
- Enable "Less secure apps" or use App Password
- Check SMTP/IMAP settings

**Module Import Errors**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`
- Check Python version (3.10+)

**Streamlit Port in Use**
- Change `STREAMLIT_SERVER_PORT` in `.env`
- Or run: `streamlit run app.py --server.port 8502`

### Logs
Check `logs/app.log` for detailed error messages.

## License

MIT License - Feel free to use and modify for your projects.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request