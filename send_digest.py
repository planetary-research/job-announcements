"""
This script will send an email that contains a digest of all job
announcements that were published over a 1 week time period. All personalized
options are set in the project's .env file.
"""
import os
import datetime
import smtplib
from email.message import EmailMessage
import numpy as np
from dateutil.relativedelta import relativedelta
from db_models import Jobs
from app import app

import config

with app.app_context():
    date_now = datetime.datetime.now(datetime.UTC)

    # date with time set to 0
    date_now_zero = datetime.datetime(date_now.year, date_now.month, date_now.day, tzinfo=datetime.UTC)
    start_weekday = config.start_weekday

    stop = date_now_zero
    start = date_now_zero - relativedelta(days=7)

    # determine how many days are between now and the weekday of stop
    offset = date_now.weekday() - start_weekday
    if offset < 0:
        offset += 7

    stop = stop - relativedelta(days=offset)
    start = start - relativedelta(days=offset)

    jobs_list = dict()
    sum_category = np.zeros(len(config.categories))
    # Create list of all job announcements posted between start and stop
    for row in Jobs.query.filter_by(is_active=True).order_by(Jobs.post_date.asc()).all():
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

        post_date = row.post_date.replace(tzinfo=datetime.UTC)  # timezone is lost in sqlalchemy

        if post_date >= start and post_date < stop:
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

    message = (
        '<style>' +
        '    table.job-table {' +
        '    font-size: 0.8em;' +
        '    border-bottom: 2px solid #aaa;' +
        '    layout: auto;' +
        '    border-collapse: collapse;' +
        '}' +
        '.job-table th {' +
        '    border-right: 1px solid #ddd;' +
        '    text-align: left;' +
        '    padding: 0.3em 0.8em 0.3em 0.8em;' +
        '    background-color: #3176b1;' +
        '    color: #ffffff;' +
        '}' +
        '.job-table tr {' +
        '    vertical-align: top;' +
        '}' +
        '.job-table td {' +
        '    border: 1px solid #ddd;' +
        '    text-align: left;' +
        '    padding: 0.3em 0.8em 0.3em 0.8em;' +
        '}' +
        '.job-table tr:nth-of-type(even) {' +
        '    background-color: #f5f5f5;' +
        '}' +
        '</style>'
    )

    # Only process if there is a new announcement
    if sum_category.sum() > 0:
        # Create HTML message with list of announcments, organized by category
        message += (
            '<div>\n' +
            '<h2>' + config.site_title + '</h2>\n' +
            '<p>WEEKLY DIGEST\n' +
            '<br />' + start.strftime("%B %d, %Y") + ' to ' + (stop - relativedelta(days=1)).strftime("%B %d, %Y") + '</p><br />'
            )

        for id, category in enumerate(config.categories):
            if mask[id]:
                message += (
                    '<p><b>' + category + '</b></p>\n' +
                    '<table class="job-table">\n' +
                    '<thead>\n' +
                    '<tr>\n' +
                    '<th>Title</th>\n' +
                    '<th style="width: 22em;">Institution</th>\n' +
                    '<th style="width: 15em;">Location</th>\n' +
                    '<th style="width: 7em;">Deadline</th>\n' +
                    '<th style="width: 7em;">Posted</th>\n' +
                    '</tr>\n' +
                    '</thead>\n' +
                    '<tbody>\n'
                    )

                for name, desc in jobs_list.items():
                    if desc[0] == id:
                        message += (
                            '<tr>\n' +
                            '<td><a href="' + desc[1] + '">' + desc[2] + '</a></td>\n' +
                            '<td>' + desc[3] + '</td>\n' +
                            '<td>' + desc[4] + '</td>\n' +
                            '<td>' + desc[5] + '</td>\n' +
                            '<td>' + desc[6] + '</td>\n' +
                            '</tr>\n'
                        )

                message += (
                    '</tbody>\n' +
                    '</table>\n'
                )

        message += '</div>'

        # Send email
        msg = EmailMessage()
        msg['From'] = config.site_title + " <" + config.smtp_email + ">"
        msg['To'] = config.email_digest
        msg['Subject'] = "[" + config.site_title + "] Weekly digest"
        msg['Reply-To'] = "do-not-reply <" + config.smtp_reply_email + ">"
        msg.add_alternative(message, subtype='html')

        try:
            if config.smtp_port == 465:
                with smtplib.SMTP_SSL(config.smtp_server, 465) as server:
                    server.login(config.smtp_email, config.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
                    server.starttls()  # Secure the connection
                    server.login(config.smtp_email, config.smtp_password)
                    server.send_message(msg)
            print("Email sent successfully!")
        except Exception as e:
            print(f"Failed to send email: {e}")
