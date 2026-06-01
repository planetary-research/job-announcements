import os
import re
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from io import BytesIO
import secrets
from flask import Flask
from flask import request, session
from flask import redirect, render_template
from flask import send_from_directory, send_file
from markupsafe import escape
from waitress import serve
import orcid
from feedgen.feed import FeedGenerator
import numpy as np
from mastodon import Mastodon

import config
from db_models import db, Jobs, JobCategory, Admin, UserRole, Block
from utils import get_orcid_name, checksum


""" ORCID API """

if config.orcid_member:
    api = orcid.MemberAPI(config.client_ID, config.client_secret, sandbox=config.sandbox)
else:
    api = orcid.PublicAPI(config.client_ID, config.client_secret, sandbox=config.sandbox)

if config.sandbox:
    api._token_url = "https://sandbox.orcid.org/oauth/token"
else:
    api._token_url = "https://orcid.org/oauth/token"

""" App configuration """
app = Flask(__name__)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = config.db_URI
app.config["SECRET_KEY"] = config.cookie_secret
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
app.config.from_object(__name__)

""" Database """
db.init_app(app)

# Create database if it doesn't exist and add admin
if not os.path.exists(config.dbpath):
    print(f"Database doesn't exist. Creating new database: {config.db_URI}")
    if not os.path.isdir(config.dbdir):
        os.mkdir(config.dbdir)
    with app.app_context():
        db.create_all()
        # get admin name from orcid
        name = get_orcid_name(api, config.admin_orcid)
        admin = Admin(orcid=config.admin_orcid, name=name, role_id=3)
        db.session.add(admin)
        db.session.commit()

        for role_name in ("User", "Editor", "Administrator"):
            new_role = UserRole(name=role_name)
            db.session.add(new_role)

        for category_name in config.categories:
            new_category = JobCategory(category_name=category_name)
            db.session.add(new_category)

        db.session.commit()

reserved_slugs = [
    "logout",
    "privacy",
    "faq",
    "admin",
    "insufficient-privileges",
    "create",
    "editor",
    "user-banned",
    "feed",
    "feeds",
    "rss",
    "atom",
]

""" Update database for any new tables """
with app.app_context():
    db.create_all()
    db.session.commit()

""" Default URLs """

home_URI = config.site_path
logout_URI = os.path.join(config.site_path, "logout")
privacy_URI = os.path.join(config.site_path, "privacy")
faq_URI = os.path.join(config.site_path, "faq")
job_URI = os.path.join(config.site_path, "<slug>")
admin_URI = os.path.join(config.site_path, "admin")
insufficient_privileges_URI = os.path.join(config.site_path, "insufficient-privileges")
create_URI = os.path.join(config.site_path, "create")
editor_URI = os.path.join(config.site_path, "editor")
edit_URI = os.path.join(config.site_path, "<slug>", "edit")
banned_URI = os.path.join(config.site_path, "user-banned")

job_template = "job-single-column.html"  # default template for job announcements

# Check if Mastodon API credentials are present
if (
    config.mastodon_client_id is not None and
    config.mastodon_client_secret is not None and
    config.mastodon_access_token is not None and
    config.mastodon_api_base_url is not None
):
    try:
        mastodon = Mastodon(
            client_id=config.mastodon_client_id,
            client_secret=config.mastodon_client_secret,
            access_token=config.mastodon_access_token,
            api_base_url=config.mastodon_api_base_url)
        mastodon_api = True
    except:
        mastodon_api = False
else:
    mastodon_api = False

base_data = {
    "site_title": config.site_title,
    "site_title_footer": config.site_title_footer,
    "home_uri": home_URI,
    "logout_uri": logout_URI,
    "privacy_uri": privacy_URI,
    "faq_uri": faq_URI,
    "admin_uri": admin_URI,
    "create_uri": create_URI,
    "editor_uri": editor_URI,
    "job_announcements_url": config.job_announcements_url,
    "footer_url_name": config.footer_url_name,
    "footer_url": config.footer_url,
    "thank_prc": config.thank_prc,
    "contact_email": config.contact_email,
    "orcid_url": config.orcid_url,
    "authorization_uri_admin": api.get_login_url(
        scope="/authenticate",
        redirect_uri=config.code_callback_URI + "-admin"),
    "redirect_alerts": None,
    "role_id": 0,
    "everyone_is_editor": config.everyone_is_editor,
    "header_title": config.site_title,
    "header_subtitle": config.site_subtitle,
    "header_path": config.site_path,
    "category_names": config.categories,
}

