from setuptools import setup, find_packages

setup(
    name='transpilex',
    version='1.0.0',
    description='Transpile HTML into given frameworks',
    author='Anant Navadiya',
    author_email='contact@anantnavadiya.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[],
    entry_points={
        'console_scripts': [
            'transpile=transpilex.main:main',
        ],
    },
    license='MIT',
)
