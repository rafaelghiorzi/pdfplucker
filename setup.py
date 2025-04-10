import os
from setuptools import setup, find_packages

# Read the contents of your README file
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

# Read requirements
with open("requirements.txt", encoding="utf-8") as f:
    requirements = f.read().strip().split("\n")

setup(
    name="pdfplucker",
    version="0.2.0",
    description="Docling wrapper for PDF parsing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="rafaelghiorzi",
    author_email="rafael.ghiorzi@gmail.com",
    url="https://github.com/rafaelghiorzi/pdfplucker",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Natural Language :: English"
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "pdfplucker=pdfplucker.cli:main",
        ],
    },
)