base_alerts = {
    "success": None,
    "danger": None,
    "info": None,
    "warning": None,
}


""" Routes """


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static/img'),
        config.favicon, mimetype='image/vnd.microsoft.icon')


@app.route(home_URI)
def home():
    # Home page
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    jobs_list = dict()
    sum_category = np.zeros(len(config.categories))
    # Create list of job announcements
    for row in Jobs.query.filter_by(is_active=True).order_by(Jobs.creation_date.desc()).all():
        if row.deadline_date is None:
            deadline_date = ''
        else:
            deadline_date = row.deadline_date.strftime('%Y-%m-%d')

        location = row.city
        if row.country != '':
            if location != '':
                location = location + ', ' + row.country
            else:
                location = row.country

        date_now = datetime.datetime.now(datetime.UTC)
        date_expire = date_now + relativedelta(years=1)
        post_date = row.post_date.replace(tzinfo=datetime.UTC)  # timezone is lost in sqlalchemy
        if row.deadline_date is not None:
            deadline = row.deadline_date.replace(tzinfo=datetime.UTC)
            if date_now < deadline + relativedelta(days=1):  # add one extra day to the deadline to account for time zone differences
                deadline_ok = True
            else:
                deadline_ok = False
        else:
            deadline_ok = True

        if (post_date < date_expire) and deadline_ok:
            jobs_list[row.job_slug] = [
                row.category_id,
                os.path.join(config.site_path, row.job_slug),
                row.title,
                row.institution,
                location,
                deadline_date,
                row.post_date.strftime('%Y-%m-%d')
                ]
            sum_category[row.category_id] += 1

    mask = sum_category > 0

    data = {
        "jobs_list": jobs_list,
        "page": "home",
        "role_id": role_id,
        "category_mask": mask,
    }

    return render_template("index.html", **(base_data | data))


@app.route(job_URI, methods=["POST", "GET"])
def action(slug):
    # Show the job announcement
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    # check if the job announcement exists
    result = Jobs.query.filter_by(job_slug=slug).first()
    if not result:
        return render_template("job-announcement-not-found.html", **base_data)

    # check if the job announcement is open
    if result.is_active is False:
        return render_template("job-announcement-closed.html", **base_data)

    job = Jobs.query.filter_by(job_slug=slug).first()

    if job.deadline_date is None:
        deadline_date = ''
    else:
        deadline_date = job.deadline_date.strftime('%Y-%m-%d')
    if job.start_date is None:
        start_date = ''
    else:
        start_date = job.start_date.strftime('%Y-%m-%d')
    if job.post_date is None:
        post_date = ''
    else:
        post_date = job.post_date.strftime('%Y-%m-%d')
    if job.closed_date is None:
        closed_date = ''
    else:
        closed_date = job.closed_date.strftime('%Y-%m-%d')

    location = job.city
    if job.country != '':
        if location != '':
            location = location + ', ' + job.country
        else:
            location = job.country

    data = {
        "job_category": config.categories[job.category_id],
        "job_title": job.title,
        "job_description": job.description,
        # "job_application_instructions": job.application_instructions,
        "job_institution": job.institution,
        "job_department": job.department,
        "job_country": job.country,
        "job_city": job.city,
        "job_location": location,
        "job_work_arrangement": job.work_arrangement,
        "job_official_announcement_url": job.official_announcement_url,
        "job_duration": job.duration,
        "job_can_extend": job.can_extend,
        "job_salary": job.salary,
        "job_number_positions": job.number_positions,
        "job_reference_code": job.reference_code,
        "job_inquiries_name": job.inquiries_name,
        "job_inquiries_email": job.inquiries_email,
        "job_owner_orcid": job.owner_orcid,
        "job_owner_name": job.owner_name,
        "job_closed_date": closed_date,
        "job_post_date": post_date,
        "job_start_date": start_date,
        "job_deadline_date": deadline_date,
        "role_id": role_id,
    }

    return render_template(job_template, **(base_data | data))


