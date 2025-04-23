"""
pdfplucker - a powerful wrapper for the Docling library
"""
# __init__.py

__version__ = "0.3.7"
__author__ = "Rafael Ghiorzi"
__email__ = "rafael.ghiorzi@gmail.com"

from pdfplucker.processor import process_batch, process_pdf, create_converter
from pdfplucker.utils import format_result, link_subtitles
from pdfplucker.core import pdfplucker

__all__ = [
    "process_batch",
    "process_pdf",
    "create_converter",
    "format_result",
    "link_subtitles",
    "pdfplucker",
]