from io import BytesIO
import pandas as pd
import requests

# Base configuration for Princeton DSS sandbox
BASE_URL = "https://vpn.princeton.edu/https/sandbox-dss1.lib.princeton.edu/Kaiko/"
SESSION = requests.Session()

# 🔑 Inject your fresh browser session cookies here if required:
SESSION.cookies.set(
    "GP_SESSION_CK",
    "cguAIlucsUbPqiZ6Ij8Gii6TmGcJVHZ7",
    domain="vpn.princeton.edu",
)
SESSION.cookies.set(
    "SESSID", "649e6feb-ad94-4232-8eda-ea5c3b2c36b7", domain="vpn.princeton.edu"
)

TARGETS = [
    {"exchange": "btso", "pair": "usdtars"},
    {"exchange": "btso", "pair": "usdtbrl"},
    {"exchange": "btso", "pair": "usdtmxn"},
    {"exchange": "merc", "pair": "usdtbrl"},
    {"exchange": "merc", "pair": "usdcbrl"},
    {"exchange": "bnce", "pair": "usdtbrl"},
]


def test_connection():
  """Verifies if the session cookies are successfully bypassing the 403 wall."""
  test_url = f"{BASE_URL}trades/btso/spot/usdtbrl/"
  res = SESSION.get(test_url)
  print(f"Connection Test Status: {res.status_code} (URL: {res.url})")
  if res.status_code == 403 or "login.esp" in res.url:
    print(
        "  ❌ ERROR: Authentication failed (HTTP 403 or redirect). Your session"
        " cookies need to be refreshed from your browser."
    )
    return False
  print("  ✅ Authentication successful!")
  return True


if __name__ == "__main__":
  if test_connection():
    # Proceed with downloading / processing target files
    print("Ready to fetch trade data panels.")