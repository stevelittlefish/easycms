"""
Backend editor for CMS - implemented with a Flask blueprint
"""

import logging
import traceback
import datetime
import os
from functools import wraps

from flask import Blueprint, render_template, request, abort, redirect, jsonify, url_for,\
    flash
import easyforms
from easyforms import CkeditorConfig  # noqa
from easyforms import validate
from easyforms.bs4 import Form
from littlefish import timetool, imageutil
from littlefish.pager import Pager
from titlecase import titlecase
import sqlalchemy.exc
import flaskfilemanager
from sqlalchemy import or_

from . import accesscontrol, models, cmsutil
from .settings import get_settings, get_page_defs
from .models import db
import easycms
from . import comments

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)

editor = Blueprint('easycms_editor', __name__, static_folder='static', template_folder='templates')

# Set up jinja2 filters
editor.add_app_template_filter(timetool.format_date, 'easycms_format_date')
editor.add_app_template_filter(timetool.format_datetime, 'easycms_format_datetime')
editor.add_app_template_filter(timetool.format_datetime_seconds, 'easycms_format_datetime_seconds')


def snippet_view(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        settings = get_settings()
        if not settings.snippets_enabled:
            return error_page('If you\'d like to use snippets, please enable them in the '
                              'EasyCmsSettings used to initialise EasyCMS',
                              title='Snippets Disabled')

        return f(*args, **kwargs)

    return decorated


def get_post_types_input(name, value=None, required=True, readonly=False):
    if len(easycms.post_types) == 1 or readonly:
        return easyforms.TextField(name, value=value if value else easycms.post_types[0], readonly=True,
                                   required=required)
    else:
        return easyforms.ListSelectField(name, values=easycms.post_types,
                                         value=value if value else easycms.post_types[0],
                                         required=required)


def error_page(message, title='Error', preformat=False, http_status_code=500):
    return render_template('easycms/error_page.html', title=title, message=message, preformat=preformat), http_status_code


@editor.context_processor
def add_editor_context():
    return {
        'access_control': accesscontrol.get_access_control(),
        'settings': get_settings(),
        'post_types': easycms.post_types,
        'pages_enabled': bool(get_page_defs()),
        'base_template': get_settings().editor_base_template
    }


@editor.errorhandler(Exception)
def internal_error(e):
    try:
        db.session.rollback()
    except:  # noqa
        pass

    title = str(e)
    message = traceback.format_exc()

    log.error('Exception caught: %s\n%s' % (title, message))

    return error_page(message, title=title, preformat=True, http_status_code=500)

    
@editor.route('/')
@accesscontrol.can_view_editor
def index():
    return render_template('easycms/index.html')


@editor.route('/pages')
@accesscontrol.can_view_editor
def view_pages():
    query = db.session.query(models.CmsPage).order_by(models.CmsPage.code)
    pager = Pager(30, request.args.get('page', 1), query)

    return render_template('easycms/view_pages.html', pager=pager)


@editor.route('/pages/<int:page_id>')
@accesscontrol.can_view_editor
def view_page(page_id):
    page = db.session.query(models.CmsPage).filter(models.CmsPage.id == page_id).one_or_none()
    if not page:
        abort(404)

    return render_template('easycms/view_page.html', page=page)


@editor.route('/pages/<int:page_id>/edit', methods=['GET', 'POST'])
@accesscontrol.can_edit_page
def edit_page(page_id=None):
    settings = get_settings()

    ajax = request.args.get('ajax') == 'true'

    page = db.session.query(models.CmsPage).filter(models.CmsPage.id == page_id).first()
    if not page:
        abort(404)

    form = Form([
        easyforms.CkeditorField('page', value=page.content, height=550, width=10,
                                on_change='handleCkeditorChange', config=settings.ckeditor_config)
    ], label_width=1, submit_text=None, form_name='create-page', form_type=easyforms.HORIZONTAL)
    
    user = accesscontrol.get_access_control().get_logged_in_cms_user()

    if form.ready:
        content = form['page']
        if content is None:
            content = ''

        page.content = content

        # Always save a history record
        revision = models.CmsPageRevision(page, user)
        db.session.add(revision)

        try:
            db.session.commit()
        except:  # noqa
            if ajax:
                return jsonify({'status': 'error', 'error': 'Background save failed!'})
            raise

        if ajax:
            # We need to send the edit url for this page, otherwise, we will repeatedly create new pages each time
            # we background save
            return jsonify({'status': 'ok',
                            'submitUrl': url_for('.edit_page', page_id=page.id),
                            'message': 'Page save successfully (background)'})
        
        flash('Page "{}" saved'.format(page.title), 'success')
        return redirect(url_for('.view_page', page_id=page.id))

    return render_template('easycms/edit_page.html', form=form, page=page)


@editor.route('/pages/<int:page_id>/history/latest', methods=['GET', 'POST'])
@editor.route('/pages/<int:page_id>/history/<int:history_id>', methods=['GET', 'POST'])
@accesscontrol.can_edit_page
def view_page_history(page_id, history_id=None):
    page = db.session.query(models.CmsPage).filter(models.CmsPage.id == page_id).one_or_none()
    if not page:
        abort(404)

    if not page.revisions:
        flash('This page has no history to view', 'danger')
        return redirect(url_for('.edit_page', page_id=page.id))

    if history_id is None:
        history = page.revisions[0]
    else:
        # Load the history record
        history = db.session.query(
            models.CmsPageRevision
        ).filter(
            models.CmsPageRevision.page_id == page_id,
            models.CmsPageRevision.id == history_id
        ).one_or_none()

        if not history:
            abort(404)

    if request.method == 'POST':
        # We need to restore the revision
        page.content = history.content

        # Add another history row
        user = accesscontrol.get_access_control().get_logged_in_cms_user()
        notes = 'Restored revision {} from {}'.format(
            history.id, timetool.format_datetime_seconds(history.timestamp)
        )
        new_history = models.CmsPageRevision(page, user, revision_notes=notes)
        db.session.add(new_history)
        db.session.commit()
        flash('Revision restored successfully', 'success')
        return redirect(url_for('.view_page', page_id=page.id))

    return render_template('easycms/view_page_history.html', page=page, history=history)


@editor.route('/posts')
@editor.route('/posts/<string:post_type>')
@accesscontrol.can_view_editor
def view_posts(post_type=None):
    if post_type and post_type not in easycms.post_types:
        abort(404)

    pager = easycms.get_all_posts_pager(request.args.get('page', 1), num_per_page=30,
                                        post_type=post_type, allow_unpublished=True)

    return render_template('easycms/view_posts.html', pager=pager, post_type=post_type)


@editor.route('/posts/<int:post_id>')
@accesscontrol.can_view_editor
def view_post(post_id):
    post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).one_or_none()
    if not post:
        abort(404)
    
    return render_template('easycms/view_post.html', post=post)


