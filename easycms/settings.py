"""
Manages configuration for easy cms
"""

import logging
import os

from flask import url_for
from easyforms import CkeditorConfig
from flaskfilemanager import filemanager

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

_settings = None
_page_defs = None


class PageDef(object):
    def __init__(self, code, title):
        self.code = code
        self.title = title


class EasyCmsSettings(object):
    def __init__(
            self,
            home_link_text='EasyCMS',
            home_link_endpoint='easycms_editor.index',
            website_name='EasyCMS',
            logout_endpoint=None,
            tagline_max_length=170,
            snippets_enabled=True,
            snippet_image_width=350,
            snippet_image_height=200,
            snippet_image_subfolder='cms-snippet-images',
            snippet_description_max_length=170,
            snippet_missing_image_url=None,
            pil_saved_image_quality=98,
            pil_saved_image_subsampling=0,
            pil_saved_image_compression_level=9,
            init_filemanager=True,
            filemanager_url_prefix='/fm',
            ckeditor_config=None,
            custom_stylesheet_url=None,
            editor_base_template='easycms/root.html',
            post_main_image_enabled=False,
            post_main_image_width=None,
            post_main_image_height=None,
            post_main_image_required=False,
            post_code_is_edittable=False,
            view_post_url_function=None,
            comments_enabled=False,
            comment_added_hook=None,
            comment_reply_hook=None
    ):
        """
        :param home_link_text: Text for home link in editor
        :param home_link_endpoint: Flask endpoint for home link to point to
        :param website_name: Name of website - used in editor pages
        :param logout_endpoint: Flask endpoint for logout link to point to
        :param tagline_max_length: Maximum length for the "tagline"
        :param snippets_enabled: Enable the snippets system
        :param snippet_image_width: Width of snippet image in pixels
        :param snippet_image_height: Height of snippet image in pixels
        :param snippet_image_subfolder: Subfolder inside filemanager directory to store snippet images
        :param snippet_description_max_length: Maximum length of snippet text
        :param snippet_missing_image_url: URL of image to use when there is no snippet image
        :param pil_saved_image_quality: Quality to save system generated images i.e. snippet images
        :param pil_saved_image_subsampling: Subsampling to save system generated images i.e. snippet images
        :param pil_saved_image_compression_level: Compression to save system generated images i.e. snippet images
        :param init_filemanager: Whether or not to automatically initialise the filemanager
        :param filemanager_url_prefix: URL prefix for filemanager
        :param ckeditor_config: easyforms.CkeditorConfig to configure CK Editor fields in the CMS editor
        :param custom_stylesheet_url: URL of custom stylesheet for rendering post content
        :param editor_base_template: Path of base template if you wish to override the default base template
        :param post_main_image_enabled: Do posts have a "main image" - an image that is not part of the regular content
        :param post_main_image_width: Unused
        :param post_main_image_height: Unused
        :param post_main_image_required: Is a "main" image required? Otherwise it will be optional
        :param post_code_is_edittable: Can the code of a post be editted?
        :param view_post_url_function: Set to a function that takes a post as its only argument and returns a url
                                       to view that post. The returned URL must be a full URL (i.e. use
                                       _external=True if using flask.get_url)
        :param comments_enabled: Are comments enabled?
        :param comment_added_hook: Set to a function which takes a single parameter to add a comment hook.
                                   Whenever a comment is added to the site this function will be called and the
                                   newly added comment will be passed in
        :param comment_reply_hook: A function which takes a single parameter to add a reply hook. Whenever
                                   a comment is approved, and that comment is replying to another comment, this
                                   function will be called with the newly added comment
        """
        self.home_link_text = home_link_text
        self.home_link_endpoint = home_link_endpoint
        self.website_name = website_name
        self.logout_endpoint = logout_endpoint
        self.tagline_max_length = tagline_max_length
        self.snippets_enabled = snippets_enabled
        self.snippet_image_width = snippet_image_width
        self.snippet_image_height = snippet_image_height
        self.snippet_image_subfolder = snippet_image_subfolder
        self.snippet_description_max_length = snippet_description_max_length
        self.snippet_missing_image_url = snippet_missing_image_url
        self.pil_saved_image_quality = pil_saved_image_quality
        self.pil_saved_image_subsampling = pil_saved_image_subsampling
        self.pil_saved_image_compression_level = pil_saved_image_compression_level
        self.init_filemanager = init_filemanager
        self.filemanager_url_prefix = filemanager_url_prefix
        self._ckeditor_config = ckeditor_config
        self.custom_stylesheet_url = custom_stylesheet_url
        self.editor_base_template = editor_base_template
        self.post_main_image_enabled = post_main_image_enabled
        self.post_main_image_width = post_main_image_width
        self.post_main_image_height = post_main_image_height
        self.post_main_image_required = post_main_image_required
        self.post_code_is_edittable = post_code_is_edittable
        self.view_post_url_function = view_post_url_function
        self.comments_enabled = comments_enabled
        self.comment_added_hook = comment_added_hook
        self.comment_reply_hook = comment_reply_hook
        
        if self._ckeditor_config is None:
            self._ckeditor_config = CkeditorConfig()

    @property
    def snippet_image_file_path(self):
        filemanager_path = filemanager.get_root_path()
        return os.path.join(filemanager_path, self.snippet_image_subfolder)

    @property
    def front_end_urls_enabled(self):
        return self.view_post_url_function is not None

    @property
    def ckeditor_config(self):
        filemanager_url = None
        if self.init_filemanager:
            filemanager_url = url_for('flaskfilemanager.index')

        return self._ckeditor_config.clone(
            filemanager_url=filemanager_url,
            ckeditor_url=url_for('easycms_editor.static', filename='ckeditor/ckeditor.js')
        )


def init(easy_cms_settings, page_defs):
    """
    :param easy_cms_settings: EasyCmsSettings object
    :param page_defs: List of PageDef objects
    """
    global _settings, _page_defs

    if easy_cms_settings is None:
        _settings = EasyCmsSettings()
    else:
        _settings = easy_cms_settings

    _page_defs = page_defs


def get_settings():
    global _settings

    return _settings


def get_page_defs():
    global _page_defs

    return _page_defs

