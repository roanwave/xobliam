# Changelog

All notable changes to xobliam will be documented in this file.

## [1.1.0] - 2024-12-28

### Added

**Label Sender Breakdown**
- New "Label Details" tab in Labels page showing sender breakdown for each label
- Senders ranked by volume with read rate per sender and percentage of label
- CLI: `xobliam labels --label "LabelName"` to view sender breakdown

**Label Merge Execution**
- "Merge Now" button in Labels > Overlap & Merge tab
- Modal confirmation with merge direction selection
- Execute merges via Gmail API: add target label, remove source label
- Option to delete source label after merge
- Progress tracking during merge operation

**Per-Day Hourly Breakdown**
- New "Day Breakdown" tab in Analytics page
- Select any day of the week to see hourly email distribution
- Automatic "Focus Mode" suggestions identifying low-traffic periods
- Activity by time block (6am-9am, 9am-12pm, etc.) with peak/quiet indicators
- CLI: `xobliam stats --day Friday` for hourly breakdown

**Label Manager (Smart Labeling)**
- New "Label Manager" tab in Labels page for creating and bulk-applying labels
- Create new Gmail labels directly from the UI
- Find unlabeled emails by sender pattern (comma-separated, case-insensitive partial match)
- Optional subject keyword filtering
- Preview matching emails grouped by sender with checkboxes to include/exclude
- Apply label to selected emails with progress tracking
- Makes xobliam an inbox organization tool, not just analytics

### Changed
- Labels page now has 7 tabs: Health Summary, All Labels, Label Details, Coherence, Engagement, Overlap & Merge, Label Manager
- Analytics page now has 5 tabs: Time Patterns, Day Breakdown, Sender Analysis, Daily Distribution, Engagement

## [1.0.0] - 2024-12-27

### Added

**Streamlit Dashboard**
- Full-featured web dashboard with six pages: Dashboard, Analytics, Labels, Taxonomy, Smart Delete, Settings
- First-run setup wizard with OAuth flow and initial data fetch
- Windows launcher (`run_xobliam.bat`) for double-click launch with auto-browser opening
- No CLI dependency required for normal use

**Analytics**
- Time pattern heatmaps (day of week × hour)
- Open rate analysis with per-sender engagement metrics
- Sender analysis with volume, read rate, and reply tracking
- Daily distribution and busiest day identification
- Calendar view of email volume

**Label Optimization**
- Coherence scoring (0-100) measuring label focus based on sender concentration
- Engagement efficiency comparing label read rates to inbox average
- Overlap detection finding redundant label pairs with high co-occurrence
- Abandoned label detection for labels with zero messages
- Split candidate identification for overly broad labels
- Smart new label suggestions filtered by engagement and activity consistency
- Actionable recommendations (MERGE, FIX, REVIEW, CLEANUP, SPLIT) with impact ratings

**Email Taxonomy**
- Automatic classification into 9 categories: Newsletter, Transactional, Marketing, Automated, Social, Financial, Travel, Personal, Professional
- Category breakdown with volume and engagement stats
- Per-category drill-down with top senders

**Smart Delete**
- Safety scoring algorithm (0-100) with weighted factors
- Four tiers: Very Safe (90+), Likely Safe (70-89), Review (50-69), Keep (<50)
- Batch selection and deletion with confirmation
- Dry-run mode for previewing deletions
- Progress tracking during deletion

**Settings & Admin**
- Re-authentication flow
- Data refresh with progress indicator
- Cache clearing
- JSON export of all analytics

**CLI**
- Commands: `ui`, `auth`, `fetch`, `stats`, `labels`, `taxonomy`, `export`, `delete`, `clear`
- Rich-formatted output with tables, progress bars, and color coding
- Full parity with dashboard features

**Infrastructure**
- SQLite caching for email metadata
- Gmail API integration with pagination and rate limiting
- OAuth 2.0 authentication with token persistence
- Exponential backoff for API errors

### Security
- Comprehensive `.gitignore` protecting credentials and tokens
- All sensitive data stored in gitignored paths
- Deleted emails go to Trash (recoverable for 30 days)
- No external servers - all data stays local
