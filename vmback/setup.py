#!/usr/bin/env python3
"""
Setup script for vmback
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text() if readme_file.exists() else ''

setup(
    name='vmback',
    version='2.2.3',
    description='XCP-ng Virtual Machine Backup Utility',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/vmback',
    packages=find_packages(),
    install_requires=[
        'XenAPI>=1.2',
        'PyYAML>=6.0',
        'python-dotenv>=1.0.0',
        'prettytable>=3.0.0',
    ],
    entry_points={
        'console_scripts': [
            'vmback=vmback.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: System :: Archiving :: Backup',
    ],
    python_requires='>=3.8',
)