@app.route("/authorization-code-callback", methods=["GET"])
def authorize():
    # Instantiate the return code
    code = None

    # If a GET request is made
    if request.method == "GET":
        # Fetch (and sanitise) the return code
        code = escape(request.args["code"])

        # Exchange the security code for a token
        token = api.get_token_from_authorization_code(code, config.code_callback_URI)

        # Extract the ORCID and user name from the token, and set to session
        session["orcid"] = escape(token["orcid"])
        session["name"] = escape(token["name"])
        session.permanent = True

        # check if user is banned
        if len(Block.query.filter_by(orcid=session["orcid"]).all()) > 0:
            return redirect(banned_URI)

    return "Fetching ORCID account details..."


@app.route("/authorization-code-callback-admin", methods=["GET"])
def authorize_admin():
    # Instantiate the return code
    code = None

    # If a GET request is made
    if request.method == "GET":
        # Fetch (and sanitise) the return code
        code = escape(request.args["code"])

        # Exchange the security code for a token
        token = api.get_token_from_authorization_code(code, config.code_callback_URI+"-admin")

        # Extract the ORCID and user name from the token, and set to session
        session["orcid"] = escape(token["orcid"])
        session["name"] = escape(token["name"])
        session.permanent = True

        # check if user is banned
        if len(Block.query.filter_by(orcid=session["orcid"]).all()) > 0:
            return redirect(banned_URI)

        return redirect(editor_URI)

    return "Fetching ORCID account details..."


@app.route(privacy_URI)
def privacy():
    # Show the privacy page
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    data = {
        "role_id": role_id,
    }
    return render_template("privacy.html", **(base_data | data))


@app.route(faq_URI)
def faq():
    # Show the faq page
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    data = {
        "role_id": role_id,
    }
    return render_template("faq.html", **(base_data | data))


