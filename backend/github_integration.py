import os
import time
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv


# Load settings.env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "settings.env")


GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"


def load_private_key():
    """Load the GitHub App private key from disk."""
    if not GITHUB_PRIVATE_KEY_PATH:
        raise RuntimeError("GITHUB_PRIVATE_KEY_PATH is not configured.")

    key_path = Path(GITHUB_PRIVATE_KEY_PATH)

    if not key_path.is_absolute():
        key_path = BASE_DIR / key_path

    if not key_path.exists():
        raise FileNotFoundError(
            f"GitHub private key not found: {key_path}"
        )

    return key_path.read_text(encoding="utf-8")


def create_app_jwt():
    """
    Create a short-lived JWT used to authenticate MellowTech
    as the GitHub App itself.
    """

    if not GITHUB_CLIENT_ID:
        raise RuntimeError("GITHUB_CLIENT_ID is not configured.")

    private_key = load_private_key()

    now = int(time.time())

    payload = {
        "iat": now - 60,
        "exp": now + (9 * 60),
        "iss": GITHUB_CLIENT_ID,
    }

    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256"
    )

    return token


def github_headers(token):
    """Standard GitHub API headers."""
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def get_app_installations():
    """
    Get the GitHub accounts where the MellowTech GitHub App
    is installed.
    """

    token = create_app_jwt()

    response = requests.get(
        f"{GITHUB_API}/app/installations",
        headers=github_headers(token),
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def get_installation_token(installation_id):
    """
    Generate a short-lived installation access token.

    This token allows MellowTech to access repositories that
    the GitHub App installation has been granted access to.
    """

    app_jwt = create_app_jwt()

    response = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers=github_headers(app_jwt),
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def get_installation_repositories(installation_id):
    """
    Get repositories that the MellowTech GitHub App installation
    can access.
    """

    token_data = get_installation_token(installation_id)

    installation_token = token_data["token"]

    response = requests.get(
        f"{GITHUB_API}/installation/repositories",
        headers=github_headers(installation_token),
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def get_repository(owner, repo, installation_id):
    """
    Get basic information about one authorized repository.
    """

    token_data = get_installation_token(installation_id)

    installation_token = token_data["token"]

    response = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}",
        headers=github_headers(installation_token),
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def test_github_connection():
    """
    Simple connection test.

    Returns information about the GitHub App installations.
    """

    installations = get_app_installations()

    return {
        "success": True,
        "installations": installations,
    }


if __name__ == "__main__":
    try:
        result = test_github_connection()

        print("GitHub connection successful.")
        print(f"Installations found: {len(result['installations'])}")

        for installation in result["installations"]:
            account = installation.get("account", {})
            print(
                f"- {account.get('login')} "
                f"(installation ID: {installation.get('id')})"
            )

    except Exception as error:
        print("GitHub connection failed.")
        print(error)