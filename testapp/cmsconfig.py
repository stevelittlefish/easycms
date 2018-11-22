"""
Configuration for EasyCMS
"""

import logging

import easycms
import easycms.models
import easycms.accesscontrol
from easycms.settings import PageDef
import easyforms
import auth
import permissions
from permissions import Permissions
from constants import pagecodes


__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


class CmsAccessControl(easycms.accesscontrol.AccessControlConfig):
    def get_logged_in_cms_user(self):
        user = auth.get_user()

        if user:
            return easycms.models.db.session.query(
                easycms.models.CmsUser
            ).filter(
                easycms.models.CmsUser.id == user.cms_user_id
            ).one()

        return None

    def can_view_editor(self):
        return permissions.has_permission(Permissions.admin)

    def can_edit_page(self):
        return permissions.has_permission(Permissions.admin)

    def can_edit_post(self):
        return permissions.has_permission(Permissions.admin)

    def can_delete_post(self):
        return permissions.has_permission(Permissions.admin)

    def can_publish_post(self):
        return permissions.has_permission(Permissions.admin)

    def can_edit_category(self):
        return permissions.has_permission(Permissions.admin)

    def can_moderate_comments(self):
        return permissions.has_permission(Permissions.admin)

    def can_access_filemanager(self):
        return permissions.has_permission(Permissions.admin)


ckeditor_config = easyforms.CkeditorConfig(
    allow_all_extra_content=False,
    disallowed_content='img[height]',
    custom_styles_js_url='/static/js/ckeditor_styles.js',
    custom_contents_css_url='/static/css/ckeditor_contents.css',
    force_paste_as_plain_text=True
)

settings = easycms.settings.EasyCmsSettings(
    home_link_text='Test Site Homepage',
    home_link_endpoint='main.index',
    website_name='Test Site',
    logout_endpoint='main.logout',
    ckeditor_config=ckeditor_config,
    custom_stylesheet_url='/static/css/editor.css',
    # editor_base_template='admin/cmsbase.html',
    snippets_enabled=True,
    snippet_image_width=300,
    snippet_image_height=200,
    snippet_image_subfolder='cms-snippet-images',
    snippet_description_max_length=170,
    snippet_missing_image_url='/static/img/no-image.png',
)

page_defs = [
    PageDef(pagecodes.HOMEPAGE, 'Homepage'),
]

