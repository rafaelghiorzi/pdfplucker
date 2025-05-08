"""
pdfplucker - a powerful wrapper for the Docling library
"""
# __init__.py
from pdfplucker.processor import process_batch, process_pdf, create_converter, process_with_timeout, _update_metrics
from pdfplucker.utils import format_results, setup_logging, get_safe_executor
from pdfplucker.core import pdfplucker

__all__ = [
    "setup_logging",
    "get_safe_executor",
    "process_with_timeout",
    "_update_metrics",
    "process_batch",
    "process_pdf",
    "create_converter",
    "format_results",   
    "pdfplucker",
]