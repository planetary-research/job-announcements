import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Admin(db.Model):
    orcid = db.Column(db.String(length=19), primary_key=True)
    name = db.Column(db.String)
    role_id = db.Column(db.Integer, db.ForeignKey("user_role.role_id"), nullable=False, default=1)

    def __repr__(self):
        return "<Admin %s>" % self.orcid


class Block(db.Model):
    orcid = db.Column(db.String(length=19), primary_key=True)
    name = db.Column(db.String)

    def __repr__(self):
        return "<Block %s>" % self.orcid


class Jobs(db.Model):
    job_slug = db.Column(db.String, nullable=False, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("job_category.category_id"), nullable=False, default=0)
    title = db.Column(db.String, nullable=False, default='')
    description = db.Column(db.String, nullable=False)
    application_instructions = db.Column(db.String, default='')
    institution = db.Column(db.String, default='')
    department = db.Column(db.String, default='')
    country = db.Column(db.String, default='')
    city = db.Column(db.String, default='')
    work_arrangement = db.Column(db.String, default='')
    official_announcement_url = db.Column(db.String, default='')
    duration = db.Column(db.String, default='')
    can_extend = db.Column(db.String, default='')
    salary = db.Column(db.String, default='')
    number_positions = db.Column(db.Integer, default=1)
    reference_code = db.Column(db.String, default='')
    inquiries_name = db.Column(db.String, default='')
    inquiries_email = db.Column(db.String, default='')
    owner_orcid = db.Column(db.String(length=19), default='')
    owner_name = db.Column(db.String, default='')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now(datetime.UTC))
    post_date = db.Column(db.DateTime, default=None)
    closed_date = db.Column(db.DateTime, default=None)
    start_date = db.Column(db.DateTime, default=None)
    deadline_date = db.Column(db.DateTime, default=None)

    def __repr__(self):
        return "<Jobs %s>" % self.job_slug


class JobCategory(db.Model):
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(length=255), nullable=False)

    def __repr__(self):
        return "<JobCategory %s>" % self.name


class UserRole(db.Model):
    role_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=255), nullable=False)

    def __repr__(self):
        return "<UserRole %s>" % self.name