@editor.route('/posts/<string:post_type>/new', methods=['GET', 'POST'])
@editor.route('/posts/<int:post_id>/edit', methods=['GET', 'POST'])
@accesscontrol.can_edit_post
def edit_post(post_type=None, post_id=None):
    settings = get_settings()
    ac = accesscontrol.get_access_control()

    post = None

    ajax = request.args.get('ajax') == 'true'

    if post_id:
        post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).first()
        if not post:
            abort(404)
        post_type = post.post_type

    published_help_text = 'The post will only be visible if this box is ticked'
    if post and post.published:
        published_help_text += '. Published %s' % timetool.format_datetime_long(post.published)

    categories = db.session.query(
        models.CmsCategory
    ).filter(
        models.CmsCategory.post_type == post_type
    ).order_by(
        models.CmsCategory.name
    ).all()

    if not categories:
        flash('You must add at least one {0} category before creating a {0} post'.format(post_type), 'danger')
        return redirect(url_for('.view_categories'))

    tagline_max_length = settings.tagline_max_length

    fields = [
        easyforms.TextField('title', required=True, value=post.title if post else None, width=10)
    ]

    if ac.can_publish_post():
        fields.append(
            easyforms.BooleanCheckbox('publish-post', default=post.published is not None if post else False,
                                      help_text=published_help_text)
        )
    
    fields += [
        easyforms.ObjectListSelectField('category', categories, required=True, value=post.category if post else categories[0], width=3),
        easyforms.TextField('tagline', required=True, value=post.tagline if post else None,
                            help_text='A very short description of the post. You can copy + paste the first sentence here! Max {} characters'.format(tagline_max_length),
                            width=10, validators=[validate.max_length(tagline_max_length)])
    ]

    if settings.post_main_image_enabled:
        fields.append(
            easyforms.FilemanagerField('main-image', label='Image', width=10,
                                       value=post.main_image_url if post else None,
                                       required=settings.post_main_image_required,
                                       help_text='The main image to display for this post')
        )

    fields.append(easyforms.CkeditorField('post', value=post.content if post else None, height=550, width=10,
                                          on_change='handleCkeditorChange', config=settings.ckeditor_config))

    form = Form(fields, label_width=1, submit_text=None, form_name='create-post', form_type=easyforms.HORIZONTAL)
    
    user = accesscontrol.get_access_control().get_logged_in_cms_user()

    if form.ready:
        if post:
            duplicate = db.session.query(
                models.CmsPost
            ).filter(
                models.CmsPost.post_type == post_type,
                models.CmsPost.title.ilike(form['title']),
                models.CmsPost.id != post.id
            ).first()
        else:
            duplicate = db.session.query(
                models.CmsPost
            ).filter(
                models.CmsPost.post_type == post_type,
                models.CmsPost.title.ilike(form['title'])
            ).first()

        if duplicate:
            form.set_error('title', 'A post with this title already exists')

    if form.ready:
        publish_post = False
        if ac.can_publish_post():
            publish_post = form['publish-post'] or 'post-publish' in request.form

        content = form['post']
        if content is None:
            content = ''
        
        main_image_url = None
        if settings.post_main_image_enabled:
            main_image_url = form['main-image']

        if post:
            post.category = form['category']
            post.title = titlecase(form['title'])
            post.content = content
            post.tagline = form['tagline']
            post.main_image_url = main_image_url
        else:
            post = models.CmsPost(
                post_type, form['category'], titlecase(form['title']), content, user.author,
                form['tagline'], publish_post, main_image_url=main_image_url
            )
            db.session.add(post)

        if publish_post and not post.published:
            post.published = datetime.datetime.utcnow()
        elif not publish_post and post.published:
            post.published = None

        # Always save a history record
        revision = models.CmsPostRevision(post, user)
        db.session.add(revision)

        # If we don't have a snippet image, try to create one
        if not post.snippet_image and settings.snippets_enabled:
            cmsutil.add_default_snippet(post)

        try:
            db.session.commit()
        except:  # noqa
            if ajax:
                return jsonify({'status': 'error', 'error': 'Background save failed!'})
            raise

        # Refresh the cache when you edit a post
        # from blogcache import refresh_cache
        # refresh_cache()

        if ajax:
            # We need to send the edit url for this post, otherwise, we will repeatedly create new posts each time
            # we background save
            return jsonify({'status': 'ok',
                            'submitUrl': url_for('.edit_post', post_id=post.id),
                            'message': 'Post save successfully (background)'})
        
        flash('Post "{}" saved'.format(post.title), 'success')
        return redirect(url_for('.view_post', post_id=post.id))

    elif ajax:
        error_fields = []
        for field in form.fields:
            if field.error:
                error_fields.append(field.label)

        return jsonify({
            'status': 'error',
            'error': 'Background save failed due to missing / invalid values for the '
                     'following fields: {}'.format(', '.join(error_fields))
        })

    all_tags = db.session.query(models.CmsTag).order_by(models.CmsTag.name).all()

    return render_template('easycms/edit_post.html', form=form, post=post, all_tags=all_tags)


