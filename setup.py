from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='fordconnect',
    version='0.2.7',
    author="sillygoose",
    author_email="sillygoose@me.com",
    description="Python examples for accessing FordPass status, trips, and charging queries.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sillygoose/fordconnect",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'requests',
        'json',
        'python-dateutil',
        'pygeocodio',
        'python-configuration',
        'pyyaml',
        'python-dateutil',
    ]
)
