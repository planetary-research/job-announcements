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
site_title = os.getenv("site_title")
site_subtitle = os.getenv("site_subtitle")
site_title_footer = os.getenv("site_title_footer")

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

# Mastodon API credentials
mastodon_client_id = os.getenv("mastodon_client_id")
mastodon_client_secret = os.getenv("mastodon_client_secret")
mastodon_access_token = os.getenv("mastodon_access_token")
mastodon_api_base_url = os.getenv("mastodon_api_base_url")
