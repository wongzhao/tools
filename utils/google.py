import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

def perform_oauth(token_path, credentials_path, scopes):
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, scopes
            )
            creds = flow.run_local_server(port=0, open_browser=False)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return creds
