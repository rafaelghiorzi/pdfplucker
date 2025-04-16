"""
pdfplucker - a powerful wrapper for the Docling library
"""
# __init__.py

__version__ = "0.3.7"
__author__ = "Rafael Ghiorzi"
__email__ = "rafael.ghiorzi@gmail.com"

from processor import process_batch, process_pdf, create_converter
from utils import format_result, link_subtitles

__all__ = [
    "process_batch",
    "process_pdf",
    "create_converter",
    "format_result",
    "link_subtitles"
]