@editor.route('/posts/<int:post_id>/edit-tags', methods=['GET', 'POST'])
@accesscontrol.can_tag_post
def edit_post_tags(post_id):
    post = db.session.query(
        models.CmsPost
    ).filter(
        models.CmsPost.id == post_id
    ).one_or_none()

    if not post:
        abort(404)

    can_manage_tags = accesscontrol.get_access_control().can_manage_tags()

    extra_help_text = ''
    if not can_manage_tags:
        extra_help_text = '. Note: you only have permission to add existing tags to this post.'

    form = Form([
        easyforms.TextAreaField('tags', 2,
                                help_text='Enter as many tags as you want, comma separated{}'.format(extra_help_text),
                                required=True),
        easyforms.SubmitButton('submit', 'Add Tags')
    ], submit_text=None, form_type=easyforms.HORIZONTAL)

    if form.ready:
        tags = form['tags']
        tags = tags.split(',')
        
        for tag_name in tags:
            tag_name = tag_name.strip()
            if tag_name:
                log.debug('Adding tag to post: %s' % tag_name)
                # See if the tag already exists
                tag_code = models.CmsTag.name_to_code(tag_name)

                tag = db.session.query(
                    models.CmsTag
                ).filter(
                    models.CmsTag.post_type == post.post_type,
                    models.CmsTag.code == tag_code
                ).first()

                if tag:
                    log.debug('Adding existing tag to post')
                elif can_manage_tags:
                    tag = models.CmsTag(post.post_type, tag_name)
                    log.debug('Creating new tag')
                else:
                    log.debug('Not creating new tag - user doesn\'t have permission')
                    flash('Not adding tag "{}" - you do not have permission to create new tags'.format(
                        tag_name
                    ), 'danger')
                
                if tag:
                    flash('Tag {} added'.format(tag_name), 'success')
                    post.tags.append(tag)

        db.session.commit()
        form.clear()

    if 'delete-tag' in request.form:
        tag = db.session.query(
            models.CmsTag
        ).filter(
            models.CmsTag.post_type == post.post_type,
            models.CmsTag.code == request.form['delete-tag']
        ).first()

        if not tag:
            flash('Tag doesn\'t exist', 'danger')
        else:
            post.tags.remove(tag)
    
            db.session.commit()
            # Check if there are any posts left with this tag
            db.session.expire(tag)
            if not tag.posts and can_manage_tags:
                # TODO: this could leave orphaned tags!
                db.session.delete(tag)
                db.session.commit()
            
            db.session.refresh(post)

        flash('Tag deleted', 'success')

    all_tags = db.session.query(
        models.CmsTag
    ).filter(
        models.CmsTag.post_type == post.post_type
    ).order_by(
        models.CmsTag.name
    ).all()

    return render_template('easycms/edit_post_tags.html', form=form, post=post, all_tags=all_tags)


