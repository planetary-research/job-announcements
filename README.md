# About

**Job Announcements** is a simple web-based program that allows you to browse and
create job announcements. Designed for academics, it is only necessary to
authenticate with an Open Researcher and Contributor ID account
([ORCID](https://orcid.org)) to create a new job announcement. All branding for
the website is contained in a single file, allowing it to be adapted for
any discipline.

This code was developed from a fork of the
[Signatories](https://github.com/planetary-research/signatories) project that
was developed by the
[Planetary Research Cooperative](https://coop.planetary.research.org).

# Features

* Create a job announcement effortlessly by filling out a simple form.
* Add a job description using a graphical editor.
* Edit an announcement later, or close the announcement when it has been filled.
* Automatically post new job announcements to Mastodon and Bluesky.
* Generate RSS/Atom feeds for all jobs, or for individual job categories.
* Allow anyone with an ORCID account to post an announcement, or restrict who is allowed to post.
* Create as many job categories as you would like.
* All branding is placed in a single file, so there is no need to edit the code.
* Administrator controls to ban users, delete posts, and more.

# Dependencies

```
conda create -n job-announcements python=3.13 numpy python-dotenv flask flask-sqlalchemy sqlalchemy-utils orcid waitress feedgen mastodon.py atproto -c conda-forge
```

# Instructions

## Initial setup

When running in production, place the project files in an appropriate directory
such as `/var/www/job-announcements`. For testing, any directory will do.

Copy the file `.env.sample` to `.env`, which should look like the following:

```txt
cookie_secret = '...'  # Random string to cross-check the stored cookie. Any string will do.
port = 3000  # port used by the web server when in sandbox mode

# Orcid ID of the site admin that is added to the database at creation
admin_orcid = 'xxxx-xxxx-xxxx-xxxx'

# If everyone_is_editor is False, admins must add editors to the database manually.
# Otherwise, everyone with an ORCID account can create announcements.
everyone_is_editor = True

# Set favicon (use "" for none). File name is with respect to static/img
favicon = "favicon.ico"

# Default parameters for the home page
site_title = "Job Announcements"
site_subtitle = "An open source job announcement platform"
site_path = "/"
site_header = "About"

# URL and name of a link displayed in the website footer, such as the association website
footer_url_name = "My-Organization"
footer_url = "https://my-organization.example.org/"

# Add a statement in the footer that states Signatories was created by the Planetary Research Cooperative
thank_prc = False

# Contact email in the footer
contact_email = "tech@my-organization.example.org"

# ORCID API credentials
client_ID = 'APP-ABCDEFGHIJKLMNOP'
client_secret = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'

# If the ORCID client credentials correspond to a member account, set to 1
orcid_member = 0

# Mastodon API. If present, each new announcement will be posted to Mastodon
# mastodon_client_id = "...""
# mastodon_client_secret = "...
# mastodon_access_token = "..."
# mastodon_api_base_url = "..."
# mastodon_account_name = "@...@..."
# mastodon_account_url = "..."

# Bluesky API. If present, each new announcement will be posted to Bluesky
# bluesky_username = "..."
# bluesky_app_password = "..."
# bluesky_account_name = "@..."
# bluesky_account_url = "..."

# Uncomment and provide a public URL when used in production. When public_domain
# is not set, the app will use the ORCID sandbox API.
# public_domain = 'https://jobs.example.org'
```

Then modify the following variables:

1. `cookie_secret`: a random string to cross-check the stored cookie. Any string will do.
2. `client_ID`, `client_secret`: ORCID API credentials.

> For testing, register for a [sandbox ORCID API](https://sandbox.orcid.org/) using a dummy email address. When the API is enabled, go to [`ORCID profile > developer tools`](https://sandbox.orcid.org/developer-tools) and create a client ID and secret.
> In production use the main [ORCID API credentials](https://orcid.org/developer-tools).

3. Add a public domain if the application is used in production (not required for local development in sandbox mode).
4. Update the parameters `favicon`, `footer_url_name`, `footer_url`, `thank_prc`, and `contact_email`.

Finally, to run the app, use:
```bash
python app.py
```

## System service

To have the application start automatically when the system reboots, create a file `/etc/systemd/system/job-announcements.service` with the following contents:

```
[Unit]
Description=Job Announcements daemon
After=multi-user.target

[Service]
ExecStart=/opt/miniforge3/envs/job-announcements/bin/python /var/www/job-announcements/app.py &
Type=simple
Restart=always

[Install]
WantedBy=multi-user.target
```

and then run the following at the command line
```
systemctl daemon-reload
systemctl enable job-announcements
service job-announcements start
```

## Reverse proxy

Running the application will enable an http web server on port 3000. To use this
securely with an apache web server, it will be necessary to create a reverse proxy.
First, create the file `/etc/apache2/sites-available/job-announcements.conf` with
the following:

```
<VirtualHost *:80>
    ServerName jobs.example.org
    Redirect / https://jobs.example.org
</VirtualHost>

<VirtualHost *:443>
    ServerName jobs.example.org
    ProxyPass / http://127.0.0.1:3000/
    ProxyPassReverse / http://127.0.0.1:3000/
    ProxyRequests Off
</VirtualHost>

<Directory /var/www/job-announcements>
    Options +FollowSymLinks
    Options -Indexes
    AllowOverride All
    order allow,deny
    allow from all
</Directory>
```

Then execute the following commands:
```
a2enmod proxy
a2enmod proxy_http
systemctl restart apache2
a2ensite job-announcements.conf
```

## Notes

* The database is by default located at `db/jobs.db`.
* If you change from sandbox to production modes (by setting `public_domain`), you should re-initialize the database. Otherwise sandbox accounts will appear in the production database.
