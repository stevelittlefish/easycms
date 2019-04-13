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


class ColumnDoesNotExist(Exception):
    pass


class Constraint(object):
    def __init__(self, table_name, constraint_name, definition):
        self.table_name = table_name
        self.constraint_name = constraint_name
        self.definition = definition


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
        log.info('No version in database: adding {}'.format(easycms.VERSION))
        current_db_version = models.CmsVersionHistory(easycms.MAJOR_VERSION, easycms.MINOR_VERSION)
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
        return db.session.execute(sql)

    except sqlalchemy.exc.ProgrammingError as e:
        db.session.rollback()

        if 'already exists' in str(e):
            raise ColumnAlreadyExists(e)
        else:
            raise e


def alter_column(sql):
    try:
        return db.session.execute(sql)

    except sqlalchemy.exc.ProgrammingError as e:
        db.session.rollback()
        
        # TODO: error handling
        raise e


def rename_column(sql):
    try:
        return db.session.execute(sql)

    except sqlalchemy.exc.ProgrammingError as e:
        db.session.rollback()
        
        # TODO: error handling
        raise e


def drop_column(sql):
    try:
        return db.session.execute(sql)

    except sqlalchemy.exc.ProgrammingError as e:
        db.session.rollback()
        
        if 'does not exist' in str(e):
            raise ColumnDoesNotExist(e)
        else:
            raise e


def get_foreign_key_constraints(table_name):
    sql = '''
SELECT conrelid::regclass AS table_name,
       conname AS constraint_name,
       pg_get_constraintdef(c.oid) AS constraint_def
FROM   pg_constraint c
       JOIN pg_namespace n ON n.oid = c.connamespace
WHERE  contype = 'f'
       AND n.nspname = 'public'
       AND conrelid::regclass::text = '{table_name}'
ORDER  BY conrelid::regclass::text;
'''
    
    rows = db.session.execute(sql.format(table_name=table_name)).fetchall()

    out = []
    for row in rows:
        out.append(Constraint(row['table_name'], row['constraint_name'], row['constraint_def']))

    return out


def does_column_exist(table_name, column_name):
    sql = '''
SELECT column_name
FROM information_schema.columns
WHERE table_name='{table_name}'
      AND column_name='{column_name}';
'''
    
    rows = db.session.execute(sql.format(table_name=table_name, column_name=column_name)).fetchall()

    return bool(rows)


def update_database(current_db_version):
    """
    Update the schema and add any missing data
    """
    if current_db_version.major_version != 0:
        raise Exception('Major version > 0 not implemented!')

    if current_db_version.minor_version == 0:
        migrate_0_0_to_0_1()

    if current_db_version.minor_version == 1:
        migrate_0_1_to_0_2()

    if current_db_version.minor_version == 2:
        migrate_0_2_to_0_3()

    log.info('Update Complete!')


def migrate_0_0_to_0_1():
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


