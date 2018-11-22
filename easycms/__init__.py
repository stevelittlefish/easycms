"""
Flask / SQLAlchemy CMS library
"""

import datetime

import sqlalchemy.sql
from littlefish.pager import SimplePager
import flaskfilemanager
from littlefish import util

from . import models, accesscontrol
from .editor import editor as blueprint  # noqa
from .settings import init as init_settings
from . import datautil

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

bind = None
post_types = None


def init(app, engine_or_connection, metadata=None, all_post_types=['post'], table_prefix='cms',
         access_control_config=None, settings=None, page_defs=[]):

    global bind, session, post_types

    bind = engine_or_connection
    
    models.init(table_prefix, metadata, bind)

    post_types = all_post_types
    accesscontrol.init(access_control_config)

    init_settings(settings, page_defs)

    if settings.init_filemanager:
        ac = accesscontrol.get_access_control()

        def ffm_ac_fun():
            return ac.can_access_filemanager()

        flaskfilemanager.init(app, url_prefix=settings.filemanager_url_prefix,
                              access_control_function=ffm_ac_fun)

    if settings.snippets_enabled:
        # Make sure this directory exists
        snippet_path = settings.snippet_image_file_path
        util.ensure_dir(snippet_path)
    
    # Create al tables
    models.create_all()

    # Ensure all pages are up to date
    datautil.update_all_pages()


def get_all_posts_query(post_type=None, allow_unpublished=False, session=None):
    if session is None:
        session = models.session

    query = session.query(models.CmsPost)
    
    if post_type is not None:
        query = query.filter(models.CmsPost.post_type == post_type)
    
    if allow_unpublished:
        query = query.order_by(sqlalchemy.sql.func.coalesce(models.CmsPost.published, models.CmsPost.created).desc())
    else:
        query = query.filter(models.CmsPost.published != None)
        query = query.order_by(models.CmsPost.published.desc())

    return query


def get_all_posts_pager(page, num_per_page=10, post_type=None, allow_unpublished=False, session=None):
    query = get_all_posts_query(post_type=post_type, allow_unpublished=allow_unpublished, session=session)
    
    return SimplePager(num_per_page, page, query)


def get_posts_by_category_query(post_type, category_code, allow_unpublished=False, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsPost
    ).join(
        models.CmsCategory
    ).filter(
        models.CmsPost.post_type == post_type,
        models.CmsCategory.code == category_code
    )

    if allow_unpublished:
        query = query.order_by(
            sqlalchemy.sql.func.coalesce(models.CmsPost.published, models.CmsPost.created).desc()
        )
    else:
        query = query.filter(
            models.CmsPost.published != None
        ).order_by(
            models.CmsPost.published.desc()
        )

    return query


def get_posts_by_category_pager(post_type, category_code, page, num_per_page=10,
                                allow_unpublished=False, session=None):

    query = get_posts_by_category_query(post_type, category_code,
                                        allow_unpublished=allow_unpublished, session=session)

    return SimplePager(num_per_page, page, query)


def get_posts_by_tag_query(post_type, tag_name, allow_unpublished=False, session=None):
    query = get_all_posts_query(post_type=post_type, allow_unpublished=allow_unpublished,
                                session=session)
    
    # Join and filter by tag
    query = query.join(
        models.CmsPost.tags
    ).filter(
        models.CmsTag.name == tag_name
    )

    return query


def get_posts_by_tag_pager(post_type, tag, page, num_per_page=10,
                           allow_unpublished=False, session=None):
    query = get_posts_by_tag_query(post_type, tag, allow_unpublished=allow_unpublished,
                                   session=session)

    return SimplePager(num_per_page, page, query)


def get_post_by_code(post_type, code, allow_unpublished=False, session=None):
    if session is None:
        session = models.session
    
    query = session.query(
        models.CmsPost
    ).filter(
        models.CmsPost.post_type == post_type, models.CmsPost.code == code
    )

    if not allow_unpublished:
        query = query.filter(models.CmsPost.published < datetime.datetime.utcnow())

    return query.one_or_none()


def get_page_by_code(code, allow_disabled=True, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsPage
    ).filter(
        models.CmsPage.code == code
    )

    if not allow_disabled:
        query = query.filter(models.CmsPage.disabled == False)

    return query.one_or_none()


def get_category_by_code(post_type, code, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsCategory
    ).filter(
        models.CmsCategory.post_type == post_type,
        models.CmsCategory.code == code
    )

    return query.one_or_none()
