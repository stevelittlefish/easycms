"""
This module contains the code to handle the authentication system for the site
"""

import logging
from functools import wraps

from flask import session, redirect, request, url_for
import bcrypt

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

KEY_AUTH = 'auth'
KEY_LOGIN_DEST = 'login_dest'

# Auth record keys
KEY_VERSION = 'version'
KEY_ROLE_ID = 'role_id'
KEY_EMAIL = 'email'
KEY_FULL_NAME = 'full_name'
KEY_BACKEND = 'backend'
KEY_USER_ID = 'user_id'


def logged_in():
    return KEY_AUTH in session


def set_login_dest(url):
    session[KEY_LOGIN_DEST] = url


def get_login_dest():
    if KEY_LOGIN_DEST in session:
        return session[KEY_LOGIN_DEST]
    else:
        return url_for('main.index')


def get_role_id():
    if not logged_in():
        return None

    return session[KEY_AUTH][KEY_ROLE_ID]


def get_email():
    if not logged_in():
        return None

    return session[KEY_AUTH][KEY_EMAIL]


def get_full_name():
    if not logged_in():
        return None

    if 'full_name' not in session[KEY_AUTH]:
        return None

    return session[KEY_AUTH][KEY_FULL_NAME]


def get_user_id():
    if not logged_in():
        return None

    return session[KEY_AUTH][KEY_USER_ID]


def get_user():
    """
    Get the currently logged in user

    :return: The user
    """
    from models import User

    if not logged_in():
        return None

    return User.query.filter(User.id == get_user_id()).one()


def is_backend_user():
    if not logged_in():
        return False

    return session[KEY_AUTH][KEY_BACKEND]


def login_redirect():
    # Store destination in session
    set_login_dest(request.url)

    return redirect(url_for('main.login'))


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return login_redirect()

        # Allow access to the decorated view
        return f(*args, **kwargs)

    return decorated


def hash_password(plain_password):
    """
    Hash the users password.  We need the email_address to be able to support legacy MD5 passwords with use the
    email_address as salt

    :param plain_password: The plain password, as the user typed it in

    :return: The hashed password
    """
    return bcrypt.hashpw(plain_password, bcrypt.gensalt(10))


def check_password(password, plain_password):
    """
    :param password: The encrypted password saved on the user
    :param plain_password: The password typed in by the user

    :return: Whether or not the password matches
    """
    # Bcrypt handled seperately because of the way it handles salt
    try:
        return bcrypt.hashpw(plain_password, password) == password
    except UnicodeEncodeError:
        return False


def create_session(user):
    """Creates the session for an authenticated user"""
    from permissions import Permissions

    # Get items from session that we need to persist
    dest = get_login_dest()

    # Create the session
    session.clear()

    # Re-add persistent stuff to session
    session[KEY_LOGIN_DEST] = dest

    # Create the auth record and add to session
    auth_record = create_auth_record(user.email_address, user.id, user.role.id, user.full_name,
                                     user.has_permission(Permissions.admin))
    session[KEY_AUTH] = auth_record


def destroy_session():
    session.clear()


def create_auth_record(email, user_id, role_id, full_name, backend):
    """
    Create the auth record, store it in the session and return it

    :param email: The user's email address
    :param user_id: The user's id
    :param role_id: The user's role id
    :param full_name: The user's full name
    :param backend: Does this user have the 'backend' permission?

    :return: The auth record
    """
    auth_record = {
        KEY_EMAIL: email,
        KEY_USER_ID: user_id,
        KEY_ROLE_ID: role_id,
        KEY_FULL_NAME: full_name,
        KEY_BACKEND: backend
    }

    return auth_record


