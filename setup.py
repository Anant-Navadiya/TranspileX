from setuptools import setup, find_packages

from transpilex.config.package import PACKAGE_NAME, PACKAGE_VERSION, PACKAGE_DESCRIPTION, PACKAGE_AUTHOR, \
    PACKAGE_AUTHOR_EMAIL, PACKAGE_LICENSE

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description=PACKAGE_DESCRIPTION,
    author=PACKAGE_AUTHOR,
    author_email=PACKAGE_AUTHOR_EMAIL,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'arrow==1.3.0',
        'beautifulsoup4==4.13.4',
        'binaryornot==0.4.4',
        'certifi==2025.6.15',
        'chardet==5.2.0',
        'charset-normalizer==3.4.2',
        'click==8.2.1',
        'colorama==0.4.6',
        'cookiecutter==2.6.0',
        'idna==3.10',
        'Jinja2==3.1.6',
        'markdown-it-py==3.0.0',
        'MarkupSafe==3.0.2',
        'mdurl==0.1.2',
        'Pygments==2.19.1',
        'python-dateutil==2.9.0.post0',
        'python-slugify==8.0.4',
        'PyYAML==6.0.2',
        'requests==2.32.4',
        'rich==14.0.0',
        'six==1.17.0',
        'soupsieve==2.7',
        'text-unidecode==1.3',
        'typing_extensions==4.14.0',
        'urllib3==2.5.0',
    ],
    entry_points={
        'console_scripts': [
            'transpile=transpilex.main:main',
        ],
    },
    license=PACKAGE_LICENSE,
)
