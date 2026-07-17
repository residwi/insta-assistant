# Instagram Follower-Diff Tracker

A command-line tool that detects who unfollowed you by comparing your follower list between runs, and tells you whether each departure *unfollowed* you or *disappeared* (deactivated/deleted/banned).

## Features

- **Follower Diff Detection**: Compares your follower list between runs to find who left
- **Departure Classification**: Labels each departure as `unfollowed` (account still exists) or `disappeared` (deactivated/deleted/banned)
- **Sanity Gate**: A throttled or partial fetch is skipped automatically — no false unfollowers recorded
- **Session Persistence**: Saves Instagram session to avoid repeated logins
- **2FA Support**: Full support for two-factor authentication
- **Historical Tracking**: SQLite database saves snapshots and run metadata

## Requirements

- Python 3.14 or higher
- [uv](https://docs.astral.sh/uv/)

## Installation

1. Clone or download this repository

2. Install dependencies:

```bash
uv sync
```

3. (Optional) Create `.env` file for credentials:

```bash
cp .env.example .env
# Edit .env and add your Instagram username and password
```

## Usage

### First Run — Establish Baseline

Run the program to create an initial snapshot:

```bash
uv run main.py
```

If no `.env` file or saved session exists, you'll be prompted for credentials.

The first run saves a baseline snapshot. No diff is shown because there is nothing to compare against yet.

### Subsequent Runs — Detect Changes

```bash
uv run main.py
```

**Example output:**

```output
Since last check:
  Unfollowed you (1): @john_doe
  Disappeared (0):
  New followers (2): @alice, @bob
```

## Authentication

The tool uses a multi-tier authentication system:

### 1. Session File (Fastest)

After first login, the session is saved to `data/session.json`. Future runs use this session automatically with no prompt.

### 2. Environment Variables

Create a `.env` file with:

```output
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

Credentials are only used when the saved session has expired.

### 3. Standard Input

If no `.env` file exists and the session has expired, you'll be prompted for credentials.

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

1. **Validate Session**: Checks the saved session; prompts for credentials only if expired
2. **Fetch Followers**: Retrieves your follower list from Instagram
3. **Sanity Gate**: Compares the fetched count against Instagram's reported count; aborts the run if the fetch appears throttled or incomplete
4. **Diff vs Last Snapshot**: Identifies who left and who joined since the last run
5. **Classify Departures**: For each departure, checks whether the account still exists (unfollowed) or has vanished (disappeared), with rate-limit backoff between checks
6. **Report + Save**: Prints the delta and saves the snapshot and events to the database

## Database

Data is stored in `data/tracker.db` with the following tables:

- **follower_events**: Records each departure and gain, with departure type (`unfollowed` or `disappeared`)
- **check_history**: Metadata for each run, including `follower_count` (fetched count), `reported_follower_count`, and `fetch_ok` (whether the sanity gate passed)
- **accounts**: Retained for historical influencer marks from the previous version; no longer written by the tracker

## Project Structure

```output
instagram-follower-diff-tracker/
├── src/
│   ├── __init__.py
│   ├── auth.py           # Authentication & session management
│   ├── database.py       # SQLite operations
│   ├── tracker.py        # Follower fetch + diff logic
│   └── cli.py            # CLI orchestration
├── tests/
│   ├── conftest.py       # Shared fixtures
│   ├── test_auth.py
│   ├── test_cli.py
│   ├── test_database.py
│   └── test_tracker.py
├── data/
│   ├── session.json      # Instagram session (auto-generated)
│   └── tracker.db        # SQLite database (auto-generated)
├── main.py               # Entry point
├── pyproject.toml        # Project metadata and tool config
├── uv.lock               # Pinned dependency lockfile
├── .env.example          # Environment template
└── README.md             # This file
```

## Troubleshooting

### "Fetched only N of ~M followers — likely throttled"

Instagram rate-limited the fetch. The run is skipped so no false unfollowers are recorded; try again in 30–60 minutes.

### "Error: Rate limit exceeded"

Instagram is blocking requests. Wait 30–60 minutes before trying again.

### "Error: Invalid username or password"

Check your credentials in `.env` or re-enter them when prompted.

### "Session expired, logging in with credentials..."

Normal behavior — the session has expired and will be refreshed automatically.

### "Error: 2FA verification failed"

Double-check the verification code from your authenticator app.

## Security Notes

- Never commit `.env` or `data/session.json` to version control
- Session file contains authentication tokens — keep it private
- Use environment variables or stdin for credentials, never hardcode
- The `.gitignore` file is configured to exclude sensitive files

## Limitations

- The first run establishes a baseline; the diff appears on the second run
- Large follower counts (>5k) may take several minutes to fetch
- Instagram rate limits may throttle requests; the sanity gate will skip a partial fetch automatically
- Session expires periodically and requires re-authentication

## License

This project is for personal use only. Respect Instagram's Terms of Service.
