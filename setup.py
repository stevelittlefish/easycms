import sys
from setuptools import setup

if sys.version_info.major < 3:
    sys.exit('Sorry, this library only supports Python 3')

setup(
    name='easycms',
    packages=['easycms', 'easycms.templates', 'easycms.static', 'easycms.customfields'],
    include_package_data=True,
    version='0.2.1',
    description='CMS and Blogging Sysetm for Flask',
    author='Stephen Brown (Little Fish Solutions LTD)',
    author_email='opensource@littlefish.solutions',
    url='https://github.com/stevelittlefish/easycms',
    download_url='https://github.com/stevelittlefish/easycms/archive/v0.2.1.tar.gz',
    keywords=['flask', 'jinja2', 'easy', 'cms', 'blog'],
    license='LGPLv3',
    classifiers=[
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Framework :: Flask',
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries'
    ],
    install_requires=[
        'flaskfilemanager>=0.0.5',
        'SQLAlchemy>=1.2.10',
        'Flask>=1.0.2',
        'Pillow>=5.2.0',
        'requests>=2.19.1',
        'easyforms>=0.1.8',
        'littlefish>=0.0.25',
        'titlecase>=0.12.0',
        'beautifulsoup4>=4.6.0',
        'unidecode>=1.0.23',
        'lxml>=4.2.5'
    ],
)

