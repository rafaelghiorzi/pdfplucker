"""
pdfplucker - a powerful wrapper for the Docling library
"""

__version__ = "0.2.4"

from src.processor import process_batch, process_pdf, create_converter
from src.utils import format_result, link_subtitles
__all__ = [
    "process_batch",
    "process_pdf",
    "create_converter",
    "format_result",
    "link_subtitles"
]