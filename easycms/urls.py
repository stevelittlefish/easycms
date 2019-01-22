"""
Functions to return URLs to pages provided by the system
"""

import logging

from flask import url_for

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def create_new_post(post_type):
    return url_for('easycms_editor.edit_post', post_type=post_type)


def view_categories():
    return url_for('easycms_editor.view_categories')


def view_comments(deleted=None, approved=None, pending=None):
    return url_for('easycms_editor.view_comments', deleted=deleted, approved=approved, pending=pending)
