import os
import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

def get_gspread_client():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials_oauth.json", SCOPES)
        # Headless: não tenta abrir navegador, imprime URL no terminal
        creds = flow.run_local_server(port=0, open_browser=False)
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    client = gspread.authorize(creds)
    return client

if __name__ == "__main__":
    client = get_gspread_client()
    sh = client.create("Test Sheet Headless")
    print("✅ Sheet created:", sh.url)
