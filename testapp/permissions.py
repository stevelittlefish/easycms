"""
Contains all of the permissions for the webapp
"""

import logging
from functools import wraps

from flask import abort

from models import Role
import auth
import collections

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'


log = logging.getLogger(__name__)

all_roles = None


# noinspection PyClassHasNoInit
class Permissions:
    """
    This is the list of all permissions - the database list of permissions is generated from this by the create script
    """
    admin = 'Admin'

    @classmethod
    def as_list(cls):
        """Return the list of all permissions"""
        return [getattr(cls, attr) for attr in dir(cls)
                if not isinstance(attr, collections.Callable) and not attr.startswith("__") and attr != 'as_list']


class CachedRole:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.permissions = []

    def has_permission(self, permission):
        for p in self.permissions:
            # Admin permission results in user having all other permissions
            if p.name == permission or p.name == 'Admin':
                return True

        return False
    
    def __repr__(self):
        return '<CachedRole: %s>' % self.name


class CachedPermission:
    def __init__(self, id, name):
        self.id = id
        self.name = name


# noinspection PyShadowingBuiltins
def reload():
    """Reload all of the roles and store them in hash table"""
    global all_roles

    log.info('Reloading roles')

    all_roles = {}
    roles = Role.query.all()
    for role in roles:
        cached_role = CachedRole(role.id, role.name)
        for permission in role.permissions:
            cached_permission = CachedPermission(permission.id, permission.name)
            cached_role.permissions.append(cached_permission)
            
        all_roles[role.id] = cached_role
    
    log.debug('Roles loaded: %s' % all_roles)


def get_role():
    role_id = auth.get_role_id()
    if role_id is None:
        return None
    
    # get the cached role object
    role = None
    if role_id in all_roles:
        role = all_roles[role_id]

    if not role:
        raise Exception('Unknown role: %s' % role_id)

    return role


def has_permission(permission):
    # log.debug('Permission check: %s' % permission)
    role = get_role()

    if not role:
        log.debug('User has no role, returning False')
        return False

    # log.debug('User has role: %s' % role.name)

    if role.has_permission(permission):
        return True

    # If role does not have permission,s then check the extra permissions
    if permission in auth.get_permission_names():
        return True

    return False


def requires_permission(permission):
    # Normal (non-parameterised decorator):
    def decorator(f):
        # Actual function wrapper:
        @wraps(f)
        def decorated(*args, **kwargs):
            auth.check_reset_session_timeout()
            
            # Normal login check
            if not auth.logged_in():
                return auth.login_redirect()

            # Permission check
            if not has_permission(permission):
                return abort(403)

            return f(*args, **kwargs)

        return decorated

    return decorator
