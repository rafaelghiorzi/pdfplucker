"""
pdfplucker - a powerful wrapper for the Docling library
"""

__version__ = "0.3.2"

from pdfplucker.processor import process_batch, process_pdf, create_converter
from pdfplucker.utils import format_result, link_subtitles

__all__ = [
    "process_batch",
    "process_pdf",
    "create_converter",
    "format_result",
    "link_subtitles"
]