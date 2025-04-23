import os
import gc
import json
import fitz
import time
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pdfplucker.utils import format_result, link_subtitles, Data
from concurrent.futures import as_completed, TimeoutError
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling_core.types.doc import ImageRefMode
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    EasyOcrOptions,
)

logging.basicConfig(
    level=logging.INFO,
    format = '%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pdfplucker_process.log')
    ]
)
logger = logging.getLogger(__name__)

def convert_paths_to_strings(obj):
    """Recursively convert all Path objects to strings in a nested structure"""
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_paths_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_paths_to_strings(item) for item in obj]
    else:
        return obj

def create_converter(device : str = 'CPU', num_threads : int = 4, ocr_lang: list = ['es', 'pt'], force_ocr: bool = False) -> DocumentConverter:
    ''' Create a DocumentConverter object with the pipeline options configured''' 
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = False
    # pipeline_options.table_structure_options.do_cell_matching = True 
    pipeline_options.ocr_options.lang = ocr_lang
    pipeline_options.generate_picture_images = True
    pipeline_options.do_picture_classification = True
    pipeline_options.do_formula_enrichment = True
    
    # Aggressive scaling for low memory mode
    pipeline_options.images_scale = 1
    
    if force_ocr:
        # Rapid OCR or Easy OCr
        ocr_options = EasyOcrOptions(force_full_page_ocr=True, lang=ocr_lang)
        pipeline_options.ocr_options = ocr_options
    
    # Device acceleration
    device_type = AcceleratorDevice.CUDA if device.upper() == 'CUDA' else AcceleratorDevice.CPU if device.upper() == 'CPU' else AcceleratorDevice.AUTO if device.upper() == 'AUTO' else AcceleratorDevice.AUTO
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=device_type)
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    return converter

def process_with_timeout(
    source: Path,
    output: Path,
    image_path: Path,
    doc_converter: DocumentConverter,
    separate_folders: bool = False,
    timeout: int = 600,
    markdown: bool = False
) -> bool:
    """ Process a single PDF with safety timeout """
    """ Returns True if successful, False otherwise """

    filename = os.path.basename(source)

    result = [False]

    def worker():
        try:
            result[0] = process_pdf(
                source,
                output,
                image_path,
                doc_converter,
                separate_folders,
                markdown
            )
        except Exception as e:
            logger.error(f"Worker error processing {filename}: {e}")
            result[0] = False

    thread = threading.Thread(target=worker)
    thread.daemon = True # Allow main thread to exit even if worker is running

    start_time = time.time()
    thread.start()

    thread.join(float(timeout))

    if thread.is_alive():
        logger.error(f"Timeout after {timeout}s! Killing process for {filename}")
        return False
    
    time_elapsed = time.time() - start_time
    if result[0]:
        logger.info(f"Successfully processed {filename} in {time_elapsed:.2f}s")
    else:
        logger.error(f"Failed to process {filename} in {time_elapsed:.2f}s")
    
    return result[0]

