import os
from dotenv import load_dotenv

load_dotenv()

port = os.getenv('port')
sandbox = True

site_path = os.getenv("site_path")

if (public_domain := os.getenv("public_domain")) is not None:
    sandbox = False
    code_callback_URI = f"{public_domain}/authorization-code-callback"
    orcid_url = "https://orcid.org/"
    if site_path == '/':
        job_announcements_url = public_domain
    else:
        job_announcements_url = os.path.join(public_domain, os.getenv("site_path")[1:])

else:
    sandbox = True
    code_callback_URI = f"http://127.0.0.1:{port}/authorization-code-callback"
    orcid_url = "https://sandbox.orcid.org/"
    if site_path == '/':
        job_announcements_url = f"http://127.0.0.1:{port}"
    else:
        job_announcements_url = os.path.join(f"http://127.0.0.1:{port}", os.getenv("site_path")[1:])

# Load ORCID and admin parameters from .env file
cookie_secret = os.getenv("cookie_secret")
client_ID = os.getenv("client_ID")
client_secret = os.getenv("client_secret")
admin_orcid = os.getenv("admin_orcid")
orcid_member = os.getenv("orcid_member")
if orcid_member == 1:
    orcid_member = True
else:
    orcid_member = False
if os.getenv("everyone_is_editor").lower() == "true":
    everyone_is_editor = True
else:
    everyone_is_editor = False


# Database
basedir = os.path.abspath(os.path.dirname(__file__))
dbdir = os.path.join(basedir, "db")
dbname = "jobs.db"
dbpath = os.path.abspath(os.path.join(dbdir, dbname))
db_URI = "sqlite:////" + dbpath


# Default parameters for the home page
favicon = os.getenv("favicon")
background = os.getenv("background")
preview = os.getenv("preview")
site_title = os.getenv("site_title")
site_subtitle = os.getenv("site_subtitle")
site_title_footer = os.getenv("site_title_footer")
site_description = os.getenv("site_description")

# Job listing categories
raw_categories = os.getenv("categories")
categories = [item.strip() for item in raw_categories.split(';') if item.strip()]

# Default parameters for the footer
footer_url_name = os.getenv("footer_url_name")
footer_url = os.getenv("footer_url")
if os.getenv("thank_prc").lower() == "true":
    thank_prc = True
else:
    thank_prc = False
contact_email = os.getenv("contact_email")
github_repo = os.getenv("github_repo")
codeberg_repo = os.getenv("codeberg_repo")

# Mastodon API credentials
mastodon_client_id = os.getenv("mastodon_client_id")
mastodon_client_secret = os.getenv("mastodon_client_secret")
mastodon_access_token = os.getenv("mastodon_access_token")
mastodon_api_base_url = os.getenv("mastodon_api_base_url")
mastodon_account_name = os.getenv("mastodon_account_name")
mastodon_account_url = os.getenv("mastodon_account_url")

# Bluesky API credentials
bluesky_username = os.getenv("bluesky_username")
bluesky_app_password = os.getenv("bluesky_app_password")
bluesky_account_name = os.getenv("bluesky_account_name")
bluesky_account_url = os.getenv("bluesky_account_url")

# Email digest parameters
faq_email = os.getenv("faq_email")
email_digest = os.getenv("email_digest")
start_weekday = os.getenv("start_weekday")
if start_weekday is not None:
    start_weekday = int(start_weekday)
smtp_email = os.getenv("smtp_email")
smtp_reply_email = os.getenv("smtp_reply_email")
smtp_password = os.getenv("smtp_password")
smtp_server = os.getenv("smtp_server")
smtp_port = os.getenv("smtp_port")
if smtp_port is not None:
    smtp_port = int(smtp_port)
