"""
Access control for easy cms
"""

import logging
from functools import wraps

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

_access_control = None


class AccessControlConfig(object):
    """
    Extend this class and redefine the methods below to configure who can do what
    """
    def get_logged_in_cms_user(self):
        return None
    
    def can_view_editor(self):
        return True
    
    def can_edit_page(self):
        return True

    def can_edit_post(self):
        return True

    def can_edit_post_seo(self):
        return True

    def can_tag_post(self):
        """Can the user add (already existing tags) to a post?"""
        return self.can_edit_post()

    def can_manage_tags(self):
        """Can the user create new tags?"""
        return self.can_tag_post()

    def can_delete_post(self):
        return False

    def can_publish_post(self):
        return True

    def can_edit_category(self):
        return True
    
    def can_post_comments_as_admin(self):
        return self.can_moderate_comments() or self.can_edit_post()

    def can_moderate_comments(self):
        return True

    def can_access_filemanager(self):
        return True

    def can_manage_authors(self):
        return True


def init(access_control):
    global _access_control
    
    if access_control is None:
        _access_control = AccessControlConfig()
    else:
        _access_control = access_control


def get_access_control():
    global _access_control

    return _access_control


def _access_control_handler(access_control_method, f, args, kwargs):
    from . import editor

    access_control = get_access_control()

    ac_function = getattr(access_control, access_control_method) if access_control_method else lambda: True
    if not access_control.can_view_editor() or not ac_function():
        # Not allowed in!
        return editor.error_page('You don\'t have permission to view this page', title='Access Denied', http_status_code=403)

    # Allow access to the decorated view
    return f(*args, **kwargs)


def can_view_editor(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler(None, f, args, kwargs)

    return decorated


def can_edit_page(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_edit_page', f, args, kwargs)

    return decorated


def can_edit_post(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_edit_post', f, args, kwargs)

    return decorated


def can_tag_post(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_tag_post', f, args, kwargs)

    return decorated


def can_manage_tags(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_manage_tags', f, args, kwargs)

    return decorated


def can_edit_post_seo(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_edit_post_seo', f, args, kwargs)

    return decorated


def can_publish_post(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_publish_post', f, args, kwargs)

    return decorated


def can_delete_post(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_delete_post', f, args, kwargs)

    return decorated


def can_edit_category(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_edit_category', f, args, kwargs)

    return decorated


def can_moderate_comments(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_moderate_comments', f, args, kwargs)

    return decorated


def can_manage_authors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        return _access_control_handler('can_manage_authors', f, args, kwargs)

    return decorated

