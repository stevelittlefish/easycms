"""
This is where the emails would be sent - but instead we just print some stuff to the log
"""

import logging

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def send_blog_comment_reply_notification_email(email, name, comment):
    log.info('**EMAIL:** to {} <{}> - your comment has been replied to: {}'.format(
        name, email, comment.content
    ))


def send_blog_comment_notification_email(blog_notification_email, comment):
    log.info('**EMAIL:** Hi {} - the following comment needs moderation: {}'.format(
        blog_notification_email, comment.content
    ))


