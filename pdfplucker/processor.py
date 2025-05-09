# Version 1.1.0
import os
import gc
import json
import fitz
import time
import multiprocessing  # Changed back to multiprocessing
from pathlib import Path
from concurrent.futures import as_completed, TimeoutError
from pdfplucker.utils import format_results, get_safe_executor, logger, Data
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling_core.types.doc import ImageRefMode
from docling.exceptions import ConversionError
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
    EasyOcrOptions,
)
# from docling.datamodel.pipeline_options import granite_picture_description -> For a future trial

def update_error_log(
    filename: str,
    error: str,
    final: bool = False,
    temp_dir: str = None,
    metrics: dict = None,
    output_dir: str = None
) -> None:
    """
    Updates error logs in temporary files and optionally finalizes metrics.
    
    Args:
        filename: The name of the file that caused the error
        error: Error message or description
        final: If True, consolidates all errors into final metrics
        temp_dir: Directory for temporary error files (defaults to output_dir/temp)
        metrics: Metrics dictionary (required if final=True)
        output_dir: Directory for output files (required if final=True)
    """
    
    # Set default temp directory if not provided
    if temp_dir is None:
        if output_dir is None:
            temp_dir = "temp_errors"
        else:
            temp_dir = os.path.join(output_dir, "temp_errors")
    
    # Create temp directory if it doesn't exist
    os.makedirs(temp_dir, exist_ok=True)
    
    if not final:
        # Create a safe filename for the temp file
        safe_filename = Path(filename).stem
        error_file = os.path.join(temp_dir, f"error_{safe_filename}_{int(time.time())}.json")
        
        # Write error information to temp file
        error_data = {
            "file": filename,
            "error": error,
            "timestamp": time.time()
        }
        
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)
            
    else:
        # Final mode - consolidate all errors and update metrics
        if metrics is None or output_dir is None:
            raise ValueError("Metrics and output_dir must be provided when final=True")
        
        # Initialize fails key if it doesn't exist
        if 'fails' not in metrics:
            metrics['fails'] = []
        
        # Get all error files
        error_files = [f for f in os.listdir(temp_dir) if f.startswith("error_")]
        
        # Read all error files and collect data
        all_errors = []
        for error_file in error_files:
            try:
                with open(os.path.join(temp_dir, error_file), 'r', encoding='utf-8') as f:
                    error_data = json.load(f)
                    all_errors.append({
                        'file': error_data.get('file', 'unknown'),
                        'error': error_data.get('error', 'Unknown error')
                    })
            except Exception as e:
                print(f"Error reading error file {error_file}: {e}")
        
        # Add all errors to metrics (without overwriting existing ones)
        metrics['fails'] = metrics['fails'] + all_errors
        
        # Update failed_docs count to match the total number of unique failed files
        # Create a set of unique filenames that failed
        unique_failed_files = set(error['file'] for error in metrics['fails'])
        metrics['failed_docs'] = len(unique_failed_files)
        
        if 'success_rate' in metrics:
            # Recalculate success rate
            processed = metrics['processed_docs']
            if processed > 0:
                metrics['success_rate'] = ((processed - metrics['failed_docs']) / processed) * 100
        else:
            metrics['success_rate'] = 0

        # Write final metrics file
        metrics_file = os.path.join(output_dir, 'final_metrics.json')
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

        # delete temp directory and all files inside it
        try:
            for error_file in error_files:
                os.remove(os.path.join(temp_dir, error_file))
            os.rmdir(temp_dir)
        except Exception as e:
            print(f"Error deleting temp directory {temp_dir}: {e}")

def json_serializable(obj):
    """Função auxiliar para tornar objetos personalizados serializáveis em JSON."""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)

def create_converter(device : str = 'CPU', num_threads : int = 4, ocr_lang: list = ['es', 'pt'], force_ocr: bool = False) -> DocumentConverter:
    ''' Create a DocumentConverter object with the pipeline options configured''' 
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True 
    pipeline_options.ocr_options.lang = ocr_lang
    pipeline_options.generate_picture_images = True
    pipeline_options.do_picture_classification = True
    pipeline_options.do_formula_enrichment = True
    #pipeline_options.do_picture_description = True
    #pipeline_options.picture_description_options = (
    #    smolvlm_picture_description
    #) 
    #pipeline_options.picture_description_options.prompt = (
    #    "Descreva a imagem em 3 frases. Seja sucinto e preciso."
    #)

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

