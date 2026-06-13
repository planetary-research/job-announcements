"""
This script will clean the database of old job announcements.

All jobs that have exceed the application deadline by 120 days
(4 months) will be closed.

All jobs that have exceeded the application deadline by 1 year
will be deleted from the database.

All jobs that do not have an application deadline will be
deleted 1 year after they are posted.

All jobs that do not have an application deadline and that are closed
will be deleted 1 year after they were created.
"""
from db_models import db, Jobs
from app import app
import datetime

close_interval = 4 * 30
delete_interval = 365

now = datetime.datetime.now(datetime.UTC)
print('Now : ', now)

with app.app_context():
    for row in Jobs.query.all():
        creation_date = row.creation_date.replace(tzinfo=datetime.UTC)
        if row.post_date is not None:
            post_date = row.post_date.replace(tzinfo=datetime.UTC)
            closed_date = None
        else:
            post_date = None
            closed_date = row.closed_date.replace(tzinfo=datetime.UTC)

        if row.deadline_date is None:
            if post_date is not None:
                total_days = (now - post_date).days
            else:
                total_days = (now - creation_date).days

            if total_days > delete_interval:
                print('---')
                print(row.title)
                print('post_date: ', post_date)
                print('closed_date: ', closed_date)
                print('creation_date: ', creation_date)
                print("Number of days since post_date or creation_date: ", total_days)
                print('Job will be deleted.')
                row.delete()

        else:
            deadline_date = row.deadline_date.replace(tzinfo=datetime.UTC)
            total_days = (now - deadline_date).days

            if row.is_active:
                if total_days > close_interval:
                    print('---')
                    print(row.title)
                    print('deadline_date: ', deadline_date)
                    print('post_date: ', post_date)
                    print('closed_date: ', closed_date)
                    print('creation_date: ', creation_date)
                    print('Days since deadline_date: ', total_days)
                    print("Closing job")
                    row.is_active = False

            if total_days > delete_interval:
                print('---')
                print(row.title)
                print('deadline_date: ', deadline_date)
                print('post_date: ', post_date)
                print('closed_date: ', closed_date)
                print('creation_date: ', creation_date)
                print('Days since deadline_date: ', total_days)
                print('Job will be deleted.')
                row.delete()

    commit = input("Commit changes to the database? [y/n] > ")
    if commit.lower == 'y':
        db.session.commit()