@app.route(admin_URI, methods=["POST", "GET"])
def admin():
    # Show the admin page

    # Check if the user is logged in
    if session.get("orcid") is None:
        return redirect(home_URI)

    # Query database for user's ORCID
    user = Admin.query.filter_by(orcid=session["orcid"]).first()
    if user is None:
        print("User is not in the Admin database")
        return redirect(insufficient_privileges_URI)

    # Check if the user has sufficient permissions
    if user.role_id < 3:
        print("Insufficient permissions to view the Admin page")
        return redirect(insufficient_privileges_URI)

    role = UserRole.query.filter_by(role_id=user.role_id).first()
    modify_options = [[1, "Remove"], [2, "Editor"], [3, "Administrator"]]
    delete_options = [[1, "Delete"], [2, "Ban"], [3, "Remove ban"]]
    alerts = base_alerts.copy()

    orphans = len(Jobs.query.filter_by(job_slug='').all())

    # If an update is pushed
    if request.method == "POST":

        # Add or modify a user
        if request.form.get("mode") == "modify_user":
            # Get the user's ORCID
            user_id = escape(request.form["user_id"])
            # Get the desired user role
            role_id = int(request.form["user_role"])

            # Check if we are not accidently changing self
            if user_id == session["orcid"]:
                alerts["danger"] = "You cannot modify yourself."
            # Check if the ORCID is valid (4 groups of 4 digits)
            elif (re.match(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9|xX]", user_id.strip()) is None) or not checksum(user_id.strip()):
                alerts["danger"] = "Invalid ORCID."
            # All good
            else:
                # Try to get user from DB
                user = Admin.query.filter_by(orcid=user_id).first()
                if user is None and role_id > 1:
                    # Try to get public name and email from orcid profile
                    orcid_name = get_orcid_name(api, user_id)
                    if orcid_name == '':
                        alerts["warning"] = "The ORCID user name is marked as private and will not be shown."
                    # Add new user
                    user = Admin(orcid=user_id, name=orcid_name, role_id=role_id)
                    db.session.add(user)
                    alerts["success"] = "New user added to admin database."
                elif user is None and role_id == 1:
                    alerts["warning"] = "User does not exist and can not be deleted."
                elif role_id > 1:
                    # Modify role ID
                    if user.role_id == role_id:
                        alerts["info"] = "User role did not need to be modified."
                    else:
                        user.role_id = role_id
                        alerts["success"] = "User role modified."
                else:
                    db.session.delete(user)
                    alerts["success"] = "User deleted."

                db.session.commit()

        # Delete or ban user
        if request.form.get("mode") == "delete_ban_user":
            # Get the user's ORCID
            user_id = escape(request.form["user_id"])
            # Get the desired user role
            user_option = int(request.form["user_option"])

            # Check if we are not accidently changing self
            if user_id == session["orcid"]:
                alerts["danger"] = "You cannot delete, ban, or unban your own account."
            # Check if the ORCID is valid (4 groups of 4 digits)
            elif (re.match(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9|xX]", user_id.strip()) is None) or not checksum(user_id.strip()):
                alerts["danger"] = "Invalid ORCID iD."
            elif Admin.query.filter_by(orcid=user_id).first() is not None:
                alerts["danger"] = "Can not delete, ban or unban users with administrator roles."
            else:
                if user_option == 1:
                    result = Jobs.query.filter_by(orcid=user_id).all()
                    num_deleted = len(result)
                    if num_deleted > 0:
                        Jobs.query.filter_by(orcid=user_id).delete()
                        db.session.commit()
                        if num_deleted == 1:
                            alerts["success"] = f"Deleted {num_deleted} jobs associated with ORCID iD {user_id}."
                        else:
                            alerts["success"] = f"Deleted {num_deleted} jobs associated with ORCID iD {user_id}."
                    else:
                        alerts["info"] = f"No jobs to delete for ORCID iD {user_id}."

                if user_option == 2:
                    if len(Block.query.filter_by(orcid=user_id).all()) > 0:
                        alerts["info"] = f"User is already banned: {user_id}"
                    else:
                        user = Block(orcid=user_id, name=get_orcid_name(api, user_id))
                        db.session.add(user)
                        db.session.commit()
                        alerts["success"] = f"User banned: {user_id}"

                if user_option == 3:
                    result = Block.query.filter_by(orcid=user_id).all()
                    if len(result) > 0:
                        Block.query.filter_by(orcid=user_id).delete()
                        db.session.commit()
                        alerts["success"] = f"Ban removed for ORCID iD: {user_id}"
                    else:
                        alerts["info"] = "ORCID iD is not banned."

        # Download database file
        if request.form.get("mode") == "backup_db":
            return send_file(config.dbpath, as_attachment=True)

        # Delete database orphans
        if request.form.get("mode") == "delete_orphans":
            Jobs.query.filter_by(job_slug='').delete()
            db.session.commit()
            alerts["success"] = "Deleted orphan jobs"
            orphans = 0

    # Create a list of administrators and editors and count all users
    admins = Admin.query.filter_by(role_id=3).order_by(Admin.name.asc()).all()
    editors = Admin.query.filter_by(role_id=2).order_by(Admin.name.asc()).all()
    blocked = Block.query.order_by(Block.name.asc()).all()

    data = {
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role": role.name.capitalize(),
        "role_id": role.role_id,
        "modify_options": modify_options,
        "delete_options": delete_options,
        "alert": alerts,
        "editors": editors,
        "admins": admins,
        "blocked": blocked,
        "orphans": orphans,
        "page": 'admin'
    }

    # Serve the admin page
    return render_template("admin.html", **(base_data | data))


@app.route(create_URI, methods=["POST", "GET"])
def create():
    # Show the page to create a job announcement
    if session.get("orcid") is None:
        return redirect(home_URI)
    elif base_data["everyone_is_editor"] is False:
        # Query database for user's ORCID
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            print("User is not in the Admin database")
            return redirect(insufficient_privileges_URI)

        # Check if the user has sufficient permissions
        role_id = user.role_id
        if role_id < 2:
            print("Insufficient permissions to view this page")
            return redirect(insufficient_privileges_URI)
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2

    # Default alerts (= None)
    alerts = base_alerts.copy()

    hex_string = secrets.token_hex(4)
    new_job = Jobs(
        job_slug=hex_string[0:4] + '-' + hex_string[4:8],
        is_active=True,
        title='',
        description='',
        # application_instructions='',
        institution='',
        department='',
        country='',
        city='',
        work_arrangement='',
        official_announcement_url='',
        duration='',
        can_extend='',
        salary='',
        number_positions='',
        reference_code='',
        inquiries_name='',
        inquiries_email='',
        owner_orcid=session["orcid"],
        owner_name=session["name"],
    )

    # If an update is pushed
    if request.method == "POST":
        if request.form.get("mode") == "create_job":
            if request.form["activate_job"] == 'True':
                is_active = True
                closed_date = None
                post_date = datetime.datetime.now(datetime.UTC)
            else:
                is_active = False
                closed_date = datetime.datetime.now(datetime.UTC)
                post_date = None

            job_slug = escape(request.form["job_slug"])

            if request.form["start_date"] == '':
                start_date = None
            else:
                start_date = datetime.datetime.strptime(request.form["start_date"], '%Y-%m-%d')

            if request.form["deadline_date"] == '':
                deadline_date = None
            else:
                deadline_date = datetime.datetime.strptime(request.form["deadline_date"], '%Y-%m-%d')

            new_job = Jobs(
                job_slug=job_slug,
                category_id=request.form["new_category"],
                title=escape(request.form["title"]),
                description=request.form["description"],
                # application_instructions=request.form["application_instructions"],
                institution=escape(request.form["institution"]),
                department=escape(request.form["department"]),
                country=escape(request.form["country"]),
                city=escape(request.form["city"]),
                work_arrangement=escape(request.form["work_arrangement"]),
                official_announcement_url=escape(request.form["official_announcement_url"]),
                duration=escape(request.form["duration"]),
                can_extend=escape(request.form["can_extend"]),
                salary=escape(request.form["salary"]),
                number_positions=escape(request.form["number_positions"]),
                reference_code=escape(request.form["reference_code"]),
                inquiries_name=escape(request.form["inquiries_name"]),
                inquiries_email=escape(request.form["inquiries_email"]),
                owner_orcid=session["orcid"],
                owner_name=session["name"],
                is_active=is_active,
                closed_date=closed_date,
                post_date=post_date,
                start_date=start_date,
                deadline_date=deadline_date,
            )

            if Jobs.query.filter_by(job_slug=job_slug).first() is not None:
                alerts["danger"] = "Job slug already exists. Please choose another."
            elif job_slug == '':
                alerts["danger"] = "Job slug cannot be an empty string."
            elif ' ' in job_slug:
                alerts["danger"] = "Job slug cannot contain spaces."
            elif job_slug in reserved_slugs:
                alerts["danger"] = "Job slug is reserved. Please choose another."
            elif new_job.title == '':
                alerts["danger"] = "You must enter a job title."
            else:
                db.session.add(new_job)
                db.session.commit()

                location = new_job.city
                if new_job.country != '':
                    if location != '':
                        location = location + ', ' + new_job.country
                    else:
                        location = new_job.country

                if mastodon_api and new_job.is_active:
                    mastodon.toot(
                        "PLANETARY SCIENCE JOB ANNOUNCEMENT\nCategory: " +
                        config.categories[new_job.category_id] + "\n\n" +
                        new_job.title + "\n" + new_job.institution + "\n" +
                        location + "\n\n" +
                        os.path.join(config.job_announcements_url, new_job.job_slug)
                    )

                base_data["redirect_alerts"] = {
                    "success": "Job created.",
                    "danger": None,
                    "info": None,
                    "warning": None,
                }
                return redirect(editor_URI)

    data = {
        "categories": list(enumerate(config.categories)),
        "form_category_id": new_job.category_id,
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role_id": role_id,
        "alert": alerts,
        "page": 'create',
        "form_slug": new_job.job_slug,
        "form_title": new_job.title,
        "form_description": new_job.description,
        # "form_application_instructions": new_job.application_instructions,
        "form_institution": new_job.institution,
        "form_department": new_job.department,
        "form_country": new_job.country,
        "form_city": new_job.city,
        "form_work_arrangement": new_job.work_arrangement,
        "form_official_announcement_url": new_job.official_announcement_url,
        "form_duration": new_job.duration,
        "form_can_extend": new_job.can_extend,
        "form_number_positions": new_job.number_positions,
        "form_reference_code": new_job.reference_code,
        "form_inquiries_name": new_job.inquiries_name,
        "form_inquiries_email": new_job.inquiries_email,
        "form_salary": new_job.salary,
        "form_activate": new_job.is_active,
        "form_start_date": new_job.start_date,
        "form_deadline_date": new_job.deadline_date,
    }

    return render_template("create.html", **(base_data | data))


@app.route(edit_URI, methods=["POST", "GET"])
def edit(slug):
    # Show the page to edit a specific job announcement
    if session.get("orcid") is None:
        return redirect(home_URI)
    elif base_data["everyone_is_editor"] is False:
        # Query database for user's ORCID
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            print("User is not in the Admin database")
            return redirect(insufficient_privileges_URI)

        # Check if the user has sufficient permissions
        role_id = user.role_id
        if role_id < 2:
            print("Insufficient permissions to view this page")
            return redirect(insufficient_privileges_URI)
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2

    edit_job = Jobs.query.filter_by(job_slug=slug).first()
    if not edit_job:
        return render_template("job-announcement-not-found.html", **(base_data))

    # For editors, check if the user is the job announcement owner
    if role_id == 2:
        if edit_job.owner_orcid != session["orcid"]:
            print("Insufficient permissions to edit this announcement")
            return redirect(insufficient_privileges_URI)

    # Default alerts (= None)
    alerts = base_alerts.copy()

    published = edit_job.is_active
    # If an update is pushed
    if request.method == "POST":
        if request.form.get("mode") == "edit_job":

            if request.form["start_date"] == '':
                start_date = None
            else:
                start_date = datetime.datetime.strptime(request.form["start_date"], '%Y-%m-%d')

            if request.form["deadline_date"] == '':
                deadline_date = None
            else:
                deadline_date = datetime.datetime.strptime(request.form["deadline_date"], '%Y-%m-%d')

            edit_job.start_date = start_date
            edit_job.deadline_date = deadline_date
            edit_job.category_id = request.form["new_category"]
            edit_job.title = escape(request.form["title"])
            edit_job.description = request.form["description"]
            # edit_job.application_instructions=request.form["application_instructions"]
            edit_job.institution = escape(request.form["institution"])
            edit_job.department = escape(request.form["department"])
            edit_job.country = escape(request.form["country"])
            edit_job.city = escape(request.form["city"])
            edit_job.work_arrangement = escape(request.form["work_arrangement"])
            edit_job.official_announcement_url = escape(request.form["official_announcement_url"])
            edit_job.duration = escape(request.form["duration"])
            edit_job.can_extend = escape(request.form["can_extend"])
            edit_job.salary = escape(request.form["salary"])
            edit_job.number_positions = escape(request.form["number_positions"])
            edit_job.reference_code = escape(request.form["reference_code"])
            edit_job.inquiries_name = escape(request.form["inquiries_name"])
            edit_job.inquiries_email = escape(request.form["inquiries_email"])

            if edit_job.title == '':
                alerts["danger"] = "You must enter a job title."
            else:
                db.session.commit()

                base_data["redirect_alerts"] = {
                    "success": "Job announcement updated.",
                    "danger": None,
                    "info": None,
                    "warning": None,
                }
                return redirect(editor_URI)

        if request.form.get("mode") == "close_activate":
            if request.form["is_active"] == "Active":
                is_active = True
                edit_job.closed_date = None
                edit_job.post_date = datetime.datetime.now(datetime.UTC)
                alert_text = "Job announcement published."
            else:
                is_active = False
                edit_job.closed_date = datetime.datetime.now(datetime.UTC)
                edit_job.post_date = None
                alert_text = "Job announcement closed."

            edit_job.is_active = is_active
            db.session.commit()

            location = edit_job.city
            if edit_job.country != '':
                if location != '':
                    location = location + ', ' + edit_job.country
                else:
                    location = edit_job.country

            if mastodon_api and edit_job.is_active and not published:
                mastodon.toot(
                    "PLANETARY SCIENCE JOB ANNOUNCEMENT\nCategory: " +
                    config.categories[edit_job.category_id] + "\n\n" +
                    edit_job.title + "\n" + edit_job.institution + "\n" +
                    location + "\n\n" +
                    os.path.join(config.job_announcements_url, edit_job.job_slug)
                )

            base_data["redirect_alerts"] = {
                "success": alert_text,
                "danger": None,
                "info": None,
                "warning": None,
            }
            return redirect(editor_URI)

        if request.form.get("mode") == "reset_date":
            edit_job.creation_date = datetime.datetime.now(datetime.UTC)
            db.session.commit()

            base_data["redirect_alerts"] = {
                "success": "Job announcement creation date updated.",
                "danger": None,
                "info": None,
                "warning": None,
            }
            return redirect(editor_URI)

        if request.form.get("mode") == "delete_job":
            if request.form["confirmation"].lower() == "delete":
                # delete a job
                Jobs.query.filter_by(job_slug=edit_job.job_slug).delete()
                db.session.commit()
                base_data["redirect_alerts"] = {
                    "success": "Job annnouncement deleted.",
                    "danger": None,
                    "info": None,
                    "warning": None,
                }
                return redirect(editor_URI)
            else:
                alerts["danger"] = "Please confirm your response with \"delete\"."
            db.session.commit()

    if edit_job.start_date is None:
        form_start_date = None
    else:
        form_start_date = edit_job.start_date.strftime('%Y-%m-%d')
    if edit_job.deadline_date is None:
        form_deadline_date = None
    else:
        form_deadline_date = edit_job.deadline_date.strftime('%Y-%m-%d')

    data = {
        "categories": list(enumerate(config.categories)),
        "form_category_id": edit_job.category_id,
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role_id": role_id,
        "alert": alerts,
        "page": 'edit',
        "form_slug": edit_job.job_slug,
        "form_title": edit_job.title,
        "form_description": edit_job.description,
        # "form_application_instructions": edit_job.application_instructions,
        "form_institution": edit_job.institution,
        "form_department": edit_job.department,
        "form_country": edit_job.country,
        "form_city": edit_job.city,
        "form_work_arrangement": edit_job.work_arrangement,
        "form_official_announcement_url": edit_job.official_announcement_url,
        "form_duration": edit_job.duration,
        "form_can_extend": edit_job.can_extend,
        "form_number_positions": edit_job.number_positions,
        "form_reference_code": edit_job.reference_code,
        "form_inquiries_name": edit_job.inquiries_name,
        "form_inquiries_email": edit_job.inquiries_email,
        "form_salary": edit_job.salary,
        "form_activate": edit_job.is_active,
        "form_start_date": form_start_date,
        "form_deadline_date": form_deadline_date,
        "owner_orcid": edit_job.owner_orcid,
        "owner_name": edit_job.owner_name,
        "creation_date": edit_job.creation_date,
        "post_date": edit_job.post_date,
        "closed_date": edit_job.closed_date,
    }

    return render_template("edit.html", **(base_data | data))


@app.route(editor_URI)
def editor():
    # Show the editor page with their list of jobs
    if session.get("orcid") is None:
        return redirect(home_URI)
    elif base_data["everyone_is_editor"] is False:
        # Query database for user's ORCID
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            print("User is not in the Admin database")
            return redirect(insufficient_privileges_URI)

        # Check if the user has sufficient permissions
        role_id = user.role_id
        if role_id < 2:
            print("Insufficient permissions to view this page")
            return redirect(insufficient_privileges_URI)
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2

    # Default alerts (= None)
    if base_data["redirect_alerts"] is None:
        alerts = base_alerts.copy()
    else:
        alerts = base_data["redirect_alerts"]
        base_data["redirect_alerts"] = None

    my_jobs = dict()
    all_jobs = dict()
    # Create list of jobs
    for row in Jobs.query.order_by(Jobs.title.asc()).all():
        if row.owner_orcid == session["orcid"]:
            my_jobs[row.job_slug] = [
                row.title,
                os.path.join(config.site_path, row.job_slug),
                row.is_active
            ]

    if role_id == 3:
        for row in Jobs.query.order_by(Jobs.title.asc()).all():
            all_jobs[row.job_slug] = [
                row.title,
                os.path.join(config.site_path, row.job_slug),
                row.is_active
            ]

    data = {
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role_id": role_id,
        "alert": alerts,
        "page": 'editor',
        "my_jobs": my_jobs,
        "all_jobs": all_jobs,
    }

    return render_template("editor.html", **(base_data | data))


@app.route(insufficient_privileges_URI)
def insufficient_privileges():
    return render_template("insufficient-privileges.html", **base_data)


@app.route(logout_URI)
def logout():
    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)

    return redirect(home_URI)


@app.route(banned_URI)
def banned():
    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)

        data = {
            "role_id": 0,
        }
        return render_template("user-banned.html", **(base_data | data))
    else:
        return redirect(home_URI)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", **base_data), 404