def migrate_0_1_to_0_2():
    log.info('Updating from v0.1.X to v0.2.X')

    # CmsAuthor table will have been created already
    
    # Add author_id column to CmsUser
    log.info('Adding author_id to user table')
    try:
        add_column('ALTER TABLE {} ADD COLUMN author_id BIGINT REFERENCES {}(id)'.format(
            models.CmsUser.__tablename__,
            models.CmsAuthor.__tablename__
        ))
    except ColumnAlreadyExists:
        log.info('Column already exists: skipping')
    
    log.info('Adding missing authors')
    users = db.session.query(
        models.CmsUser
    ).filter(
        models.CmsUser.author_id == None
    ).order_by(
        models.CmsUser.id
    ).all()

    for user in users:
        log.info(' > Adding author for user "{}"'.format(user.name))
        user.author = models.CmsAuthor(user.name)
        db.session.commit()
    else:
        log.info('No authors to add')
    
    log.info('Making author_id NOT NULL')
    alter_column('ALTER TABLE {} ALTER COLUMN author_id SET NOT NULL'.format(
        models.CmsUser.__tablename__
    ))

    log.info('Changing post.author_id to reference author instead of user')

    log.info('> Temporarily renaming author_id to author_id_old')

    # First look for the old constraint

    constraints = get_foreign_key_constraints(models.CmsPost.__tablename__)
    has_old_constraint = False
    for constraint in constraints:
        # print('{}.{} -> {}'.format(constraint.table_name, constraint.constraint_name, constraint.definition))
        if '(author_id)' in constraint.definition \
                and '{}(id)'.format(models.CmsUser.__tablename__) in constraint.definition:
            has_old_constraint = True
            break

    if has_old_constraint:
        # Rename the column
        rename_column('ALTER TABLE {} RENAME COLUMN author_id TO author_id_old'.format(
            models.CmsPost.__tablename__
        ))
    else:
        log.info('It looks like the column has already been renamed - skipping')

    log.info('> Creating the new author_id column')
    
    try:
        add_column('ALTER TABLE {} ADD COLUMN author_id BIGINT REFERENCES {}(id)'.format(
            models.CmsPost.__tablename__,
            models.CmsAuthor.__tablename__
        ))
    except ColumnAlreadyExists:
        log.info('Column already exists - skipping')

    log.info('> Updating author_id values')
    posts = db.session.query(
        models.CmsPost
    ).filter(
        models.CmsPost.author_id == None
    ).order_by(
        models.CmsPost.id
    ).all()

    for post in posts:
        log.info('> > Updating "{}"'.format(post.title))
        old_author_id = db.session.execute('SELECT author_id_old FROM {} WHERE id={}'.format(
            models.CmsPost.__tablename__, post.id
        )).fetchall()[0][0]
        
        new_author_id = db.session.execute('SELECT author_id FROM {} WHERE id={}'.format(
            models.CmsUser.__tablename__, old_author_id
        )).fetchall()[0][0]

        post.author_id = new_author_id
        db.session.commit()
    else:
        log.info('No author ids to update')

    log.info('> Adding NOT NULL constraint')

    alter_column('ALTER TABLE {} ALTER COLUMN author_id SET NOT NULL'.format(
        models.CmsPost.__tablename__
    ))

    log.info('> Deleting old column')
    
    try:
        drop_column('ALTER TABLE {} DROP COLUMN author_id_old'.format(
            models.CmsPost.__tablename__
        ))
    except ColumnDoesNotExist:
        log.info('Column doesn\'t exist: skipping')
    
    log.info('Adding tag_type to tag table')
    try:
        add_column('ALTER TABLE {} ADD COLUMN tag_type CHARACTER VARYING'.format(
            models.CmsTag.__tablename__
        ))
    except ColumnAlreadyExists:
        log.info('Column already exists - skipping')

    log.info('Adding external_code to tag table')
    try:
        add_column('ALTER TABLE {} ADD COLUMN external_code CHARACTER VARYING'.format(
            models.CmsTag.__tablename__
        ))
    except ColumnAlreadyExists:
        log.info('Column already exists - skipping')

    log.info('Recreating Comment table')
    
    # Commit to avoid postgres locks stopping the table from being dropped
    db.session.commit()
    already_created = does_column_exist(models.CmsComment.__tablename__, 'edited_by_user_id')
    if already_created:
        log.info('Comments table already up to date - skipping')
    else:
        models.CmsComment.__table__.drop()
        models.CmsComment.__table__.create()

    # Update the version
    log.info('Updating DB Version to 0.2.X')
    current_db_version = models.CmsVersionHistory(0, 2)
    db.session.add(current_db_version)
    db.session.commit()


def migrate_0_2_to_0_3():
    log.info('Updating from v0.2.X to v0.3.X')

    # New published page tables will have been automatically added

    # Add author field to CmsPage table
    log.info('> Creating the new author_id column on page table')
    
    try:
        add_column('ALTER TABLE {} ADD COLUMN author_id BIGINT REFERENCES {}(id)'.format(
            models.CmsPage.__tablename__,
            models.CmsAuthor.__tablename__
        ))
    except ColumnAlreadyExists:
        log.info('Column already exists - skipping')

    # Add published field to CmsPage table
    log.info('> Creating the new published column on page table')
    
    try:
        add_column('ALTER TABLE {} ADD COLUMN published BOOLEAN DEFAULT FALSE NOT NULL'.format(
            models.CmsPage.__tablename__
        ))
    except ColumnAlreadyExists:
        log.info('Column already exists - skipping')

    log.info('Dropping default on published column')
    alter_column('ALTER TABLE {} ALTER COLUMN published DROP DEFAULT'.format(
        models.CmsPage.__tablename__
    ))

    # Update the version
    log.info('Updating DB Version to 0.3.X')
    current_db_version = models.CmsVersionHistory(0, 3)
    db.session.add(current_db_version)
    db.session.commit()


