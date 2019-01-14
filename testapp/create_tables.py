# coding=utf-8
import logging
import traceback

from sqlalchemy.exc import IntegrityError

import models
import easycms.models
from models import db
from permissions import Permissions

log = logging.getLogger(__name__)

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'


print_stack_traces = False


def insert(obj):
    db.session.add(obj)

    try:
        db.session.commit()
        log.info('Inserted OK')
    except IntegrityError:
        if print_stack_traces:
            log.info('Insert Failed!')
            traceback.print_exc()
        else:
            log.info('%s already exists' % obj)
        db.session.rollback()


def add_permission(name):
    permission = models.Permission(name)
    log.info('Adding permission %s...' % name)
    insert(permission)


def add_role(name, permissions, copy_from_role=None):
    role = models.Role(name)
    log.info('Adding role %s with permissions %s...' % (name, permissions))

    db.session.add(role)

    try:
        db.session.commit()
        log.info('Inserted OK')

    except IntegrityError:
        log.info('%s already exists' % role)
        db.session.rollback()

        role = models.Role.query.filter(models.Role.name == name).first()
    
    # Copy from the role if needed
    if copy_from_role:
        log.info('Copying permissions from role %s' % copy_from_role.name)
        permission_set = set()
        for permission in permissions:
            permission_set.add(permission)
        
        for permission in copy_from_role.permissions:
            permission_set.add(permission.name)
        
        permissions = list(permission_set)
    
    # Add the permissions to the role
    for permission in permissions:
        if role.has_permission(permission):
            log.info('%s already has permission %s' % (role.name, permission))
        else:
            # Load the permission and add it to the role
            p = models.Permission.query.filter(models.Permission.name == permission).first()

            if not p:
                raise Exception('Permission does not exist: %s' % permission)

            log.info('Adding %s to %s' % (p.name, role.name))
            role.permissions.append(p)

            db.session.commit()
            log.info('Inserted OK')
    
    return role


def add_user(email_address, full_name, password, role):
    log.info('Creating user \'%s\' with role \'%s\'' % (email_address, role.name))
    
    existing_user = models.User.query.filter(models.User.email_address == email_address).one_or_none()
    if existing_user:
        log.info('User already exists')
        return

    cms_user = easycms.models.CmsUser(full_name)
    db.session.add(cms_user)
    db.session.flush()
    user = models.User(email_address, full_name, password, role, cms_user)
    insert(user)
    

def update_permissions():
    # Add permissions
    for permission in Permissions.as_list():
        add_permission(permission)

    # Add roles
    add_role('admin', [Permissions.admin])


def create_tables(app, drop_all=False):
    if drop_all:
        log.info('Running in test mode - allowing drop all')
        log.info('Dropping all tables!')
        db.session.commit()
        db.drop_all()

    log.info('Creating tables')
    db.create_all()

    log.info('Updating roles and permissions')
    update_permissions()
    
    log.info('Inserting Users')
    role_admin = models.Role.query.filter(models.Role.name == 'admin').one()

    add_user('admin@a.com', 'Admin User', 'qwe123', role_admin)

    log.info('Inserting Authors')
    bilbo = easycms.models.CmsAuthor('Bilbo Baggins')
    insert(bilbo)

