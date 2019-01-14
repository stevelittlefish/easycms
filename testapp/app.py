"""
App factory function
"""

import logging
import datetime
import traceback

from flask import Flask, render_template, redirect
from werkzeug.exceptions import HTTPException
import jinja2
from littlefish import timetool
import easycms

from main import main
import permissions
import cmsconfig
from constants import posttypes
import create_tables
import auth

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

CACHE_BUSTER = int(timetool.unix_time())

log = logging.getLogger(__name__)


def create_app():
    logging.basicConfig(level=logging.DEBUG)

    # Create the webapp
    app = Flask(__name__)
    app.secret_key = 'TestAppSecretKeyWhoCaresWhatThisIs'
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://cmstestsite:power@127.0.0.1:5432/cmstestsite_db'
    app.config['FLASKFILEMANAGER_FILE_PATH'] = 'tmp-webapp-uploads'
    log.info('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    log.info(' Test App Starting')
    log.info('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    
    log.info('Trying to load testapp/config.py...')
    try:
        app.config.from_object('config')
        log.info('Local config loaded')
    except Exception:
        log.info('Config not found or invalid')

    init_db(app)
    init_cms(app)
    
    # Create tables
    create_tables.create_tables(app)

    init_templating(app)
    init_app_behaviours(app)
    register_blueprints(app)
    init_db_dependent(app)
    
    log.info('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    log.info(' Startup Complete!')
    log.info('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
    
    return app


def init_db(app):
    from models import db
    db.init_app(app)
    db.app = app
    log.info('Using database: "%s"' % db.engine)


def init_templating(app):
    log.info('Setting up templating environment')
    app.jinja_env.filters['format_datetime'] = timetool.format_datetime
    app.jinja_env.filters['format_date'] = timetool.format_date
    app.jinja_env.filters['format_date_long'] = timetool.format_date_long

    # Don't allow output of undefined variables in jinja templates
    app.jinja_env.undefined = jinja2.StrictUndefined


def init_app_behaviours(app):
    @app.context_processor
    def add_global_context():
        return {
            'date': datetime.datetime.now(),
            'CACHE_BUSTER': CACHE_BUSTER,
            'logged_in_name': auth.get_full_name(),
            'logged_in_email': auth.get_email(),
            'backend': auth.is_backend_user()
        }

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        if e.code >= 300 and e.code < 400:
            return redirect(e.new_url, e.code)

        return render_template('http_exception.html', e=e), e.code

    @app.errorhandler(Exception)
    def catch_all(e):
        title = str(e)
        message = traceback.format_exc()

        log.error('Exception caught: %s\n%s' % (title, message))

        return render_template('error_page.html', title=title, message=message, preformat=True)


def register_blueprints(app):
    log.info('Registering blueprints')
    app.register_blueprint(main)
    app.register_blueprint(easycms.blueprint, url_prefix='/cms-admin')
    

def init_db_dependent(app):
    log.info('Loading permissions')
    permissions.reload()


def init_cms(app):
    from models import metadata, db

    log.info('Initialising CMS')
    # all_post_types = ['post', 'event']
    update_db = False
    # update_db = True
    easycms.init(app, db.engine, metadata=metadata,
                 access_control_config=cmsconfig.CmsAccessControl(),
                 settings=cmsconfig.settings, all_post_types=posttypes.ALL_POST_TYPES,
                 page_defs=cmsconfig.page_defs, update_db=update_db)


