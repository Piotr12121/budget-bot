import os
import base64
import tempfile
import logging
from dotenv import load_dotenv
import gspread
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SPREADSHEET_NAME = os.environ["SPREADSHEET_NAME"]
SHEET_TAB_NAME = os.environ["SHEET_TAB_NAME"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])
USER_LANGUAGE = os.environ.get("USER_LANGUAGE", "pl")
DATABASE_URL = os.environ.get("DATABASE_URL")

MONTHS_MAPPING = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień",
}

MONTH_NAME_TO_NUM = {v.lower(): k for k, v in MONTHS_MAPPING.items()}

# OpenAI client
client_ai = OpenAI(api_key=OPENAI_API_KEY)

# Google Sheets client — handles Railway (env var) and local file
_creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")
if _creds_b64:
    _creds_json = base64.b64decode(_creds_b64 + "==").decode("utf-8")
    _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    _tmp.write(_creds_json)
    _tmp.close()
    gc = gspread.service_account(filename=_tmp.name)
else:
    gc = gspread.service_account(filename="credentials.json")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
