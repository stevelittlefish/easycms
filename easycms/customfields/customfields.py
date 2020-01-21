"""
Custom field classes for easyforms
"""

import logging
from datetime import datetime

import easyforms
from littlefish import timetool

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


class PublishField(easyforms.Field):
    """
    Allows the user to select whether or not to publish the post, and to
    set the published date / time
    """
    def __init__(self, name, post, **kwargs):
        super().__init__(name, **kwargs)

        self.post = post

    def render(self):
        # Default published date will be the date that the post was published or empty string
        default_date = ''
        default_hour = ''
        default_minute = ''
        if self.value:
            default_date = timetool.datetime_to_datepicker(self.value)
            default_hour = self.value.hour
            default_minute = self.value.minute

        return env.get_template('publish_field.html').render(
            field=self, post=self.post, default_date=default_date, default_hour=default_hour,
            default_minute=default_minute
        )

    def extract_value(self, data):
        main_value = data[self.name]
        
        if main_value == 'False':
            self.value = None
        elif main_value == 'Now':
            self.value = datetime.utcnow()
        elif main_value == 'Keep':
            self.value = self.post.published
        elif main_value == 'Date':
            date_str = data['{}-custom-date'.format(self.name)]
            hour_str = data['{}-custom-hour'.format(self.name)]
            minute_str = data['{}-custom-minute'.format(self.name)]
            
            try:
                try:
                    date = timetool.date_from_datepicker(date_str)
                except ValueError:
                    raise ValueError('"{}" is not a valid date in the format DD/MM/YYYY'.format(date_str))

                hour = int(hour_str)
                if hour < 0 or hour > 23:
                    raise ValueError('Hour must be between 0 and 23')

                minute = int(minute_str)
                if minute < 0 or minute > 59:
                    raise ValueError('Minute must be between 0 and 59')

                # Build the final datetime!
                self.value = datetime(date.year, date.month, date.day, hour, minute)

            except ValueError as e:
                self.error = str(e)

        else:
            self.value = None
            self.error = 'Invalid Option'
