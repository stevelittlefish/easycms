"""
Tools for migrating between database versions
"""

import logging

import sqlalchemy.exc

import easycms
from .models import db
from . import models

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


class ColumnAlreadyExists(Exception):
    pass


def check_current_version(fix_missing=True, update_db=False):
    """
    Check the current version in the database.  If fix_missing is True, then 0.0 will be added if there
    is no version in the database.

    If the version in the database is higher than the software version an exception will be thrown as the
    library needs to be updated

    :return: CmsVersionHistory with current database version
    """
    try:
        current_db_version = db.session.query(models.CmsVersionHistory).order_by(
            models.CmsVersionHistory.timestamp.desc()
        ).first()
    except sqlalchemy.exc.ProgrammingError as e:
        db.session.rollback()

        if update_db and 'does not exist' in str(e):
            # Create the table
            log.info('Attempting to create missing version table')
            models.CmsVersionHistory.__table__.create(db.session.connection())
            current_db_version = None
        else:
            raise e
    
    if not current_db_version:
        if not fix_missing:
            raise Exception('No version history in database!')

        # Insert the default version
        log.info('No version in database: adding v0.0.X')
        current_db_version = models.CmsVersionHistory(0, 0)
        db.session.add(current_db_version)
        db.session.commit()
    
    if current_db_version.major_version > easycms.MAJOR_VERSION \
            or current_db_version.minor_version > easycms.MINOR_VERSION:
        raise Exception('Database version is {} but software version is {} - cms library must be updated to '
                        'match the version in the database'.format(
                            easycms.VERSION, current_db_version.version_string
                        ))
    
    return current_db_version


def add_column(sql):
    try:
        # Add main_image_url column
        return db.session.execute(sql)

    except sqlalchemy.exc.ProgrammingError as e:
        db.session.rollback()

        if 'already exists' in str(e):
            raise ColumnAlreadyExists(e)
        else:
            raise e


def update_database(current_db_version):
    """
    Update the schema and add any missing data
    """
    if current_db_version.major_version != 0:
        raise Exception('Major version > 0 not implemented!')

    if current_db_version.minor_version == 0:
        log.info('Updating from v0.0.X to v0.1.X')

        # Add main_image_url column
        log.info('Adding main_image_url to post table')
        try:
            add_column('ALTER TABLE {} ADD COLUMN main_image_url CHARACTER VARYING'.format(
                models.CmsPost.__tablename__
            ))
        except ColumnAlreadyExists:
            log.info('Column already exists: skipping')

        # Update the version
        log.info('Updating DB Version to 0.1.X')
        current_db_version = models.CmsVersionHistory(0, 1)
        db.session.add(current_db_version)
        db.session.commit()

    log.info('Update Complete!')



