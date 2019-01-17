"""
Functions to deal with comments
"""

import logging
import re
import datetime

import easyforms
import easyforms.exceptions
from easyforms.bs4 import Form
import flask
from flask import request, abort, flash

from . import accesscontrol
from .models import db
from . import models
from . import customfields
from . import constants

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def create_and_process_comment_form(post, session):
    """
    COMMITS!
    """
    ac = accesscontrol.get_access_control()
    error = None

    fields = []
    if not ac.can_post_comments_as_admin():
        fields.append(easyforms.TextField('name', required=True, value=request.cookies.get(constants.COMMENT_NAME_COOKIE_NAME)))
        # Anti spam!
        # This field will be hidden using CSS and if a value is entered here we will assume that it is a spam script
        fields.append(customfields.AntiSpamField('nickname', required=False))
        fields.append(easyforms.EmailField('email', required=True,
                                           value=request.cookies.get(constants.COMMENT_EMAIL_COOKIE_NAME)))
        fields.append(easyforms.TextAreaField('content', label='Comment', required=True))
    else:
        # fields.append(expressfields.ProductEditorHtmlField('content', label='Comment', required=True, no_smiley=True, no_image=True))
        fields.append(easyforms.HtmlField('content'))

    fields.append(easyforms.HiddenField('reply-to', ''))
    fields.append(easyforms.SubmitButton('Add Comment', css_class='btn-primary btn-lg'))

    try:
        form = Form(fields, submit_text=None, label_width=2, action='#add-comment')
    except easyforms.exceptions.FieldNotFound as e:
        # this is to catch the errors from people hacking the blog forms by submitting empty fields
        log.warn('Someone trying to hack us? %s' % e)
        abort(400)

    if form.submitted:
        if form['reply-to']:
            try:
                int(form['reply-to'])
            except ValueError:
                log.warn('Someone has submitted some junk in the reply id field!  Value=%s' % form['reply-to'])
                abort(400)

            # reply_to_id = form['reply-to']
            # reply_to_author = get_comment_author_name(reply_to_id)

    if form.ready:
        if ac.can_post_comments_as_admin():
            content = form['content']
        else:
            content = flask.escape(form['content'])
            parts = re.split(r'[\n\r]+', content)
            content = '<p>%s</p>' % '</p><p>'.join(parts)

        reply_id = form['reply-to']

        reply_comment = None

        if reply_id:
            reply_comment = db.session.query(
                models.CmsComment
            ).filter(
                models.CmsComment.id == reply_id
            ).one_or_none()

            if not reply_comment:
                abort(404)

        if ac.can_post_comments_as_admin():
            # TODO: fix this
            comment = models.CmsComment(post, content, author=ac.get_logged_in_cms_user(),
                                        author_ip=request.remote_addr,
                                        user_agent=str(request.user_agent), reply_to=reply_comment)
            comment.approved = True
        else:
            # Save values in cookie
            cookie_name = form['name']
            cookie_email = form['email']

            @flask.after_this_request
            def save_cookie(response):
                response.set_cookie(constants.COMMENT_NAME_COOKIE_NAME, cookie_name)
                response.set_cookie(constants.COMMENT_EMAIL_COOKIE_NAME, cookie_email)
                return response

            # See if they are allowed to comment
            cut_off = datetime.datetime.utcnow() - datetime.timedelta(minutes=2)
            made_comment = False

            for comment in post.comments:
                if comment.author_ip == request.remote_addr and comment.timestamp > cut_off:
                    made_comment = True
                    break

            if made_comment:
                error = 'You can\'t comment as you have recently commented on this post.  Wait a while and try again.'
            elif form['nickname']:
                error = 'Comment failed'
                log.info('Not posting comment due to spam check')
                log.info('ANTISPAM! User Agent: %s | ip: %s | Post Data: %s' % (request.user_agent, request.remote_addr, request.form))
            else:
                # Make the comment
                # TODO: fix this
                comment = models.CmsComment(
                    post, content, author_name=form['name'], author_email=form['email'],
                    author_ip=request.remote_addr, user_agent=str(request.user_agent),
                    reply_to=reply_comment
                )

        if error:
            flash(error, 'danger')
        else:
            session.add(comment)
            session.commit()
            
            log.info('TODO: implement emails!')
            # TODO

            # # If the comment is an admin and it is a reply, send an email to the user whose comment is being replied to
            # if comment.approved and comment.reply_to_id:
            #     email = comment.reply_to.get_email_address()
            #     name = comment.reply_to.get_author_name()
            #     sendemail.send_blog_comment_reply_notification_email(email, name, comment)

            # if not comment.approved:
            #     # Send the notification emails
            #     sendemail.send_blog_comment_notification_email(blog_notification_emails, comment)

            flash('Comment Added!', 'success')
            form.clear()

    # Make it look like nickname is required!
    if form.submitted and not ac.can_post_comments_as_admin and not form['nickname']:
        form.set_error('nickname', 'Required')

    return form