def _worker(source, output, image_path, doc_converter, separate_folders, markdown, queue: multiprocessing.Queue):
    try:
        result = process_pdf(
            source,
            output,
            image_path,
            doc_converter,
            separate_folders,
            markdown,
        )
        queue.put(result)
    except Exception as e:
        logger.error(f"Non treated error at _worker function: {e}")
        update_error_log(str(source), f"Non treated error at _worker: {e}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        queue.put(False)

def process_with_timeout(
    source: Path,
    output: Path,
    image_path: Path,
    doc_converter: DocumentConverter,
    separate_folders: bool = False,
    timeout: int = 600,
    markdown: bool = False,
) -> bool:
    """ Process a single PDF with safety timeout """
    """ Returns True if successful, False otherwise """

    if multiprocessing.get_start_method() != 'spawn':
        multiprocessing.set_start_method('spawn', force=True)

    queue = multiprocessing.Queue()
    
    filename = os.path.basename(source)
    logger.info(f"Starting processing for '{filename}'")

    process = multiprocessing.Process(
        target=_worker,
        args=(source, output, image_path, doc_converter, separate_folders, markdown, queue) 
    )
    
    start_time = time.time()
    process.start()
    process.join(timeout)

    if process.is_alive():
        logger.error(f"Timeout after {timeout}s! Killing process for '{filename}'")
        update_error_log(str(source), f"Timeout reached for '{filename}'", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        process.terminate()
        process.join()
        return False
    
    try:
        if not queue.empty():
            result = queue.get()
            time_elapsed = time.time() - start_time
            if result:
                logger.info(f"Successfully processed '{filename}' in {time_elapsed:.2f}s")
                return True
            else:
                return False
    except Exception as e:
        logger.error(f"Error retrieving result: {e}")
        update_error_log(str(source), f"Error retrieving results: {e}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        return False

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
            "pages" : [],
            "images": [],
            "tables": [],
            "captions" : []
        }

        # Use PyMuPDF (fitz) for extracting metadata - lightweight operation
        with fitz.open(source) as doc:
            raw_metadata = doc.metadata
            # Check number of pages for large documents
            num_pages = len(doc)
            if num_pages > 100:
                logger.warning(f"Large document detected: {filename} has {num_pages} pages")

            data["metadata"].update({
                "format": raw_metadata.get('format') or None,
                "title": raw_metadata.get('title') or None,
                "creationDate": raw_metadata.get('creationDate') or None,
                "modDate": raw_metadata.get("modDate") or None,
                "filename": filename,
                "pageAmount": len(doc) or None
            }) 

        conv: ConversionResult = doc_converter.convert(str(source)) # use str instead of Path

        success = format_results(conv, data, base_filename, image_folder)

        if not success:
            logger.error(f"Error while formatting results from '{filename}'")
            update_error_log(str(source), f"Error while formatting results from '{filename}'", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
            return False

        # Save Markdown if asked
        if markdown:
            try:
                if separate_folders:
                    md_filename = Path(os.path.join(specific_folder, f"{base_filename}.md"))
                    conv.document.save_as_markdown(md_filename, image_mode=ImageRefMode.EMBEDDED)
                else:
                    md_filename = Path(os.path.join(output, f"{base_filename}.md"))
                    conv.document.save_as_markdown(md_filename, image_mode=ImageRefMode.EMBEDDED)
            except Exception as md_error:
                logger.error(f"Error saving markdown: {md_error}")
                update_error_log(str(source), f"Failed to export markdown: {md_error}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
                return False

        with open(result, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False, default=json_serializable)

        return True

    except MemoryError:
        logger.error(f"Out of memory while converting '{filename}'")
        update_error_log(str(source), f"Out of memory while converting '{filename}'", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        return False
    except (fitz.FileDataError, fitz.EmptyFileError) as e:
        logger.error(f"Failed to process '{filename}': {e}")
        update_error_log(str(source), f"Failed to process '{filename}': {e}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        return False
    except IOError as e:      
        logger.error(f"I/O error while processing '{filename}': {e}")
        update_error_log(str(source), f"I/O error while processing '{filename}': {e}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        return False
    except ConversionError as e:
        logger.error(f"Conversion error for '{filename}': {e}")
        update_error_log(str(source), f"Conversion error for '{filename}': {e}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
        return False
    except Exception as e:    
        import traceback
        logger.error(f"Error processing '{filename}': {str(e)}\n{traceback.format_exc()}")
        update_error_log(str(source), f"Error processing '{filename}': {str(e)}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
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
        'success_rate': 0,
        'memory_peak': 0,
    }

    # Switch back to ProcessPoolExecutor
    with get_safe_executor(max_workers=max_workers) as executor:
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
                markdown,
            )
            futures[future] = pdf_file

        for future in as_completed(futures):
            pdf_file = futures[future]
            metrics['processed_docs'] += 1
            
            try:
                success = future.result()
                if not success:
                    metrics['failed_docs'] += 1
            except TimeoutError:
                logger.error(f"Timeout reached for '{os.path.basename(str(pdf_file))}'")
                metrics['failed_docs'] += 1
                update_error_log(str(source), f"Timeout error in ProcessPoolExecutor", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
            except Exception as e:
                logger.error(f"Processing error for '{os.path.basename(str(pdf_file))}': {e}")
                update_error_log(str(source), f"Processing error in ProcessPoolExecutor: {e}", final=False, temp_dir=os.path.join(output, "temp_errors"), metrics=None, output_dir=None)
                metrics['failed_docs'] += 1
            gc.collect()

            if metrics['processed_docs'] % 5 == 0:
                # Save intermediate metrics every 5 files
                _update_metrics(metrics, output)

        # Check for memory peak
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        metrics['memory_peak'] = f"{(memory_info.rss / (1024 * 1024)):.2f} MB"

    # Finalize metrics
    del doc_converter
    gc.collect()
    _update_metrics(metrics, output, final=True)
    logger.info(f"Processing concluded, sucess rate: {metrics['success_rate']:.2f}%, total time: {metrics['elapsed_time']:.1f}s")

    update_error_log("final", "Processing complete", final=True, temp_dir=os.path.join(output, "temp_errors"), metrics=metrics, output_dir=output)

    return metrics

def _update_metrics(metrics: dict, output_dir: str, final: bool = False) -> None:
    """Atualiza e salva as métricas de processamento"""
    metrics['elapsed_time'] = time.time() - metrics['initial_time']

    processed = metrics['processed_docs']
    if processed > 0:
        metrics['success_rate'] = ((processed - metrics['failed_docs']) / processed) * 100
    
    filename = 'final_metrics.json' if final else 'intermediate_metrics.json'
    with open(os.path.join(output_dir, filename), 'w') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False, default=json_serializable)
    logger.info(f"Metrics updated: {filename}")