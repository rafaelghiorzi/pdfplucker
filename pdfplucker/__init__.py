"""
pdfplucker - a powerful wrapper for the Docling library
"""
# __init__.py

__version__ = "0.3.7"
__author__ = "Rafael Ghiorzi"
__email__ = "rafael.ghiorzi@gmail.com"

from pdfplucker.processor import process_batch, process_pdf, create_converter, process_with_timeout, _update_metrics
from pdfplucker.utils import format_result, link_subtitles
from pdfplucker.core import pdfplucker

__all__ = [
    "process_with_timeout",
    "_update_metrics",
    "process_batch",
    "process_pdf",
    "create_converter",
    "format_result",
    "link_subtitles",
    "pdfplucker",
]