def process_pdf(
        source: Path,
        output: Path,
        image_path: Path | None,
        doc_converter: DocumentConverter,
        separate_folders: bool | None = False,
        markdown: bool = False,
) -> bool:
    """Function to process a single PDF file utilizing Docling"""

    conv = None
    start_time = time.time()
    filename = Path(os.path.basename(source))
    base_filename = Path(os.path.splitext(filename)[0])
    logger.debug(f"Starting PDF processing for {filename}")

    try:
        if separate_folders:
            specific_folder = Path(os.path.join(output, base_filename))
            result = Path(os.path.join(specific_folder, f"{base_filename}.json"))
            image_folder = Path(os.path.join(specific_folder, "images"))
            os.makedirs(specific_folder, exist_ok=True)
            os.makedirs(image_folder, exist_ok=True)
        else:
            result = Path(os.path.join(output, f"{base_filename}.json"))
            image_folder = Path(image_path)
    
        data: Data = {
            "metadata": {},
            "sections" : [],
            "images": [],
            "tables": [],
            "subtitles" : []
        }

        # Use PyMuPDF (fitz) for extracting metadata - lightweight operation
        with fitz.open(source) as doc:
            # Check number of pages for large documents
            num_pages = len(doc)
            if num_pages > 100:
                logger.warning(f"Large document detected: {filename} has {num_pages} pages")
            data["metadata"] = doc.metadata
            data["metadata"]["filename"] = filename
            data["metadata"]["pages"] = num_pages

        conv: ConversionResult = doc_converter.convert(source)
        format_result(conv, data, base_filename, image_folder)
        link_subtitles(data)

        # Save Markdown if asked - after clearing conversion memory
        if markdown:
            try:
                md_filename = Path(os.path.join(specific_folder, f"{base_filename}.md"))
                conv.document.save_as_markdown(md_filename, image_mode=ImageRefMode.EMBEDDED)
            except Exception as md_error:
                logger.error(f"Error saving markdown: {md_error}")

        # transform Paths into strings
        data = convert_paths_to_strings(data)

        with open(result, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        processing_time = time.time() - start_time
        logger.info(f"Successfully processed {filename} in {processing_time:.2f}s")
        return True

    except MemoryError:
        logger.error(f"Out of memory while converting {filename}")
        gc.collect()
        return False
    except (fitz.FileDataError, fitz.EmptyFileError) as e:
        logger.error(f"Failed to process {filename}: {e}")
        return False
    except IOError as e:      
        logger.error(f"I/O error while processing {filename}: {e}")
        return False
    except Exception as e:    
        import traceback
        logger.error(f"Error processing {filename}: {str(e)}\n{traceback.format_exc()}")
        return False
    
    finally:
        gc.collect()  # Aggressive garbage collection
        try:
            del conv
            del data
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def process_batch(
    source: Path,
    output: Path,
    image_path: Path | None,
    separate_folders: bool = False,
    max_workers: int = 4,
    timeout: int = 600,
    device: str = 'AUTO',
    markdown: bool = False,
    force_ocr: bool = False,
    amount: int = None,
) -> dict:
    """ Process a batch of PDFs at a time in parallel """

    if not separate_folders and image_path is None:
        image_path = Path(f"{output}/images")
    
    # Create output directories
    os.makedirs(output, exist_ok=True)
    if not separate_folders:
        os.makedirs(image_path, exist_ok=True)
    
    # create the doc_converter
    doc_converter = create_converter(device=device, num_threads=max_workers, force_ocr=force_ocr)

    pdf_files = []

    if source.is_dir():
        for file in os.listdir(source):
            if file.lower().endswith('.pdf'):
                file_path = Path(os.path.join(source, file))
                pdf_files.append(file_path)
    pdf_files = pdf_files[:amount] if amount and amount > 0 else pdf_files

    total = len(pdf_files)
    logger.info(f"Total documents to process: {total}")

    # create the metrics
    metrics = {
        'initial_time': time.time(),
        'elapsed_time': 0,
        'total_docs': total,
        'processed_docs': 0,
        'failed_docs': 0,
        'timeout_docs': 0,
        'success_rate': 0,
        'memory_peak': 0,
        'fails': []
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for pdf_file in pdf_files:
            future = executor.submit(
                process_with_timeout,
                pdf_file,
                output,
                image_path if image_path else None,
                doc_converter,
                separate_folders,
                timeout,
                markdown
            )
            futures[future] = pdf_file

        for future in as_completed(futures):
            pdf_file = futures[future]
            metrics['processed_docs'] += 1
            
            try:
                success = future.result()
                if not success:
                    metrics['failed_docs'] += 1
                    metrics['fails'].append({
                        'file': str(pdf_file),
                        'error': 'Processing error'
                    })
            except TimeoutError:
                logger.error(f"Timeout reached for {os.path.basename(str(pdf_file))}")
                metrics['timeout_docs'] += 1
                metrics['fails'].append({
                    'file': str(pdf_file),
                    'error': "Timeout reached"
                })
            except Exception as e:
                logger.error(f"Processing error for {os.path.basename(str(pdf_file))}: {e}")
                metrics['failed_docs'] += 1
                metrics['fails'].append({
                    'file': str(pdf_file),
                    'error': str(e)
                })

            gc.collect()

            if metrics['processed_docs'] % 5 == 0:
                # Save intermediate metrics every 5 files
                _update_metrics(metrics, output)

    # Finalize metrics
    del doc_converter
    gc.collect()
    _update_metrics(metrics, output, final=True)
    logger.info(f"Processing concluded, sucess rate: {metrics['success_rate']:.1f}%, total time: {metrics['elapsed_time']:.1f}s")

    return metrics

def _update_metrics(metrics: dict, output_dir: str, final: bool = False) -> None:
    """Atualiza e salva as métricas de processamento"""
    metrics['elapsed_time'] = time.time() - metrics['initial_time']

    # Convert Paths to string
    metrics = convert_paths_to_strings(metrics)

    processed = metrics['processed_docs']
    if processed > 0:
        metrics['success_rate'] = ((processed - metrics['failed_docs'] - metrics['timeout_docs']) / processed) * 100
    
    filename = 'final_metrics.json' if final else 'intermediate_metrics.json'
    with open(os.path.join(output_dir, filename), 'w') as f:
        json.dump(metrics, f, indent=2)

