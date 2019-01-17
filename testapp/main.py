"""
Main blueprint for test app
"""

import logging

from flask import Blueprint, render_template, redirect, url_for, current_app, request, abort, session, \
    jsonify
import easyforms
from easyforms.bs4 import Form
import easycms
import easycms.rssfeed
import easycms.comments

from models import db, User
import auth
from constants import posttypes
from permissions import has_permission, Permissions


__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

main = Blueprint('main', __name__)

CMS_NUM_PER_PAGE = 5


def error_page(error, title='Error'):
    return render_template('main/error_page.html', title=title, message=error)


def authenticate(email, plain_password):
    """
    This function authenticates a user, checking against the database and ensuring the entered username and password
    are correct.  If the user is authenticated then the necessary values are stored in the session, True is returned,
    and the login is complete.  Otherwise, nothing is stored in the session and False is returned.

    :param email: The email that the user typed in
    :param plain_password: The password that the user typed in
    :return: True if authentication was successful, otherwise False
    """

    # Load the user from the database
    user = User.query.filter(User.email_address == email).first()

    if user and user.check_password(plain_password):
        # login successful!
        log.info('Login successful for user \'%s\'' % user.email_address)
        if not user.role.is_normal_user():
            log.info('Logged in user has role \'%s\'' % user.role.name)
        # create the session
        auth.create_session(user)
        return True

    log.info('Login failed for \'%s\'' % email)
    return False


@main.route('/favicon.ico')
def favicon():
    return current_app.send_static_file('favicon.ico')


@main.route('/')
def index():
    # This is how wordpress does it
    if request.args.get('feed') == 'rss2':
        return rss_feed()

    pager = easycms.get_all_posts_pager(
        request.args.get('page', 1), num_per_page=CMS_NUM_PER_PAGE, post_type=posttypes.NEWS,
        session=db.session, allow_unpublished=has_permission(Permissions.admin)
    )

    return render_template('index.html', pager=pager)


@main.route('/posts/<string:post_code>', methods=['GET', 'POST'])
def view_blog_post(post_code):
    post = easycms.get_post_by_code(posttypes.NEWS, post_code, session=db.session,
                                    allow_unpublished=has_permission(Permissions.admin))
    if not post:
        abort(404)
    
    can_view_all = has_permission(Permissions.admin)
    prev_post = post.get_prev_post(include_non_published=can_view_all)
    next_post = post.get_next_post(include_non_published=can_view_all)

    # Related posts
    related_posts = easycms.get_all_posts_query(post_type=post.post_type).filter(
        easycms.models.CmsPost.id != post.id
    )[:4]

    can_edit = has_permission(Permissions.admin)
    can_edit_seo = has_permission(Permissions.admin)
    can_manage_comments = has_permission(Permissions.admin)
    show_tools = can_edit or can_edit_seo

    comments_form = easycms.comments.create_and_process_comment_form(post, session=db.session)

    return render_template('view_post.html', post=post, prev_post=prev_post,
                           next_post=next_post, can_edit=can_edit, can_edit_seo=can_edit_seo,
                           show_tools=show_tools, related_posts=related_posts,
                           comments_form=comments_form, can_manage_comments=can_manage_comments)


@main.route('/login', methods=['GET', 'POST'])
def login():
    """Handle a login request, authenticate the user and create the session"""
    error = None

    form = Form([
        easyforms.EmailField('email', width=8, required=True, placeholder='Enter your email address...'),
        easyforms.PasswordField('password', width=8, required=True, placeholder='Enter your password...'),
        easyforms.SubmitButton('submit', 'Log In', width=8, css_class='btn-primary btn-block')
    ], label_width=4, submit_text=None, form_name='sign-in')

    if form.ready:
        # Account not locked -authenticate
        logged_in = authenticate(form['email'], form['password'])

        if logged_in:
            # redirect the user to wherever they were going
            return redirect(auth.get_login_dest())
        else:
            # Display a message to the user
            error = 'The email or password you entered is incorrect.'

    return render_template('login.html', form=form, error=error)


@main.route('/logout')
def logout():
    auth.destroy_session()

    return redirect(url_for('main.index'))


@main.route('/rss')
def rss_feed():
    return easycms.rssfeed.rss_flask_view('Amazing Wonderful Blog of Awesome',
                                          'This is the incredible blog from a site that doesn\'t even exist!')


### Test stuff ################################################################

@main.route('/session')
def view_session():
    return jsonify(dict(session))


