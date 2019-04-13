"""
Configuration for EasyCMS
"""

import logging

from flask import url_for
import easyforms

import easycms
import easycms.models
import easycms.accesscontrol
from easycms.settings import PageDef
import auth
import permissions
from permissions import Permissions
from constants import pagecodes
import sendemail
import models


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

    def can_edit_post_seo(self):
        return permissions.has_permission(Permissions.admin)

    def can_tag_post(self):
        """Can the user add (already existing tags) to a post?"""
        return permissions.has_permission(Permissions.admin)

    def can_manage_tags(self):
        """Can the user create new tags?"""
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


def comment_added_hook(comment):
    if not comment.approved:
        # Send the notification emails
        sendemail.send_blog_comment_notification_email('admin@blog.com', comment)


def comment_reply_hook(comment):
    if comment.reply_to.author_email:
        email = comment.reply_to.author_email
    else:
        cms_user = comment.reply_to.author_user
        user = models.User.query.filter(
            models.User.cms_user_id == cms_user.id
        ).one_or_none()

        if not user:
            log.error('No user for author to comment: {}'.format(cms_user.name))
            return
        
        email = user.email_address

    name = comment.reply_to.get_author_name()
    sendemail.send_blog_comment_reply_notification_email(email, name, comment)


ckeditor_config = easyforms.CkeditorConfig(
    allow_all_extra_content=False,
    strikethrough_enabled=True,
    disallowed_content='img[height]',
    # custom_styles_js_url='/static/js/ckeditor_styles.js',
    # custom_contents_css_url='/static/css/ckeditor_contents.css',
    force_paste_as_plain_text=True
)

settings = easycms.settings.EasyCmsSettings(
    home_link_text='Test Site Homepage',
    home_link_endpoint='main.index',
    website_name='Test Site',
    logout_endpoint='main.logout',
    ckeditor_config=ckeditor_config,
    # custom_stylesheet_url='/static/css/editor.css',
    # editor_base_template='admin/cmsbase.html',
    snippets_enabled=True,
    snippet_image_width=300,
    snippet_image_height=200,
    snippet_image_subfolder='cms-snippet-images',
    snippet_description_max_length=170,
    # snippet_missing_image_url='/static/img/no-image.png',
    post_main_image_enabled=True,
    post_main_image_width=800,
    post_main_image_height=600,
    post_main_image_required=True,
    view_post_url_function=lambda post: url_for('main.view_blog_post', post_code=post.code, _external=True),
    comments_enabled=True,
    comment_added_hook=comment_added_hook,
    comment_reply_hook=comment_reply_hook,
    page_publishing_enabled=True
)

page_defs = [
    PageDef(pagecodes.HOMEPAGE, 'Homepage'),
]

