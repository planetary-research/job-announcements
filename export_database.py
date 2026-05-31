from db_models import Jobs, Admin, Block
from app import app

jobs_file = "jobs.txt"
admins_file = "admins.txt"
banned_file = "banned.txt"

with app.app_context():

    with open(admins_file, "w") as f:
        f.write("ORCID, Name, Role\n")
        for user in Admin.query.all():
            f.write(f"{user.orcid}, {user.name}, {user.role_id}\n")

    with open(banned_file, "w") as f:
        f.write("ORCID, Name\n")
        for user in Block.query.all():
            f.write(f"{user.orcid}, {user.name}\n")

    with open(jobs_file, "w") as f:
        f.write("Slug, ORCID Owner, Owner name, Category ID, Title, Institution, Department, Country, City, Work arrangement, Official announcement URL, Duration, Can extend, Salary, Number of positions, Refrence code, Inquiries name, Inquiries email, Is active, Creation date, Post date, Closed date, Start date, Deadline date, Description, \n")
        for job in Jobs.query.all():
            f.write(
                f"{job.job_slug}, \
                {job.owner_orcid}, \
                {job.owner_name}, \
                {job.category_id}, \
                {job.title}, \
                {job.institution}, \
                {job.department}, \
                {job.country}, \
                {job.city}, \
                {job.work_arrangement}, \
                {job.official_announcement_url}, \
                {job.duration}, \
                {job.can_extend}, \
                {job.salary}, \
                {job.number_positions}, \
                {job.reference_code}, \
                {job.inquiries_name}, \
                {job.inquiries_email}, \
                {job.is_active}, \
                {job.creation_date}, \
                {job.post_date}, \
                {job.closed_date}, \
                {job.start_date}, \
                {job.deadline_date}, \
                {job.description}\n \
                "
            )