@editor.route('/posts/<int:post_id>/seo', methods=['GET', 'POST'])
@accesscontrol.can_edit_post_seo
def edit_post_seo(post_id):
    settings = get_settings()

    post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).one_or_none()
    if not post:
        abort(404)

    success = None
    
    all_authors = db.session.query(
        models.CmsAuthor
    ).order_by(
        models.CmsAuthor.name
    ).all()

    form = Form([
        easyforms.ObjectListSelectField('author', all_authors, value=post.author),
        easyforms.TextField('html-title', value=post.html_title, help_text='Leave blank for: "%s"' % post.title,
                            validators=[validate.max_length(55)]),
        easyforms.TextAreaField('html-description', value=post.html_description,
                                help_text='Leave blank for: "%s"' % post.description,
                                rows=3, validators=[validate.max_length(159)]),
        easyforms.TextField('code', label='Code (URL name)', required=True, value=post.code,
                            readonly=not settings.post_code_is_edittable,
                            help_text='This will change the post URL. Can only contain a-z, 0-9 and -')
    ], form_type=easyforms.HORIZONTAL)

    if form.ready:
        post.author = form['author']
        post.html_title = form['html-title']
        post.html_description = form['html-description']
        post.code = form['code']
        db.session.commit()
        success = 'Post updated'

    return render_template('easycms/edit_post_seo.html', post=post, form=form, success=success)


@editor.route('/posts/<int:post_id>/edit-publish-date', methods=['GET', 'POST'])
@accesscontrol.can_publish_post
def edit_post_publish_date(post_id):
    post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).one_or_none()
    if not post:
        abort(404)

    published = timetool.to_local_time(post.published)

    form = Form([
        easyforms.DatePickerField('date', value=published.date()),
        easyforms.TimeInputField('time', value=published.time())
    ], label_width=1, form_type=easyforms.HORIZONTAL)

    if form.ready:
        post.published = timetool.to_utc_time(datetime.datetime.combine(form['date'], form['time']))
        db.session.commit()
        flash('Published date updated', 'success')
        return redirect(url_for('.edit_post', post_id=post.id))

    return render_template('easycms/edit_post_publish_date.html', post=post, form=form)


