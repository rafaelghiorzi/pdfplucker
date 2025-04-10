"""
PDF Processor - Ferramenta para extração e processamento de documentos PDF
"""

__version__ = "0.1.0"

from pdf_parser.processor import process_batch, process_pdf, create_converter
from pdf_parser.utils import ensure_path, list_pdf_files, save_metrics

__all__ = [
    "process_batch", 
    "process_pdf", 
    "create_converter",
    "ensure_path", 
    "list_pdf_files", 
    "save_metrics"
]