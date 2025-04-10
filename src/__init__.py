"""
pdfplucker - Ferramenta para extração e processamento de documentos PDF
"""

__version__ = "0.2.0"

from src.processor import process_batch, process_pdf, create_converter
from src.utils import ensure_path
__all__ = [
    "process_batch", 
    "process_pdf", 
    "create_converter",
    "ensure_path",
]