@editor.route('/posts/<int:post_id>/history/latest', methods=['GET', 'POST'])
@editor.route('/posts/<int:post_id>/history/<int:history_id>', methods=['GET', 'POST'])
@accesscontrol.can_edit_post
def view_post_history(post_id, history_id=None):
    post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).one_or_none()
    if not post:
        abort(404)

    if history_id is None:
        history = post.revisions[0]
    else:
        # Load the history record
        history = db.session.query(
            models.CmsPostRevision
        ).filter(
            models.CmsPostRevision.post_id == post_id,
            models.CmsPostRevision.id == history_id
        ).one_or_none()

        if not history:
            abort(404)

    if request.method == 'POST':
        # We need to restore the revision
        post.title = history.title
        post.content = history.content

        # Add another history row
        user = accesscontrol.get_access_control().get_logged_in_cms_user()
        notes = 'Restored revision {} from {}'.format(
            history.id, timetool.format_datetime_seconds(history.timestamp)
        )
        new_history = models.CmsPostRevision(post, user, revision_notes=notes)
        db.session.add(new_history)
        db.session.commit()
        flash('Revision restored successfully', 'success')
        return redirect(url_for('.view_post', post_id=post.id))

    return render_template('easycms/view_post_history.html', post=post, history=history)


@editor.route('/posts/<int:post_id>/snippet', methods=['GET', 'POST'])
@accesscontrol.can_edit_post
@snippet_view
def edit_post_snippet(post_id):
    post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).first()
    if not post:
        abort(404)

    form = Form(submit_text=None, read_form_data=False, form_type=easyforms.HORIZONTAL)
    form.label_width = 2

    snippet_max_length = get_settings().snippet_description_max_length
    snippet_validators = [validate.max_length(snippet_max_length)]
    default_description = post.get_snippet_description()

    if snippet_max_length <= 120:
        description_field = easyforms.TextField('description', value=default_description, width=10,
                                                label_width=2, validators=snippet_validators)
    else:
        description_field = easyforms.TextAreaField('description', value=default_description, width=10,
                                                    rows=4, label_width=2, validators=snippet_validators)

    form.add_section('main', [
        easyforms.TextField('title', value=post.get_snippet_title(), width=10, label_width=2, required=True),
        description_field
    ])

    form.add_submit('Submit')

    form.read_form_data()

    updated = False

    # Always update the image if it's in the request
    if 'image' in request.form and request.form['image']:
        image_url = request.form['image']
        post.snippet_image = cmsutil.process_and_save_snippet_image(image_url)

        updated = True

    if form.ready:
        post.snippet_title = form['title']
        post.snippet_description = form['description']

        updated = True

    if updated:
        db.session.commit()

        # Refresh the cache when you edit a post
        # from blogcache import refresh_cache
        # refresh_cache()

        flash('Snippet updated', 'success')
        return redirect(url_for('.edit_post', post_id=post.id))
    
    return render_template('easycms/edit_post_snippet.html', post=post, form=form)


@editor.route('/posts/<int:post_id>/snippet/add-snippet-image', methods=['GET', 'POST'])
@accesscontrol.can_edit_post
@snippet_view
def add_snippet_image(post_id):
    post = db.session.query(models.CmsPost).filter(models.CmsPost.id == post_id).one_or_none()
    if not post:
        abort(404)

    form = Form([
        easyforms.ImageUploadField('snippet-image', required=True),
    ], label_width=2, form_type=easyforms.HORIZONTAL)

    if form.ready:
        image = form['snippet-image']
        # Get the form field and extract the original filename
        image_field = form.get_field('snippet-image')
        original_filename = image_field.filename
        extension = original_filename.split('.')[-1]
        settings = get_settings()

        filename = 'sn-%s.%s' % (timetool.unix_time(), extension)
        full_path = os.path.join(settings.snippet_image_file_path, filename)
        fm_path = full_path.replace(flaskfilemanager.filemanager.get_root_path() + '/', '')

        cropped_image = imageutil.resize_crop_image(image, settings.snippet_image_width,
                                                    settings.snippet_image_height,
                                                    pad_when_tall=True)

        log.info('Saving snippet image to %s' % full_path)
        cropped_image.save(
            full_path, quality=settings.pil_saved_image_quality,
            subsampling=settings.pil_saved_image_subsampling,
            compress_level=settings.pil_saved_image_compression_level
        )

        url = url_for('flaskfilemanager.userfile', filename=fm_path, _external=True, _scheme=request.scheme)

        post.snippet_image = url
        db.session.commit()

        flash('Snippet image updated', 'success')
        return redirect(url_for('.edit_post_snippet', post_id=post.id))

    return render_template('easycms/add_snippet_image.html', post=post, form=form)


