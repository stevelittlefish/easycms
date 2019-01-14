"""
Utility Functions
"""

import logging
import urllib
import io
import os
import re

from flask import request, url_for
import requests
import PIL.Image
from littlefish import imageutil, timetool
from flaskfilemanager import filemanager

from .settings import get_settings

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def make_code(s, strip_hyphens=True):
    """
    Takes a str and turns it into a url-safe code by making lower case and
    replacing all characters that are non alpha-numeric with a hyphen
    """
    code = re.sub(r'[^a-z0-9]+', '-', s.lower())
    
    if strip_hyphens:
        code = code.strip('-')

    return code


def process_and_save_snippet_image(image_url, always_local=False):
    """
    :param image_url: The url of the image to process
    :param always_local: If True, skip the usual checks and assume this is a local image (used in create script)
    :return: The image url
    """
    settings = get_settings()
    fm_path_prefix = '{}/userfiles'.format(settings.filemanager_url_prefix)
    url_parts = urllib.parse.urlparse(image_url)
    extension = url_parts.path.split('.')[-1]

    assert extension

    if always_local or url_parts.netloc.encode('UTF-8') == request.host:
        raise Exception('Not implemented - local files!')

        # This is a url on our server!
        if url_parts.path.startswith(fm_path_prefix):
            content_path = url_parts.path[14:]
            log.info('File Manager Content: %s' % content_path)
            full_path = filemanager.get_file_path(content_path)
            log.info('Loading from disk: %s' % full_path)
            image = PIL.Image.open(full_path)
        else:
            raise Exception('Unhandled self hosted URL: %s' % image_url)
    else:
        # This is the full url
        full_image_url = image_url
        log.debug('Loading image via %s: %s' % (url_parts.scheme, full_image_url))
        r = requests.get(full_image_url)
        stream = io.BytesIO(r.content)
        image = PIL.Image.open(stream)

    assert image

    # We now have an image!  Woohooooo!
    # Now we need to resize it
    cropped_image = imageutil.resize_crop_image(image, settings.snippet_image_width,
                                                settings.snippet_image_height, pad_when_tall=False)

    # Generate a filename
    filename = 'sn-%s.%s' % (timetool.unix_time(), extension)
    full_path = os.path.join(settings.snippet_image_file_path, filename)

    log.info('Saving snippet image to %s' % full_path)
    cropped_image.save(
        full_path, quality=settings.pil_saved_image_quality,
        subsampling=settings.pil_saved_image_subsampling,
        compress_level=settings.pil_saved_image_compression_level
    )

    fm_path = full_path.replace(filemanager.get_root_path() + '/', '')
    try:
        return url_for('flaskfilemanager.userfile', filename=fm_path, _external=True, _scheme=request.scheme)
    except RuntimeError:
        # Hack for create script!
        if always_local:
            return url_for('flaskfilemanager.userfile', filename=fm_path, _external=True)
        else:
            raise


def add_default_snippet(post, always_local=False):
    imgs = post.get_images()
    if imgs:
        log.info('Automatically adding snippet image: %s' % imgs[0])
        post.snippet_image = process_and_save_snippet_image(imgs[0], always_local)
