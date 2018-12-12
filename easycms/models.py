"""
Contains SQLAlchemy models for the CMS
"""

import logging
import datetime
import re

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Table, UniqueConstraint,\
    Boolean, Integer
from sqlalchemy.orm import relationship, backref, sessionmaker
from sqlalchemy.sql import func
from titlecase import titlecase
from bs4 import BeautifulSoup
from unidecode import unidecode
from flask import url_for

from .settings import get_settings
import easycms

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
        CmsPage, CmsPageRevision, CmsVersionHistory, Session, session, db

    Model = declarative_base(bind=bind, metadata=metadata)
    Session = sessionmaker(bind=bind)
    session = Session()

    prefix = '{}_'.format(table_prefix)

    # Association table for tags
    cms_post_cms_tag = Table(prefix + 'post_' + prefix + 'tag',
                             Model.metadata,
                             Column('post_id', BigInteger, ForeignKey(prefix + 'post.id')),
                             Column('tag_id', BigInteger, ForeignKey(prefix + 'tag.id')))
    
    class CmsUser(Model):
        __tablename__ = prefix + 'user'
        
        id = Column(BigInteger, primary_key=True, nullable=False)
        name = Column(String, unique=True, nullable=False)

        def __init__(self, name):
            self.name = name

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
                code = re.sub(r'[^a-z0-9]+', '-', name.lower())
                self.code = re.sub(r'[^a-z0-9]*$', '', code)

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
        
        __table_args__ = (
            UniqueConstraint(post_type, name),
            UniqueConstraint(post_type, code)
        )

        def __init__(self, post_type, name):
            self.post_type = post_type
            self.name = name
            self.code = self.name_to_code(name)

        @staticmethod
        def name_to_code(name):
            return re.sub(r'[^a-z0-9]+', '-', name.lower())

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

        def __init__(self, code, title, content):
            self.created = datetime.datetime.utcnow()
            self.code = code
            self.title = title
            self.content = content
            self.disabled = False
    
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
        author_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=False)
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
        author = relationship('CmsUser', uselist=False, backref=backref('posts'))

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
                code = re.sub(r'[^a-z0-9]+', '-', title.lower())
                self.code = re.sub(r'[^a-z0-9]*$', '', code)

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
        author_url = Column(String, nullable=True)
        author_ip = Column(String, nullable=True)
        author_user_agent = Column(String)
        author_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=True)
        edited_by_id = Column(BigInteger, ForeignKey(prefix + 'user.id'), nullable=True)
        timestamp = Column(DateTime, nullable=False)
        approved = Column(Boolean, nullable=False)
        content = Column(String, nullable=False)
        original_content = Column(String, nullable=True)
        edit_timestamp = Column(DateTime, nullable=True)
        deleted = Column(Boolean, nullable=False)
        reply_to_id = Column(BigInteger, ForeignKey(prefix + 'comment.id'), nullable=True)

        post = relationship('CmsPost', uselist=False, backref=backref('comments'))
        author = relationship('CmsUser', foreign_keys=[author_id], uselist=False)
        editor = relationship('CmsUser', foreign_keys=[edited_by_id], uselist=False)
        reply_to = relationship('CmsComment', uselist=False, remote_side=[id], backref=backref('replies', order_by=timestamp))
    
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

