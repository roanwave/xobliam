# xobliam

> "mailbox" backwards, in the spirit of xobni

Gmail analytics dashboard with intelligent cleanup recommendations. Analyze 90 days of email data to discover patterns, optimize labels, and safely clean up your inbox.

## Quick Start

**Windows:** Double-click `run_xobliam.bat` to launch the dashboard.

Or create a desktop shortcut with custom icon:
```powershell
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
```

The first time you run xobliam, a setup wizard will guide you through:
1. Google OAuth authentication
2. Initial email data fetch

After setup, just double-click the launcher anytime to open your dashboard.

## Features

### Dashboard

The web-based dashboard provides six main pages:

- **Dashboard** - Summary stats, email health, upcoming dates & deadlines
- **Analytics** - Time heatmaps, volume charts, per-day hourly breakdown
- **Labels** - Label optimization, sender breakdown, merge execution, smart suggestions
- **Taxonomy** - Automatic email classification by category
- **Smart Delete** - AI-powered safety scoring for cleanup recommendations
- **Settings** - Account management, data refresh, export, cache controls

### v1.2 Features

**Date/Deadline Extractor**
- Scans unlabeled emails for upcoming dates (sales, expirations, events, appointments)
- Extracts promo codes found near dates
- Smart year inference using email sent date as context
- Shows on Dashboard in "Upcoming Dates & Deadlines" section

**Smart Label Suggester**
- Analyzes labeled emails to build sender/keyword profiles
- Suggests existing labels for unlabeled emails based on similarity
- Apply suggestions individually or bulk apply all at once
- Labels page > Suggestions tab

### v1.1 Features

**Label Manager (Smart Labeling)**
- Create new Gmail labels directly from the UI
- Find unlabeled emails by sender pattern (partial match)
- Preview and select which senders to include
- Bulk-apply labels with progress tracking
- **Gmail filter creation**: Auto-label future emails from selected senders
- Labels page > Label Manager tab

**Label Sender Breakdown**
- See which senders are under each label
- Ranked by volume with read rate per sender
- Labels page > Label Details tab

**Label Merge Execution**
- Merge redundant labels via Gmail API
- Choose merge direction, optionally delete source label
- Labels page > Overlap & Merge tab

**Per-Day Hourly Breakdown**
- Hourly email distribution for each day of the week
- "Focus Mode" suggestions identifying low-traffic periods
- Analytics page > Day Breakdown tab

### Analytics Capabilities

1. **Time Patterns** - Visualize email volume by day of week and hour
2. **Open Rate Analysis** - Track engagement metrics by sender
3. **Sender Analysis** - Ranked senders with engagement stats
4. **Daily Distribution** - Identify busiest email days
5. **Label Optimization** - Coherence scores, overlap detection, engagement efficiency
6. **Email Taxonomy** - Automatic classification (newsletter, transactional, marketing, etc.)
7. **Smart Delete** - Safety scoring for bulk cleanup

### Label Optimization

Advanced label analysis includes:

- **Coherence Score** (0-100) - Measures how focused a label is based on sender concentration
- **Engagement Efficiency** - Compare each label's read rate to inbox average
- **Overlap Detection** - Find redundant label pairs with high co-occurrence
- **Abandoned Detection** - Identify labels with zero messages
- **Smart Suggestions** - Suggest labels for unlabeled emails based on patterns
- **Actionable Recommendations** - Prioritized suggestions (MERGE, FIX, REVIEW, CLEANUP)

### Smart Delete

Safe email cleanup with 0-100 safety scoring:

| Score | Tier | Recommendation |
|-------|------|----------------|
| 90-100 | Very Safe | Bulk delete recommended |
| 70-89 | Likely Safe | Quick review |
| 50-69 | Review | Individual attention needed |
| <50 | Keep | Do not delete |

**Scoring Factors:**

*Positive (safer to delete):*
- Has unsubscribe link (+20)
- Unread since receipt (+15)
- Sender previously deleted (+10)
- Message older than 30 days (+10)
- Promotional classification (+5)

*Negative (riskier to delete):*
- User replied in thread (-40)
- Has attachments (-30)
- From user's domain (-25)
- Starred or important (-20)

## Installation

### Prerequisites

- Python 3.11 or higher
- Google Cloud project with Gmail API enabled

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

### 3. Launch

**Windows:**
```
Double-click run_xobliam.bat
```

**Manual:**
```bash
streamlit run xobliam/app.py
```

## CLI

A CLI is also available for scripting and automation:

```bash
xobliam ui                      # Launch Streamlit dashboard
xobliam auth                    # Authenticate with Gmail
xobliam fetch                   # Fetch/refresh email data
xobliam stats                   # Quick statistics
xobliam stats --day Friday      # Hourly breakdown for a specific day
xobliam labels                  # Label analysis
xobliam labels --label "Name"   # Sender breakdown for specific label
xobliam taxonomy                # Email category breakdown
xobliam export                  # Export analytics to JSON
xobliam delete                  # Smart delete (dry run by default)
xobliam clear                   # Clear cached data
```

## Email Categories

Emails are automatically classified into:

- **Newsletter** - Subscriptions and digests
- **Transactional** - Orders, receipts, confirmations
- **Marketing** - Promotions and offers
- **Automated** - Security alerts, password resets
- **Social** - Social media notifications
- **Financial** - Banking and payment alerts
- **Travel** - Flight/hotel confirmations
- **Personal** - Individual correspondence
- **Professional** - Work-related emails

## Configuration

Create a `.env` file (optional):

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
├── run_xobliam.bat      # Windows launcher
├── create_shortcut.ps1  # Desktop shortcut creator
├── xobliam.png          # App icon
├── xobliam/
│   ├── app.py           # Streamlit entrypoint
│   ├── main.py          # CLI entrypoint
│   ├── auth/            # OAuth and credentials
│   ├── fetcher/         # Gmail API + SQLite caching
│   ├── analytics/       # Analysis modules
│   ├── taxonomy/        # Email classification
│   ├── smart_delete/    # Deletion scoring
│   └── ui/              # CLI and Streamlit pages
├── tests/               # Test suite
└── data/                # Cache (gitignored)
```

## Security Notes

- Never commit `credentials.json` or `token.json`
- The `.gitignore` is configured to protect sensitive files
- Deleted emails go to Trash (recoverable for 30 days)
- OAuth tokens are stored locally in gitignored paths
- All data stays on your machine - no external servers

## License

MIT
