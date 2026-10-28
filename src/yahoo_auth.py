import base64
import hashlib
import json
import os
import secrets
import threading
import webbrowser
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

CLIENT_ID = os.getenv("YAHOO_CLIENT_ID")
REDIRECT_URI = os.getenv("YAHOO_REDIRECT_URI")

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"

app = Flask(__name__)

# Generate PKCE values
code_verifier = base64.urlsafe_b64encode(
    secrets.token_bytes(32)
).rstrip(b"=").decode("utf-8")

code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode("utf-8")).digest()
).rstrip(b"=").decode("utf-8")

# Generate state to protect the OAuth flow
state = secrets.token_urlsafe(32)


@app.route("/")
def oauth_callback():
    # Check for OAuth errors
    if "error" in request.args:
        return f"""
        <h2>Yahoo OAuth Error</h2>
        <p>{request.args.get("error")}</p>
        <p>{request.args.get("error_description", "")}</p>
        """

    # Verify state
    returned_state = request.args.get("state")

    if returned_state != state:
        return "<h2>Error: OAuth state does not match.</h2>", 400

    # Get authorization code
    authorization_code = request.args.get("code")

    if not authorization_code:
        return "<h2>Error: No authorization code received.</h2>", 400

    print("\nAuthorization code received.")
    print("Exchanging code for tokens...")

    # Exchange authorization code for tokens
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": authorization_code,
            "code_verifier": code_verifier,
            "client_id": CLIENT_ID,
        },
        timeout=30,
    )

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print("Yahoo response:")
        print(response.text)

        return f"""
        <h2>Token exchange failed</h2>
        <p>HTTP status: {response.status_code}</p>
        <pre>{response.text}</pre>
        """, 500

    tokens = response.json()

    # Save tokens locally
    with open("tokens.json", "w") as f:
        json.dump(tokens, f, indent=2)

    print("\nSUCCESS!")
    print("Tokens saved to tokens.json")

    return """
    <h1>Yahoo OAuth Successful!</h1>
    <p>Your Yahoo authorization was successful.</p>
    <p>You can close this browser tab.</p>
    """


def start_browser():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    authorization_url = AUTH_URL + "?" + urlencode(params)

    print("\nOpening Yahoo authorization page...")
    print(authorization_url)

    webbrowser.open(authorization_url)


if __name__ == "__main__":
    if not CLIENT_ID:
        raise ValueError("YAHOO_CLIENT_ID is missing from .env")

    if not REDIRECT_URI:
        raise ValueError("YAHOO_REDIRECT_URI is missing from .env")

    print("Starting Yahoo OAuth server...")
    print(f"Redirect URI: {REDIRECT_URI}")

    # Open Yahoo authorization page shortly after Flask starts
    threading.Timer(1.5, start_browser).start()

    # HTTPS is required because our Yahoo redirect URI uses https://
    app.run(
        host="localhost",
        port=8080,
        ssl_context="adhoc",
        debug=False,
    )