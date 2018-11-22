"""
Contains the database models for the application
"""

import logging
import datetime

import bcrypt
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

metadata = sqlalchemy.MetaData()
db = SQLAlchemy(metadata=metadata)

# Association table for roles
role_permission = db.Table('role_permission',
                           db.Column('role_id', db.Integer, db.ForeignKey('role.id')),
                           db.Column('permission_id', db.Integer, db.ForeignKey('permission.id')))


def _hash_user_password(plain_password):
    return bcrypt.hashpw(plain_password, bcrypt.gensalt(10))


class Permission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)

    def __init__(self, name):
        self.name = name


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)

    permissions = db.relationship(lambda: Permission, secondary=role_permission, order_by=Permission.name,
                                  backref=db.backref('roles', order_by=name))

    def __init__(self, name):
        self.name = name

    def has_permission(self, permission):
        for p in self.permissions:
            # Admin permission results in user having all other permissions
            if p.name == permission or p.name == 'Admin':
                return True

        return False

    def __repr__(self):
        return '<Role:%s(%s)>' % (self.name, self.id)

    def is_normal_user(self):
        return self.name == 'user'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String, nullable=False, unique=True)
    full_name = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    created = db.Column(db.DateTime, nullable=False)
    cms_user_id = db.Column(db.BigInteger, db.ForeignKey('cms_user.id'), nullable=False,
                            unique=True)

    role = db.relationship('Role', lazy='joined', uselist=False)
    
    def __init__(self, email_address, full_name, plain_password, role, cms_user):
        self.email_address = email_address
        self.full_name = full_name
        self.password = _hash_user_password(plain_password)
        self.role = role
        self.created = datetime.datetime.utcnow()
        self.cms_user = cms_user
    
    @property
    def cms_user(self):
        from easycms.models import CmsUser
        return db.session.query(CmsUser).filter(CmsUser.id == self.cms_user_id).one()

    @cms_user.setter
    def cms_user(self, value):
        self.cms_user_id = value.id

    def check_password(self, plain_password):
        return bcrypt.hashpw(plain_password, self.password) == self.password

    def change_password(self, plain_password):
        self.password = _hash_user_password(plain_password)

    def has_permission(self, permission):
        if self.role.has_permission(permission):
            return True
