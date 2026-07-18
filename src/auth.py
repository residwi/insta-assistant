"""Authentication module for Instagram"""

import os
import sys
from getpass import getpass

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
)


def get_credentials() -> tuple[str, str]:
    """
    Get Instagram credentials from environment variables or stdin.

    Priority:
    1. Environment variables (.env file)
    2. Standard input prompts

    Returns:
        tuple: (username, password)
    """
    load_dotenv()

    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")

    if not username:
        username = input("Instagram username: ")

    if not password:
        password = getpass("Instagram password: ")

    return username, password


def login_with_session(
    session_file: str = "data/session.json",
    *,
    client_factory=Client,
    credentials_fn=get_credentials,
) -> Client:
    """Authenticate, validating a saved session silently before prompting.

    A valid session logs in with no credential prompt. Credentials are
    requested only when the session is missing or expired.
    """
    cl = client_factory()

    # Step 1: validate an existing session WITHOUT credentials.
    if os.path.exists(session_file):
        try:
            cl.load_settings(session_file)
            cl.get_timeline_feed()  # cheap authenticated call; raises if invalid
            print("Logged in using saved session")
            return cl
        except LoginRequired:
            print("Session expired, logging in with credentials...")

    # Step 2: fresh login with credentials.
    username, password = credentials_fn()
    try:
        cl.login(username, password)
        cl.dump_settings(session_file)
        print("Login successful, session saved")
        return cl
    except TwoFactorRequired:
        return _handle_2fa(cl, username, password, session_file)
    except ChallengeRequired:
        return _handle_challenge(cl, username, password, session_file)
    except BadPassword:
        print("Error: Invalid username or password")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Login failed: {e}")
        sys.exit(1)


def _handle_2fa(cl: Client, username: str, password: str, session_file: str) -> Client:
    """
    Handle two-factor authentication.

    Args:
        cl: Instagram client
        username: Instagram username
        password: Instagram password
        session_file: Path to session file

    Returns:
        Client: Authenticated client

    Raises:
        SystemExit: On 2FA failure
    """
    print("\n2FA required")
    code = input("Enter verification code from your authenticator app: ")

    try:
        cl.login(username, password, verification_code=code)
        cl.dump_settings(session_file)
        print("Login successful with 2FA, session saved")
        return cl
    except Exception as e:
        print(f"Error: 2FA verification failed: {e}")
        sys.exit(1)


def _handle_challenge(cl: Client, username: str, password: str, session_file: str) -> Client:
    """
    Handle Instagram security challenge (email/SMS verification).

    Args:
        cl: Instagram client
        username: Instagram username
        password: Instagram password
        session_file: Path to session file

    Returns:
        Client: Authenticated client

    Raises:
        SystemExit: On challenge failure
    """
    print("\nInstagram requires verification")
    print("Check your email/SMS for verification code")

    # Trigger challenge
    choice_input = input("Send code via (e)mail or (s)ms? ").lower()
    challenge_choice = 0 if choice_input == "e" else 1

    try:
        cl.challenge_resolve(choice=challenge_choice)
        code = input("Enter verification code: ")

        # Set handler and retry login
        cl.challenge_code_handler = lambda u, c: code
        cl.login(username, password)
        cl.dump_settings(session_file)
        print("Login successful after challenge, session saved")
        return cl
    except Exception as e:
        print(f"Error: Challenge verification failed: {e}")
        sys.exit(1)
