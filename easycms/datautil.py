"""
Contains functions for interacting with the database, mainly for loading and saving models
"""

import logging

from .settings import get_page_defs
from . import models
from .models import db

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def create_user(name, session=None, commit=False):
    author = models.CmsAuthor(name)
    user = models.CmsUser(name, author)

    if session is None:
        session = db.session

    session.add(user)
    
    if commit:
        session.commit()

    return user


def update_all_pages():
    log.info('Ensuring all pages are up-to-date')
    
    page_defs = get_page_defs()
    CmsPage = models.CmsPage

    if not page_defs:
        log.info('No page defs - marking all pages as disabled')
        
    else:
        # There are some page defs. Make sure they all have the correct title and are present in
        # the database

        for page_def in page_defs:
            page = db.session.query(CmsPage).filter(CmsPage.code == page_def.code).one_or_none()
            
            if page:
                page.disabled = False
                if page.title != page_def.title:
                    log.info('Changing title of {} from {} to {}'.format(
                        page.code, page.title, page_def.title
                    ))
                    page.title = page_def.title

            else:
                log.info('Adding missing page {}: {}'.format(page_def.code, page_def.title))
                page = CmsPage(page_def.code, page_def.title, '')
                db.session.add(page)
        
    # Finally mark pages that have no page_defs as disabled
    query = db.session.query(CmsPage)
    if page_defs:
        all_codes = [pd.code for pd in page_defs]
        query = query.filter(CmsPage.code.notin_(all_codes))
    query.update({'disabled': True}, synchronize_session=False)

    db.session.commit()