@editor.route('/categories')
@accesscontrol.can_view_editor
def view_categories():
    categories = db.session.query(models.CmsCategory).order_by(
        models.CmsCategory.name,
        models.CmsCategory.post_type
    ).all()

    return render_template('easycms/view_categories.html', categories=categories)


@editor.route('/categories/add-new-category', methods=['GET', 'POST'])
@editor.route('/categories/<string:post_type>/<string:code>', methods=['GET', 'POST'])
@accesscontrol.can_edit_category
def edit_category(post_type=None, code=None):
    category = None
    if code:
        category = db.session.query(models.CmsCategory).filter(
            models.CmsCategory.post_type == post_type,
            models.CmsCategory.code == code
        ).first()
        if not category:
            abort(404)

    form = Form([
        get_post_types_input('post-type', readonly=category is not None,
                             value=category.post_type if category else None),
        easyforms.TextField('name', required=True, value=category.name if category else None),
        easyforms.TextField('code', label='URL Name', required=True,
                            value=category.code if category else None,
                            validators=[validate.url_safe])
    ], form_type=easyforms.HORIZONTAL)

    if form.ready:
        if category:
            category.update_name(form['name'], form['code'])
        else:
            category = models.CmsCategory(form['post-type'], form['name'], form['code'])
            db.session.add(category)
        
        try:
            db.session.commit()
            flash('Category saved', 'success')
            return redirect(url_for('.view_categories'))

        except sqlalchemy.exc.IntegrityError:
            db.session.rollback()

            error_message = 'Either the name or the code is already in use for this post type'
            form.set_error('name', error_message)
            form.set_error('code', error_message)

    return render_template('easycms/edit_category.html', form=form, category=category)


@editor.route('/categories/<int:category_id>/delete', methods=['GET', 'POST'])
@accesscontrol.can_edit_category
def delete_category(category_id):
    category = db.session.query(models.CmsCategory)\
        .filter(models.CmsCategory.id == category_id).one_or_none()

    if not category:
        abort(404)

    if request.method == 'POST':
        db.session.delete(category)

        try:
            db.session.commit()

            flash('Category deleted', 'success')

            return redirect(url_for('.view_categories'))

        except sqlalchemy.exc.IntegrityError:
            db.session.rollback()
            flash('This category can\'t be deleted as some posts are using this category', 'danger')

    return render_template('easycms/delete_category.html', category=category)


@editor.route('/posts/<int:post_id>/delete', methods=['GET', 'POST'])
@accesscontrol.can_delete_post
def delete_post(post_id):
    post = db.session.query(models.CmsPost)\
        .filter(models.CmsPost.id == post_id).one_or_none()

    if not post:
        abort(404)

    if request.method == 'POST':
        post.tags = []
        for revision in post.revisions:
            db.session.delete(revision)
        db.session.delete(post)
        db.session.commit()

        flash('Post deleted', 'success')

        return redirect(url_for('.view_posts'))

    return render_template('easycms/delete_post.html', post=post)


@editor.route('/comments', methods=['GET', 'POST'])
@editor.route('/comments/<string:deleted>/<string:pending>/<string:approved>', methods=['GET', 'POST'])
@accesscontrol.can_view_editor
def view_comments(deleted='False', pending='True', approved='True'):
    show_deleted = deleted == 'True'
    show_pending = pending == 'True'
    show_approved = approved == 'True'

    comments_query = db.session.query(
        models.CmsComment
    ).order_by(
        models.CmsComment.timestamp.desc()
    )

    if show_deleted:
        if show_pending:
            if show_approved:
                # Show all posts
                pass
            else:
                # All but approved
                comments_query = comments_query.filter(or_(models.CmsComment.approved == False, models.CmsComment.deleted == True))
        else:
            if show_approved:
                # Deleted and approved only
                comments_query = comments_query.filter(or_(models.CmsComment.approved == True, models.CmsComment.deleted == True))
            else:
                # Don't show pending or approved
                comments_query = comments_query.filter(models.CmsComment.deleted == True)
    else:
        # Don't show deleted comments
        if show_pending:
            if show_approved:
                # All non-deleted posts
                comments_query = comments_query.filter(models.CmsComment.deleted == False)
            else:
                # Pending only
                comments_query = comments_query.filter(models.CmsComment.deleted == False, models.CmsComment.approved == False)
        else:
            if show_approved:
                # Approved only
                comments_query = comments_query.filter(models.CmsComment.deleted == False, models.CmsComment.approved == True)
            else:
                # Show nothing!
                comments_query = comments_query.filter(False)

    page = request.args.get('page', '1')
    pager = Pager(30, page, comments_query)
    
    ac = accesscontrol.get_access_control()

    if request.method == 'POST' and ac.can_moderate_comments:
        comment_id = request.form['comment']
        comment = db.session.query(
            models.CmsComment
        ).filter(
            models.CmsComment.id == comment_id
        ).one()

        send_reply_email = False
        if 'un-approve' in request.form:
            comment.approved = False
        elif 'approve' in request.form:
            comment.approved = True
            if comment.reply_to_id:
                send_reply_email = True
        elif 'delete' in request.form:
            comment.deleted = True
        elif 'un-delete' in request.form:
            comment.deleted = False
        else:
            raise Exception('I don\'t know what you want me to do!')

        db.session.commit()
        
        comment_reply_hook = get_settings().comment_reply_hook
        if comment_reply_hook and send_reply_email:
            comment_reply_hook(comment)

    return render_template('easycms/view_comments.html', pager=pager, show_approved=show_approved,
                           show_pending=show_pending, show_deleted=show_deleted)


