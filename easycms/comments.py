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
from .settings import get_settings
import easycms

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


class FakeForm():
    def render(self):
        return flask.Markup('<div class="alert alert-danger"><strong style="color: red;">Comments Disabled</strong></div>')


def get_ckeditor_config():
    return get_settings().ckeditor_config.clone(
        subscript_enabled=False,
        superscript_enabled=False,
        cut_enabled=False,
        copy_enabled=False,
        paste_enabled=False,
        undo_enabled=False,
        redo_enabled=False,
        anchor_enabled=False,
        image_enabled=False,
        codesnippet_enabled=False,
        link_enabled=False,
        table_enabled=False,
        styles_enabled=False,
        hr_enabled=False,
        allow_all_extra_content=False,
        format_tags='p;h4',
        custom_styles_js_url=None,
        custom_contents_css_url=None,
        force_paste_as_plain_text=True
    )


def get_comment_reply_html_field(name, value=None, required=False):
    return easyforms.CkeditorField(name, value=value, required=required, config=get_ckeditor_config())


def create_and_process_comment_form(post, session=None, action='', form_type=easyforms.VERTICAL):
    """
    COMMITS!
    """
    if session is None:
        session = db.session
    
    # Move post onto the correct session
    post = session.merge(post)

    settings = get_settings()
    
    if not settings.comments_enabled:
        return FakeForm()

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
        fields.append(get_comment_reply_html_field('content', required=True))

    fields.append(easyforms.HiddenField('reply-to', ''))
    fields.append(easyforms.SubmitButton('Add Comment', css_class='btn-primary btn-lg'))

    try:
        form = Form(fields, submit_text=None, label_width=2, action=action, form_type=form_type)
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
            reply_comment = easycms.get_comment_by_id(reply_id)
            if not reply_comment:
                abort(404)

        if ac.can_post_comments_as_admin():
            logged_in_user = session.merge(ac.get_logged_in_cms_user())

            comment = models.CmsComment(post, content, user=logged_in_user, author=logged_in_user.author,
                                        author_ip=request.remote_addr, user_agent=str(request.user_agent),
                                        reply_to=reply_comment)
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
            
            comment_added_hook = settings.comment_added_hook
            if comment_added_hook:
                comment_added_hook(comment)

            # If the comment is an admin and it is a reply, send an email to the user whose comment is being replied to
            comment_reply_hook = settings.comment_reply_hook
            if comment_reply_hook and comment.approved and comment.reply_to_id:
                comment_reply_hook(comment)

            flash('Comment Added!', 'success')
            form.clear()

    # Make it look like nickname is required!
    if form.submitted and not ac.can_post_comments_as_admin and not form['nickname']:
        form.set_error('nickname', 'Required')

    return form

