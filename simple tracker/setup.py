from setuptools import setup

setup(
    name='simple-ttracker',
    version='0.1.1',
    author='A.T.',
    author_email='ppp_meter@ukr.net',
    description='Very simple torrent tracker',
    packages=['simple_tracker'],
    install_requires=['aiohttp', 'aiohttp-jinja2', 'Jinja2', 'async-timeout'],
    entry_points={
        'console_scripts': [
            'tracker_lo=simple_tracker.tracker:start_tracker'
        ]
    }
)