@editor.route('/comments/edit/<int:comment_id>', methods=['GET', 'POST'])
@accesscontrol.can_moderate_comments
def edit_comment(comment_id):
    comment = easycms.get_comment_by_id(comment_id)
    if not comment:
        abort(404)

    form = easyforms.Form([
        comments.get_comment_reply_html_field('comment', required=True, value=comment.content)
    ], submit_text='Save Changes')

    if form.ready:
        if not comment.original_content:
            comment.original_content = comment.content
        comment.content = form['comment']
        comment.edit_timestamp = datetime.datetime.utcnow()
        ac = accesscontrol.get_access_control()
        user = ac.get_logged_in_cms_user()
        comment.editor_user = user
        comment.editor = user.author

        flash('Comment by has been successfully edited', 'success')
        db.session.commit()

    return render_template('easycms/edit_comment.html', form=form, comment=comment)


@editor.route('/authors')
@accesscontrol.can_view_editor
def view_authors():
    authors = db.session.query(
        models.CmsAuthor
    ).order_by(
        models.CmsAuthor.name
    ).all()

    return render_template('easycms/view_authors.html', authors=authors)


@editor.route('/authors/new', methods=['GET', 'POST'])
@editor.route('/authors/<string:author_code>/edit', methods=['GET', 'POST'])
@accesscontrol.can_manage_authors
def edit_author(author_code=None):
    author = None
    if author_code:
        author = db.session.query(
            models.CmsAuthor
        ).filter(
            models.CmsAuthor.code == author_code
        ).one_or_none()

        if not author:
            abort(404)
    
    fields = [
        easyforms.TextField('name', required=True, value=author.name if author else None)
    ]
    
    if author:
        fields.append(easyforms.CodeField('code', required=True, value=author.code,
                                          help_text='Note: changing this field may cause some URLs to change'))

    form = Form(fields, form_type=easyforms.VERTICAL)

    if form.ready:
        try:
            if author:
                edited_author = author
                edited_author.name = form['name']
                edited_author.code = form['code']
                db.session.commit()

                flash('Author \'{}\' updated'.format(edited_author.name), 'success')
            else:
                edited_author = models.CmsAuthor(form['name'])
                db.session.add(edited_author)
                db.session.commit()

                flash('Author \'{}\' added to the system'.format(edited_author.name), 'success')
            
            return redirect(url_for('.view_authors'))

        except sqlalchemy.exc.IntegrityError as e:
            db.session.rollback()
            
            if 'cms_author_name_key' in str(e):
                error_message = 'Another author already exists with this name'
                form.set_error('name', error_message)
            elif 'cms_author_code_key' in str(e):
                if author:
                    error_message = 'Another author already exists with this code'
                    form.set_error('code', error_message)
                else:
                    error_message = 'The name you have chosen is too similar to another author.  (Specifically, ' \
                                    'the auto-generated code already exists on another author.)  Please either ' \
                                    'choose a different name or change the code on the conflicting author'
                    form.set_error('name', error_message)
            else:
                raise e

    return render_template('easycms/edit_author.html', author=author, form=form)
