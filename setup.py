import os
from setuptools import setup, find_packages

# Read the contents of your README file
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

# Read requirements
with open("requirements.txt", encoding="utf-8") as f:
    requirements = f.read().strip().split("\n")

setup(
    name="pdf_parser",
    version="0.1.1",
    description="Extrator e processador de documentos PDF utilizando Docling",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Rafael Dias Ghiorzi",
    author_email="rafael.ghiorzi@gmail.com",
    url="https://github.com/rafaelghiorzi/pdf_parser",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Natural Language :: Portuguese (Brazilian)",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [
            "pdf-processor=pdf_parser.cli:main",
        ],
    },
)