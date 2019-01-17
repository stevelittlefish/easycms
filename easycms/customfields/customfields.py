"""
Custom field classes for easyforms
"""

import logging

import easyforms

from .env import env

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


class AntiSpamField(easyforms.TextField):
    """
    This field is invisible - it's intention is to fool spam scripts into filling it in when really it needs
    to be empty in order to post a comment!
    """
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)

        self.form_group_css_class = 'blog-nickname-field'

    def render(self):
        return env.get_template('anti_spam_field.html').render(field=self)

