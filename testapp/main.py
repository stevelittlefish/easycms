"""
Main blueprint for test app
"""

import logging

from flask import Blueprint, render_template, redirect, url_for
import easyforms
from easyforms.bs4 import Form

from models import User
import auth


__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

main = Blueprint('main', __name__)


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


@main.route('/')
def index():
    return render_template('index.html')


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


