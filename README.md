# xobliam

> "mailbox" backwards, in the spirit of xobni

Gmail analytics dashboard with intelligent cleanup recommendations. Analyze 90 days of email data to discover patterns, optimize labels, and safely clean up your inbox.

## Features

- **Time Patterns**: Visualize email volume by day of week and hour
- **Open Rate Analysis**: Track engagement metrics by sender
- **Sender Analysis**: Ranked list of senders with engagement metrics
- **Daily Distribution**: Identify your busiest email days
- **Label Audit**: Detect redundant labels and get optimization suggestions
- **Email Taxonomy**: Automatic classification of emails by type
- **Smart Delete**: AI-powered safety scoring for cleanup recommendations

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials (Desktop application)
5. Download `credentials.json` and place in project root

### 3. Run the App

**Streamlit Dashboard:**
```bash
xobliam ui
# or
streamlit run xobliam/app.py
```

**CLI:**
```bash
# Authenticate
xobliam auth

# Fetch emails
xobliam fetch --days 90

# View stats
xobliam stats

# Launch dashboard
xobliam ui
```

## CLI Commands

```bash
xobliam ui              # Launch Streamlit dashboard
xobliam auth            # Authenticate with Gmail
xobliam fetch           # Fetch/refresh email data
xobliam stats           # Quick statistics
xobliam labels          # Label analysis
xobliam taxonomy        # Email category breakdown
xobliam export          # Export analytics to JSON
xobliam delete          # Smart delete (dry run by default)
xobliam clear           # Clear cached data
```

### Smart Delete

```bash
# Dry run (see what would be deleted)
xobliam delete --min-score 80

# Actually delete emails
xobliam delete --execute --min-score 90 --confirm
```

## Safety Scoring

The smart delete feature uses a 0-100 safety score:

| Score | Tier | Recommendation |
|-------|------|----------------|
| 90-100 | Very Safe | Bulk delete recommended |
| 70-89 | Likely Safe | Quick review |
| 50-69 | Review | Individual attention needed |
| <50 | Keep | Do not delete |

### Scoring Factors

**Positive (safer to delete):**
- Has unsubscribe link (+20)
- Unread since receipt (+15)
- Sender previously deleted (+10)
- Message older than 30 days (+10)
- No attachments (+5)
- Promotional classification (+5)

**Negative (riskier to delete):**
- User replied in thread (-40)
- Has attachments (-30)
- From user's domain (-25)
- Starred or important (-20)
- Less than 7 days old (-15)

## Email Categories

Emails are automatically classified into:

- **Newsletter**: Subscriptions and digests
- **Transactional**: Orders, receipts, confirmations
- **Marketing**: Promotions and offers
- **Automated**: Security alerts, password resets
- **Social**: Social media notifications
- **Financial**: Banking and payment alerts
- **Travel**: Flight/hotel confirmations
- **Personal**: Individual correspondence
- **Professional**: Work-related emails

## Configuration

Create a `.env` file (copy from `.env.example`):

```bash
# Path to Google OAuth credentials
GOOGLE_CREDENTIALS_PATH=./credentials.json

# Token storage location
TOKEN_PATH=./data/credentials/token.json

# Days of email history to analyze
ANALYSIS_DAYS=90
```

## Project Structure

```
xobliam/
├── xobliam/
│   ├── auth/           # OAuth and credentials
│   ├── fetcher/        # Gmail API + caching
│   ├── analytics/      # Analysis modules
│   ├── taxonomy/       # Email classification
│   ├── smart_delete/   # Deletion scoring
│   └── ui/             # CLI and Streamlit pages
├── tests/              # Test suite
└── data/               # Cache (gitignored)
```

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Format code
black xobliam/
isort xobliam/

# Lint
flake8 xobliam/
```

## Security Notes

- Never commit `credentials.json` or `token.json`
- The `.gitignore` is configured to protect sensitive files
- Deleted emails go to Trash (recoverable for 30 days)
- OAuth tokens are stored locally in gitignored paths

## License

MIT
