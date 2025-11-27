# Instagram Unfollower Tracker

A command-line tool to detect people who used to follow you back on Instagram but have since unfollowed. Features an interactive marking system to categorize accounts as influencers or unfollowers.

## Features

- **Smart Detection**: Identifies accounts you follow that don't follow you back
- **Session Persistence**: Saves Instagram session to avoid repeated logins
- **2FA Support**: Full support for two-factor authentication
- **Interactive Marking**: Categorize accounts as influencers or unfollowers
- **Historical Tracking**: SQLite database saves snapshots and categorization

## Requirements

- Python 3.8 or higher

## Installation

1. Clone or download this repository

1. Install dependencies:

```bash
pip install -r requirements.txt
```

1. (Optional) Create `.env` file for credentials:

```bash
cp .env.example .env
# Edit .env and add your Instagram username and password
```

## Usage

### First Run - Establish Baseline

Run the program to create an initial snapshot:

```bash
python main.py
```

If you haven't created a `.env` file, you'll be prompted for credentials:

```output
Instagram username: your_username
Instagram password: ********
```

**First run output:**

```output
Login successful, session saved

Fetching following list... (1,500 accounts)
Fetching followers list... (1,234 accounts)

Baseline established.
You follow 1,500 accounts
1,234 follow you back
266 don't follow back

Saved snapshot.
```

### Subsequent Runs - Detect Unfollowers

Run the program again to detect changes:

```bash
python main.py
```

**Example output with unfollowers:**

```output
Logged in using saved session

Fetching following list... (1,500 accounts)
Fetching followers list... (1,230 accounts)

Detected 4 accounts that don't follow you back:

Account: @john_doe
Mark as (i)nfluencer, (u)nfollower, or (s)kip? u
Marked as unfollower.

Account: @celebrity_account
Mark as (i)nfluencer, (u)nfollower, or (s)kip? i
Marked as influencer.

Account: @user123
Mark as (i)nfluencer, (u)nfollower, or (s)kip? s
Skipped (will appear next run).

Summary:
- Total marked: 2
- Influencers: 1
- Unfollowers: 1
- Skipped: 1
```

### Marking Options

When prompted to categorize an account:

- **`i` (Influencer)**: Mark as celebrity/influencer - will never appear again
- **`u` (Unfollower)**: Mark as regular unfollower - will never appear again
- **`s` (Skip)**: Don't categorize - will appear in next run

## Authentication

The tool uses a multi-tier authentication system:

### 1. Session File (Fastest)

After first login, session is saved to `data/session.json`. Future runs use this session automatically.

### 2. Environment Variables

Create a `.env` file with:

```output
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

### 3. Standard Input

If no `.env` file exists, you'll be prompted for credentials each time.

### Two-Factor Authentication (2FA)

If your account has 2FA enabled:

```output
2FA required
Enter verification code from your authenticator app: 123456
Login successful with 2FA, session saved
```

### Email/SMS Challenge

If Instagram requires verification:

```output
Instagram requires verification
Check your email/SMS for verification code
Send code via (e)mail or (s)ms? e
Enter verification code: 123456
Login successful after challenge, session saved
```

## How It Works

1. **Fetch Data**: Retrieves your following and followers lists from Instagram
2. **Compare**: Identifies accounts you follow that don't follow back
3. **Filter Marked**: Excludes accounts already categorized as influencer/unfollower
4. **Interactive Marking**: Prompts you to categorize each unmarked account
5. **Save Snapshot**: Stores current state and categorization in database

## Database

Data is stored in `data/tracker.db` with three tables:

- **accounts**: Categorization of accounts (influencer/unfollower)
- **relationship_snapshots**: Historical follower/following data
- **check_history**: Metadata for each run

## Project Structure

```output
instagram-unfollower-tracker/
├── src/
│   ├── __init__.py
│   ├── auth.py           # Authentication & session management
│   ├── database.py       # SQLite operations
│   ├── tracker.py        # Unfollower detection logic
│   ├── marker.py         # Interactive marking system
│   └── cli.py            # CLI interface
├── data/
│   ├── session.json      # Instagram session (auto-generated)
│   └── tracker.db        # SQLite database (auto-generated)
├── main.py               # Entry point
├── requirements.txt      # Dependencies
├── .env.example          # Environment template
└── README.md             # This file
```

## Troubleshooting

### "Error: Rate limit exceeded"

Instagram is blocking requests. Wait 30-60 minutes before trying again.

### "Error: Invalid username or password"

Check your credentials in `.env` file or re-enter them when prompted.

### "Session expired, logging in with credentials..."

Normal behavior - session has expired and will be refreshed automatically.

### "Error: 2FA verification failed"

Double-check the verification code from your authenticator app.

### First run shows "Baseline established"

This is normal. The first run saves the snapshot. On the second run, you'll be able to mark non-followers interactively.

## Security Notes

- Never commit `.env` or `data/session.json` to version control
- Session file contains authentication tokens - keep it private
- Use environment variables or stdin for credentials, never hardcode
- The `.gitignore` file is configured to exclude sensitive files

## Limitations

- First run establishes baseline, subsequent runs show unmarked non-followers
- Large follower counts (>5k) may take several minutes to fetch
- Instagram rate limits may throttle requests
- Session expires periodically and requires re-authentication

## License

This project is for personal use only. Respect Instagram's Terms of Service.
