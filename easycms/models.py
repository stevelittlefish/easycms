"""
Contains SQLAlchemy models for the CMS
"""

import logging
import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Table, UniqueConstraint,\
    Boolean, Integer
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.sql import func
from titlecase import titlecase
from bs4 import BeautifulSoup
from unidecode import unidecode
from flask import url_for, request
from littlefish import timetool

from .settings import get_settings, get_page_defs
import easycms
from easycms import cmsutil
from easycms import constants

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


class Db(object):
    @property
    def session(self):
        global session
        return session


# Base class for database models
Model = None
# Sessionmaker
Session = None
# Session
session = None
# DB object (to make the code look like flask-sqlalchemy code!)
db = Db()


def init(table_prefix, metadata, bind):
    global Model, CmsUser, CmsCategory, CmsTag, CmsPost, CmsPostRevision, CmsComment,\
        CmsPage, CmsPageRevision, CmsVersionHistory, CmsAuthor, Session, session, db,\
        CmsPublishedPage, CmsPublishedPageRevision

    Model = declarative_base(bind=bind, metadata=metadata)
    Session = sessionmaker(bind=bind)
    session = Session()

    prefix = '{}_'.format(table_prefix)

    # Association table for tags
    cms_post_cms_tag = Table(prefix + 'post_' + prefix + 'tag',
                             Model.metadata,
                             Column('post_id', BigInteger, ForeignKey(prefix + 'post.id')),
                             Column('tag_id', BigInteger, ForeignKey(prefix + 'tag.id')))

    class CmsAuthor(Model):
        __tablename__ = prefix + 'author'
        id = Column(BigInteger, primary_key=True, nullable=False)
        name = Column(String, unique=True, nullable=False)
        code = Column(String, unique=True, nullable=False)

        def __init__(self, name, code=None):
            self.name = name
            if code:
                self.code = code
            else:
                self.code = cmsutil.make_code(name)
    
        @property
        def select_name(self):
            return self.name

        @property
        def select_value(self):
            return self.id
    
    class CmsUser(Model):
        __tablename__ = prefix + 'user'
        
        id = Column(BigInteger, primary_key=True, nullable=False)
        name = Column(String, unique=True, nullable=False)
        author_id = Column(BigInteger, ForeignKey(prefix + 'author.id'), unique=True, nullable=True)

        author = relationship('CmsAuthor', uselist=False, backref=backref('user', uselist=False))

        def __init__(self, name, author):
            self.name = name
            self.author = author

    class CmsCategory(Model):
        __tablename__ = prefix + 'category'

        id = Column(BigInteger, primary_key=True, nullable=False)
        post_type = Column(String, nullable=False)
        name = Column(String, nullable=False)
        code = Column(String, nullable=False)
        
        __table_args__ = (
            UniqueConstraint(post_type, name),
            UniqueConstraint(post_type, code)
        )
        
        def __init__(self, post_type, name, code=None):
            self.post_type = post_type
            self.update_name(name, code)

        def update_name(self, name, code=None):
            self.name = name
            if code:
                self.code = code
            else:
                code = cmsutil.make_code(name)

        @property
        def select_name(self):
            return self.name

        @property
        def select_value(self):
            return self.id
    
    class CmsTag(Model):
        __tablename__ = prefix + 'tag'

        id = Column(BigInteger, primary_key=True, nullable=False)
        post_type = Column(String, nullable=False)
        name = Column(String, nullable=False)
        code = Column(String, nullable=False)
        # Tag type for "special" tags.  Not assignable in normal tag editor but can be assigned programatically.
        # Allows tags to be handled differently, i.e. a tag with tag_type = "Product" may be used to link to
        # a product in an e-commerce site.  It's up to the application to manage these.
        tag_type = Column(String, nullable=True)
        # This is a more or less un-used field - you can put whatever you want in here.  The intention of this
        # field is that you can put something here which will link this tag to an external resource, for example
        # you could put the code of a product here to link this tag to that product.
        external_code = Column(String, nullable=True)
        
        __table_args__ = (
            UniqueConstraint(post_type, name),
            UniqueConstraint(post_type, code)
        )

        def __init__(self, post_type, name, tag_type=None, external_code=None):
            self.post_type = post_type
            self.name = name
            self.code = self.name_to_code(name)
            self.tag_type = tag_type
            self.external_code = external_code

        @staticmethod
        def name_to_code(name):
            return cmsutil.make_code(name, strip_hyphens=False)

        @property
        def title_name(self):
            return titlecase(self.name)
    
    class CmsPage(Model):
        __tablename__ = prefix + 'page'

        id = Column(BigInteger, primary_key=True, nullable=False)
        created = Column(DateTime, nullable=False, unique=True)
        title = Column(String, nullable=False, unique=True)
        code = Column(String, nullable=False, unique=True)
        content = Column(String, nullable=False)
        disabled = Column(Boolean, nullable=False)
        author_id = Column(BigInteger, ForeignKey(prefix + 'author.id'), nullable=True)
        # This is updated to True when we publish the page, and back to False when the page is editted
        published = Column(Boolean, nullable=False)

        author = relationship('CmsAuthor', uselist=False, backref=backref('pages'))

        def __init__(self, code, title, content):
            self.created = datetime.datetime.utcnow()
            self.code = code
            self.title = title
            self.content = content
            self.disabled = False
            self.author = None
            self.published = False

        @property
        def published_by(self):
            if self.published and self.published_page:
                return self.published_page.published_by
            
            return None

        @property
        def page_def(self):
            for page_def in get_page_defs():
                if page_def.code == self.code:
                    return page_def

            raise Exception('Could not find page def for page with code "{}"'.format(self.code))
    
        @property
        def front_end_url(self):
            return self.page_def.url
        
    class CmsPageRevision(Model):
        __tablename__ = prefix + 'page_revision'

        id = Column(BigInteger, primary_key=True, nullable=False)
        page_id = Column(BigInteger, ForeignKey(prefix + 'page.id'), nullable=False)
        timestamp = Column(DateTime, nullable=False)
        user_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=False)
        revision_notes = Column(String, nullable=True)
        content = Column(String, nullable=False)

        page = relationship('CmsPage', uselist=False, backref=backref('revisions', order_by=timestamp.desc()))
        user = relationship('CmsUser', uselist=False)

        def __init__(self, page, user, revision_notes=None):
            self.timestamp = datetime.datetime.utcnow()
            self.page = page
            self.content = page.content
            self.user = user
            self.revision_notes = revision_notes

    class CmsPublishedPage(Model):
        """
        If page publishing is enabled, this model is used to store the latest published version of a page.
        This allows a content editor to make any number of changes to the unpublished page without affecting
        the live site.  Another user can then publish the page and make it live.

        The same process can still be used after publishing and any number of changes can be made before
        re-publishing.  Previously published versions can also be restored from the revision history.
        """
        __tablename__ = prefix + 'published_page'

        id = Column(BigInteger, primary_key=True, nullable=False)
        page_id = Column(BigInteger, ForeignKey(prefix + 'page.id'), nullable=False, unique=True)
        published = Column(DateTime, nullable=False, unique=True)
        published_by_id = Column(BigInteger, ForeignKey(prefix + 'author.id'), nullable=False)
        title = Column(String, nullable=False, unique=True)
        content = Column(String, nullable=False)

        page = relationship('CmsPage', uselist=False, backref=backref('published_page', uselist=False))
        published_by = relationship('CmsAuthor', uselist=False)

        def __init__(self, page):
            self.page = page

        def apply_page_content(self, published_by):
            self.published = datetime.datetime.utcnow()
            self.published_by = published_by
            self.title = self.page.title
            self.content = self.page.content

        @property
        def disabled(self):
            return self.page.disabled
        
        @property
        def code(self):
            return self.page.code

        @property
        def created(self):
            return self.page.created

        @property
        def author(self):
            return self.page.author
        
        @property
        def page_def(self):
            return self.page.page_def

        @property
        def front_end_url(self):
            return self.page.front_end_url
    
    class CmsPublishedPageRevision(Model):
        __tablename__ = prefix + 'published_page_revision'

        id = Column(BigInteger, primary_key=True, nullable=False)
        published_page_id = Column(BigInteger, ForeignKey(prefix + 'published_page.id'), nullable=False)
        timestamp = Column(DateTime, nullable=False)
        user_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=False)
        revision_notes = Column(String, nullable=True)
        content = Column(String, nullable=False)

        published_page = relationship('CmsPublishedPage', uselist=False, backref=backref('revisions', order_by=timestamp.desc()))
        user = relationship('CmsUser', uselist=False)

        def __init__(self, published_page, user, revision_notes=None):
            self.timestamp = datetime.datetime.utcnow()
            self.published_page = published_page
            self.content = published_page.content
            self.user = user
            self.revision_notes = revision_notes

    class CmsPost(Model):
        __tablename__ = prefix + 'post'

        id = Column(BigInteger, primary_key=True, nullable=False)
        post_type = Column(String, nullable=False)
        created = Column(DateTime, nullable=False, unique=True)
        published = Column(DateTime, nullable=True, unique=True)
        category_id = Column(BigInteger, ForeignKey(prefix + 'category.id'), nullable=False)
        title = Column(String, nullable=False)
        code = Column(String, nullable=False)
        tagline = Column(String, nullable=False)
        content = Column(String, nullable=False)
        author_id = Column(BigInteger, ForeignKey(prefix + 'author.id'), nullable=False)
        # Title tag
        html_title = Column(String, nullable=True)
        # Meta (description) tag
        html_description = Column(String, nullable=True)
        # Fields for snippet
        snippet_title = Column(String, nullable=True)
        snippet_description = Column(String, nullable=True)
        snippet_image = Column(String, nullable=True)
        main_image_url = Column(String, nullable=True)

        category = relationship('CmsCategory', uselist=False, backref=backref('posts'))
        tags = relationship('CmsTag', secondary=cms_post_cms_tag, backref=backref('posts'))
        author = relationship('CmsAuthor', uselist=False, backref=backref('posts'))

        __table_args__ = (
            UniqueConstraint(post_type, title),
            UniqueConstraint(post_type, code)
        )
        
        def __init__(self, post_type, category, title, content, author, tagline,
                     publish_now=False, code=None, main_image_url=None):
            
            self.post_type = post_type
            self.created = datetime.datetime.utcnow()
            self.published = self.created if publish_now else None
            self.category = category
            self.title = title
            self.tagline = tagline
            self.content = content
            self.author = author
            self.main_image_url = main_image_url
            if code:
                self.code = code
            else:
                self.code = cmsutil.make_code(title)

        @property
        def description(self):
            soup = BeautifulSoup(unidecode(self.content), 'html.parser')
            ps = soup.find_all('p')
            for p in ps:
                desc = ''
                found = False
                for c in p.contents:
                    # c.name is the tag name.  We are looking for text which has no tag name
                    if not c.name:
                        found = True
                        desc += c + ' '
                    else:
                        # it was a tag - look one level deep for more text
                        for c2 in c.contents:
                            if not c2.name:
                                desc += c2 + ' '

                if found:
                    # There was a paragraph!
                    return desc.strip()

            return ''
        
        def get_next_post(self, include_non_published=False):
            if include_non_published:
                if self.published:
                    date = self.published
                else:
                    date = self.created

                return session.query(
                    CmsPost
                ).filter(
                    CmsPost.post_type == self.post_type,
                    func.coalesce(CmsPost.published, CmsPost.created) > date
                ).order_by(
                    func.coalesce(CmsPost.published, CmsPost.created)
                ).first()
            else:
                return session.query(
                    CmsPost
                ).filter(
                    CmsPost.post_type == self.post_type,
                    CmsPost.published > self.published
                ).order_by(
                    CmsPost.published
                ).first()

        def get_prev_post(self, include_non_published=False):
            if include_non_published:
                if self.published:
                    date = self.published
                else:
                    date = self.created

                return session.query(
                    CmsPost
                ).filter(
                    CmsPost.post_type == self.post_type,
                    func.coalesce(CmsPost.published, CmsPost.created) < date
                ).order_by(
                    func.coalesce(CmsPost.published, CmsPost.created).desc()
                ).first()
            else:
                return session.query(
                    CmsPost
                ).filter(
                    CmsPost.post_type == self.post_type,
                    CmsPost.published < self.published
                ).order_by(
                    CmsPost.published.desc()
                ).first()
        
        def get_html_title(self):
            if self.html_title:
                return self.html_title
            return self.title

        def get_html_description(self):
            if self.html_description:
                return self.html_description
            return self.description

        def get_snippet_title(self):
            if self.snippet_title:
                return self.snippet_title
            return self.title

        def get_snippet_description(self):
            if self.snippet_description:
                return self.snippet_description
            return self.tagline
        
        def get_snippet_image(self):
            if self.snippet_image:
                return self.snippet_image
            elif get_settings().snippet_missing_image_url:
                return get_settings().snippet_missing_image_url

            try:
                return url_for('easycms_editor.static', filename='img/no-image.png')
            except Exception as e:
                error = str(e)
                raise Exception('Could not display snippet image. Make sure you set '
                                'snippet_missing_image_url in your EasyCmsSettings. {}'.format(error))
        
        def get_images(self):
            soup = BeautifulSoup(unidecode(self.content), 'html.parser')
            imgs = soup.find_all('img')
            out = []
            if self.main_image_url:
                out.append(self.main_image_url)
            for img in imgs:
                out.append(img['src'])
            return out
        
        def has_visible_comments(self):
            """
            :return: True if the current logged in user can see any of the comments on this post
            """
            for comment in self.comments:
                if comment.visible():
                    return True
            return False
        
        def num_visible_comments(self):
            num_comments = 0
            for comment in self.comments:
                if comment.visible():
                    num_comments += 1

            return num_comments
        
        @property
        def editor_url(self):
            return url_for('easycms_editor.edit_post', post_id=self.id)

        @property
        def seo_editor_url(self):
            return url_for('easycms_editor.edit_post_seo', post_id=self.id)

        @property
        def front_end_url(self):
            settings = get_settings()
            
            if settings.view_post_url_function is None:
                raise Exception('To generate front-end URLS you need to set the view_post_url_function variable '
                                'in your EasyCmsSettings object')

            return settings.view_post_url_function(self)

        @property
        def is_published(self):
            return self.published and self.published <= datetime.datetime.utcnow()

        @property
        def is_scheduled(self):
            return self.published and self.published > datetime.datetime.utcnow()

        @property
        def published_string(self):
            if self.is_scheduled:
                return 'Scheduled to be published on {}'.format(timetool.format_datetime(self.published))
            elif self.is_published:
                return timetool.format_datetime(self.published)
            else:
                return 'Not published'

    class CmsPostRevision(Model):
        __tablename__ = prefix + 'post_revision'

        id = Column(BigInteger, primary_key=True, nullable=False)
        post_id = Column(BigInteger, ForeignKey(prefix + 'post.id'), nullable=False)
        timestamp = Column(DateTime, nullable=False)
        user_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=False)
        revision_notes = Column(String, nullable=True)
        title = Column(String, nullable=False)
        content = Column(String, nullable=False)

        post = relationship('CmsPost', uselist=False, backref=backref('revisions', order_by=timestamp.desc()))
        user = relationship('CmsUser', uselist=False)

        def __init__(self, post, user, revision_notes=None):
            self.timestamp = datetime.datetime.utcnow()
            self.post = post
            self.title = post.title
            self.content = post.content
            self.user = user
            self.revision_notes = revision_notes

    class CmsComment(Model):
        __tablename__ = prefix + 'comment'

        id = Column(BigInteger, primary_key=True, nullable=False)
        post_id = Column(BigInteger, ForeignKey(prefix + 'post.id'), nullable=False)
        author_name = Column(String, nullable=True)
        author_email = Column(String, nullable=True)
        author_ip = Column(String, nullable=True)
        author_user_agent = Column(String)
        author_id = Column(BigInteger, ForeignKey(prefix + 'author.id'), nullable=True)
        author_user_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=True)
        edited_by_id = Column(BigInteger, ForeignKey(prefix + 'author.id'), nullable=True)
        edited_by_user_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=True)
        timestamp = Column(DateTime, nullable=False)
        approved = Column(Boolean, nullable=False)
        content = Column(String, nullable=False)
        original_content = Column(String, nullable=True)
        edit_timestamp = Column(DateTime, nullable=True)
        deleted = Column(Boolean, nullable=False)
        reply_to_id = Column(BigInteger, ForeignKey(prefix + 'comment.id'), nullable=True)

        post = relationship('CmsPost', uselist=False, backref=backref('comments', order_by=timestamp))
        author = relationship('CmsAuthor', foreign_keys=[author_id], uselist=False)
        author_user = relationship('CmsUser', foreign_keys=[author_user_id], uselist=False)
        editor = relationship('CmsAuthor', foreign_keys=[edited_by_id], uselist=False)
        editor_user = relationship('CmsUser', foreign_keys=[edited_by_user_id], uselist=False)
        reply_to = relationship('CmsComment', uselist=False, remote_side=[id], backref=backref('replies', order_by=timestamp))

        def __init__(self, post, content, user=None, author=None, author_name=None, author_email=None,
                     author_ip=None, user_agent=None, reply_to=None):
            self.post = post
            self.content = content
            self.author_user = user
            self.author = author
            self.author_name = author_name
            self.author_email = author_email
            self.author_ip = author_ip
            self.author_user_agent = user_agent
            self.reply_to = reply_to

            self.timestamp = datetime.datetime.utcnow()
            self.approved = False
            self.deleted = False
            self.original_content = None
            self.edit_timestamp = None
            self.editor = None
            self.editor_user = None

        def visible(self):
            """
            :return: True if the current logged in user can see this comment
            """
            from . import accesscontrol
            ac = accesscontrol.get_access_control()
            
            if ac.can_moderate_comments():
                return True

            if self.deleted:
                return False

            if self.approved:
                return True
            
            if request and request.cookies and \
                    request.cookies.get(constants.COMMENT_EMAIL_COOKIE_NAME) == self.author_email:
                return True

            return False
        
        def get_author_name(self):
            return self.author.name if self.author else self.author_name
        
        @property
        def edit_url(self):
            return url_for('easycms_editor.edit_comment', comment_id=self.id)
        
    class CmsVersionHistory(Model):
        """
        Used to store the version in the database so that we can automatically update the tables
        """
        __tablename__ = prefix + 'version_history'

        id = Column(BigInteger, primary_key=True, nullable=False)
        timestamp = Column(DateTime, nullable=False)
        major_version = Column(Integer, nullable=False)
        minor_version = Column(Integer, nullable=False)

        def __init__(self, major_version, minor_version):
            self.timestamp = datetime.datetime.utcnow()
            self.major_version = major_version
            self.minor_version = minor_version
        
        @property
        def version_string(self):
            return '{}.{}.X'.format(self.major_version, self.minor_version)

        @property
        def is_current_version(self):
            return self.major_version == easycms.MAJOR_VERSION and self.minor_version == easycms.MINOR_VERSION


def create_all():
    from . import bind
    log.info('Creating all missing EasyCMS tables')
    Model.metadata.create_all(bind=bind)


def drop_all():
    from . import bind
    log.info('Dropping all EasyCMS tables')
    Model.metadata.drop_all(bind=bind)