@app.route('/feed/')
def feeds():
    fg = FeedGenerator()
    fg.id(os.path.join(config.job_announcements_url, config.site_path[1:], "feed"))
    fg.title(config.site_title)
    fg.subtitle(config.site_subtitle)
    fg.link(href=os.path.join(config.job_announcements_url, config.site_path[1:], "feed"), rel='alternate')
    fg.language('en')

    # Create list of feed entries
    for row in Jobs.query.filter_by(is_active=True).order_by(Jobs.post_date.asc()).all():
        fe = fg.add_entry()
        fe.id(os.path.join(config.site_path, row.job_slug))
        fe.title(row.title)
        fe.summary(config.categories[row.category_id])
        fe.link(href=os.path.join(config.site_path, row.job_slug))
        fe.published(row.post_date.replace(tzinfo=datetime.UTC))
        fe.content(row.description)

    # Generate the feed as bytes
    feed_data = fg.atom_str(pretty=True)

    # Create a BytesIO object
    feed_io = BytesIO(feed_data)

    # Return as downloadable file
    return send_file(
        feed_io,
        as_attachment=False,
        download_name='atom.xml',
        mimetype='application/atom+xml'
    )


@app.route('/feed/category/<feed_category_string>/')
def feed_category(feed_category_string):
    if feed_category_string.isdigit():
        feed_num = int(feed_category_string)
        if feed_num >= len(config.categories):
            return render_template("404.html", **base_data), 404
    else:
        return render_template("404.html", **base_data), 404

    fg = FeedGenerator()
    fg.id(os.path.join(config.job_announcements_url, config.site_path[1:], "feed/category", feed_category_string))
    fg.title(config.site_title + " - " + config.categories[feed_num])
    fg.subtitle(config.site_subtitle)
    fg.link(href=os.path.join(config.job_announcements_url, config.site_path[1:], "feed/category", feed_category_string), rel='alternate')
    fg.language('en')

    # Create list of feed entries
    for row in Jobs.query.filter_by(is_active=True).filter_by(category_id=feed_num).order_by(Jobs.post_date.asc()).all():
        fe = fg.add_entry()
        fe.id(os.path.join(config.site_path, row.job_slug))
        fe.title(row.title)
        fe.summary(config.categories[row.category_id])
        fe.link(href=os.path.join(config.site_path, row.job_slug))
        fe.published(row.post_date.replace(tzinfo=datetime.UTC))
        fe.content(row.description)

    # Generate the feed as bytes
    feed_data = fg.atom_str(pretty=True)

    # Create a BytesIO object
    feed_io = BytesIO(feed_data)

    # Return as downloadable file
    return send_file(
        feed_io,
        as_attachment=False,
        download_name='atom.xml',
        mimetype='application/atom+xml'
    )


if __name__ == "__main__":
    if config.sandbox:
        app.run(host="127.0.0.1", port=config.port, debug=True)
    else:
        serve(app, host="127.0.0.1", port=config.port)
