"""
Flask / SQLAlchemy CMS library
"""

import datetime
import logging
import re

import sqlalchemy.sql
from littlefish.pager import SimplePager
import flaskfilemanager
from littlefish import util
import sqlalchemy.exc

from . import models, accesscontrol
from .editor import editor as blueprint  # noqa
from .settings import init as init_settings
from . import datautil
from . import migration
from .datautil import create_user  # noqa

log = logging.getLogger(__name__)

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

bind = None
post_types = None

# The package will have a version number (in pypi) like 1.2.3 where 1 is the major
# version and 2 is the minor version.  In the code, we don't care about the 3rd
# level of version number.  If we make any database changes we must update the
# minor version, and if they are major changes we will update the major version
# too

MAJOR_VERSION = 0
MINOR_VERSION = 3
VERSION = '{}.{}.X'.format(MAJOR_VERSION, MINOR_VERSION)


def init(app, engine_or_connection, metadata=None, all_post_types=['post'], table_prefix='cms',
         access_control_config=None, settings=None, page_defs=[], update_db=False):

    global bind, session, post_types

    log.info('Initialising EasyCMS v{}'.format(VERSION))
    
    if update_db:
        log.info('Update DB mode enabled')

    bind = engine_or_connection
    
    if bind.dialect.name != 'postgresql':
        raise Exception('Only postgresql is supported by EasyCMS')
    
    models.init(table_prefix, metadata, bind)

    try:
        current_version = migration.check_current_version(update_db=update_db)
    except sqlalchemy.exc.ProgrammingError as e:
        if re.search('relation.*does not exist', str(e)):
            raise Exception('An important table is missing from the database. To '
                            'update the database you need to pass update_db=True '
                            'into easycms.init(...)')
        else:
            raise e

    if current_version.is_current_version:
        log.info('Database version matches software version')
    elif not update_db:
        raise Exception('EasyCMS version is {} but your database is currently '
                        'on version {}. To update the database you need to '
                        'pass update_db=True into easycms.init(...). '
                        .format(VERSION, current_version.version_string))
    else:
        migration.update_database(current_version)

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

    log.info('EasyCMS v{} Initialisation Complete'.format(VERSION))


def get_all_users_query(session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsUser
    ).order_by(
        models.CmsUser.id
    )

    return query


def get_all_posts_query(post_type=None, allow_unpublished=False, session=None):
    if session is None:
        session = models.session

    query = session.query(models.CmsPost)
    
    if post_type is not None:
        query = query.filter(models.CmsPost.post_type == post_type)
    
    if allow_unpublished:
        query = query.order_by(sqlalchemy.sql.func.coalesce(models.CmsPost.published, models.CmsPost.created).desc())
    else:
        now = datetime.datetime.utcnow()
        query = query.filter(models.CmsPost.published < now)
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
        now = datetime.datetime.utcnow()
        query = query.filter(
            models.CmsPost.published < now
        ).order_by(
            models.CmsPost.published.desc()
        )

    return query


def get_recent_posts(post_type, num_posts, allow_unpublished=False, session=None):
    query = get_all_posts_query(post_type=post_type, allow_unpublished=allow_unpublished,
                                session=session)

    return query[:num_posts]


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


def get_all_pages_query(allow_disabled=False, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsPage
    ).order_by(
        models.CmsPage.id
    )

    if not allow_disabled:
        query = query.filter(
            models.CmsPage.disabled == False
        )

    return query


def get_page_by_code(code, allow_disabled=True, session=None):
    query = get_all_pages_query(
        allow_disabled=allow_disabled, session=session
    ).filter(
        models.CmsPage.code == code
    )

    return query.one_or_none()


def get_all_published_pages_query(allow_disabled=False, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsPublishedPage
    ).join(
        models.CmsPage
    ).order_by(
        models.CmsPublishedPage.id
    )

    if not allow_disabled:
        query = query.filter(
            models.CmsPage.disabled == False
        )

    return query


def get_published_page_by_code(code, allow_disabled=True, session=None):
    query = get_all_published_pages_query(
        allow_disabled=allow_disabled, session=session
    ).filter(
        models.CmsPage.code == code
    )

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


def get_all_categories(post_type, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsCategory
    ).filter(
        models.CmsCategory.post_type == post_type
    ).order_by(
        models.CmsCategory.name
    )

    return query.all()


def get_all_tags(post_type, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsTag
    ).filter(
        models.CmsTag.post_type == post_type
    ).order_by(
        models.CmsTag.name
    )

    return query.all()


def get_special_tags(post_type=None, tag_type=None, external_code=None, session=None):
    if session is None:
        session = models.session

    query = session.query(
        models.CmsTag
    )
    
    if post_type:
        query = query.filter(models.CmsTag.post_type == post_type)

    if tag_type:
        query = query.filter(models.CmsTag.tag_type == tag_type)

    if external_code:
        query = query.filter(models.CmsTag.external_code == external_code)

    return query.all()


def get_comment_query(approved_only=True, show_deleted=False, session=None):
    if session is None:
        session = models.session
    
    query = session.query(
        models.CmsComment
    ).order_by(
        models.CmsComment.timestamp
    )

    if approved_only:
        query = query.filter(models.CmsComment.approved == True)

    if not show_deleted:
        query = query.filter(models.CmsComment.deleted == False)

    return query


def get_comment_by_id(comment_id, session=None):
    if session is None:
        session = models.session
    
    return session.query(
        models.CmsComment
    ).filter(
        models.CmsComment.id == comment_id
    ).one_or_none()


def get_all_authors_query(session=None):
    if session is None:
        session = models.session

    return session.query(
        models.CmsAuthor
    ).order_by(
        models.CmsAuthor.id
    )


def get_all_authors(session=None):
    return get_all_authors_query(session).all()


def get_author_by_code(author_code, session=None):
    query = get_all_authors_query(session)

    return query.filter(
        models.CmsAuthor.code == author_code
    ).one_or_none()

