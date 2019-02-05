"""
Code for generating an RSS feed for the CMS
"""

import logging
import datetime

from lxml.builder import ElementMaker
from lxml import etree
from lxml.etree import CDATA
from flask import request, make_response

from . import get_all_posts_query
from .settings import get_settings

__author__ = 'Stephen Brown (Little Fish Solutions LTD)'

log = logging.getLogger(__name__)


def generate_rss_xml(website_name=None, website_description=None):
    settings = get_settings()

    if settings.view_post_url_function is None:
        raise Exception('To generate an RSS feed you need to set the view_post_url_function variable in your '
                        'EasyCmsSettings object')

    if website_name is None:
        website_name = settings.website_name

    if website_description is None:
        website_description = 'RSS feed of all posts for {}'.format(website_name)

    get_url = settings.view_post_url_function

    posts = get_all_posts_query().all()

    nsmap = {
        'content': 'http://purl.org/rss/1.0/modules/content/',
        # 'wfw': 'http://wellformedweb.org/CommentAPI/',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'atom': 'http://www.w3.org/2005/Atom',
        'sy': 'http://purl.org/rss/1.0/modules/syndication/',
        'slash': 'http://purl.org/rss/1.0/modules/slash/'
    }
    E = ElementMaker(nsmap=nsmap)

    CONTENT = ElementMaker(nsmap={None: nsmap['content']}, namespace=nsmap['content'])
    # WFW = ElementMaker(nsmap={None: nsmap['wfw']}, namespace=nsmap['wfw'])
    DC = ElementMaker(nsmap={None: nsmap['dc']}, namespace=nsmap['dc'])
    ATOM = ElementMaker(nsmap={None: nsmap['atom']}, namespace=nsmap['atom'])
    SY = ElementMaker(nsmap={None: nsmap['sy']}, namespace=nsmap['sy'])
    SLASH = ElementMaker(nsmap={None: nsmap['slash']}, namespace=nsmap['slash'])

    def format_datetime(dt):
        # Wed, 28 Jan 2015 19:51:49 +0000
        return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')

    last_build_date = datetime.datetime(1900, 1, 1)

    for post in posts:
        build_date = post.revisions[0].timestamp
        if build_date > last_build_date:
            last_build_date = build_date

    channel = E.channel(
        E.title(website_name),
        ATOM.link(href=request.url, rel='self', type='application/rss+xml'),
        E.link(request.url),
        E.description(website_description),
        E.lastBuildDate(format_datetime(last_build_date)),
        E.language('en-GB'),
        SY.updatePeriod('hourly'),
        SY.updateFrequency('1'),
        E.generator('http://littlefish.solutions/')
    )

    for post in posts:
        # comments = 0
        # for comment in post.comments:
        #     if comment.approved and not comment.deleted:
        #         comments += 1
        
        rss_description = post.description + '&hellip; <a href="{}">Read More</a>'.format(get_url(post))
        rss_content = post.content

        if post.main_image_url:
            rss_content = '<img src="{}"><br><br>{}'.format(post.main_image_url, rss_content)
        
        channel.append(
            E.item(
                E.title(post.title),
                E.link(get_url(post)),
                # E.link(url_for('blog.view_post', nice_name=post.nice_name, _external=True) + '#comments-%s' % post.id),
                E.pubDate(format_datetime(post.published)),
                DC.creator(CDATA(post.author.name)),
                E.category(CDATA(post.category.name)),
                E.guid({'isPermaLink': 'false'}, get_url(post)),
                E.description(CDATA(rss_description)),
                CONTENT.encoded(CDATA(rss_content)),
                # WFW.commentRss(),
                SLASH.comments(str(0))
            )
        )

    rss = E.rss(
        {'version': '2.0'},
        channel
    )

    xml = '<?xml version="1.0" encoding="UTF-8"?>' + etree.tostring(rss, pretty_print=True).decode('utf-8')
    
    return xml


def rss_flask_view(website_name=None, website_description=None):
    xml = generate_rss_xml(website_name, website_description)
    response = make_response(xml)
    response.headers['Content-Type'] = 'text/xml'  # 'application/rss+xml'
    return response
