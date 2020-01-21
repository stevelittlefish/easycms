"""
Contains code for building re-usable forms and fields
"""

import logging

import easyforms
from easyforms import validate

from .settings import get_settings


__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def get_post_important_fields(categories, post=None):
    """
    Returns the fields that are (probably) needed to create an empty post
    """
    
    settings = get_settings()

    fields = [
        easyforms.TextField('title', required=True, value=post.title if post else None, width=10)
    ]

    fields += [
        easyforms.ObjectListSelectField('category', categories, required=True,
                                        value=post.category if post else categories[0], width=3),
        easyforms.TextField('tagline', required=True, value=post.tagline if post else None,
                            help_text='A very short description of the post. You can copy + paste the first sentence here! Max {} characters'.format(settings.tagline_max_length),
                            width=10, validators=[validate.max_length(settings.tagline_max_length)])
    ]

    if settings.post_main_image_enabled:
        fields.append(
            easyforms.FilemanagerField('main-image', label='Image', width=10,
                                       value=post.main_image_url if post else None,
                                       required=settings.post_main_image_required,
                                       help_text='The main image to display for this post')
        )

    return fields
