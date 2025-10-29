# Job Application Automation System

Automated job application system using n8n, Claude API, and local LLMs.

## Tech Stack
- **n8n**: Workflow automation (Docker)
- **SQLite**: Database (included with n8n)
- **Claude API**: AI for job analysis & personalization
- **LM Studio**: Local LLM (optional)
- **Playwright**: Web scraping
- **SendGrid**: Email sending

## Quick Start
```bash
# Start the system
docker-compose up -d

# Access n8n
http://localhost:5678

# Stop the system
docker-compose down
```

## Project Structure
- `data/`: Persistent data storage
- `scripts/`: Automation scripts
- `prompts/`: AI prompt templates
- `workflows/`: n8n workflow backups

## Stats
- Applications sent: TBD
- Response rate: TBD
- Interviews landed: TBD

## Setup Date
Started: 29/10/2025
Production: TBD
