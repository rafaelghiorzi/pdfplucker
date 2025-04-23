import os
import gc
import json
import fitz
import time
import psutil
import multiprocessing
import logging
from pathlib import Path
from pdfplucker.utils import format_result, link_subtitles, Data
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pdf_processing.log')
    ]
)
logger = logging.getLogger(__name__)

_converter_cache = {} # caching converters for memory efficiency

# Memory management functions
def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def force_gc():
    """Force garbage collection to free memory"""
    before_mem = get_memory_usage()
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except:
        pass  # not always available
    
    after_mem = get_memory_usage()
    freed = before_mem - after_mem
    if freed > 10:  # Only log if significant memory was freed
        logger.debug(f"Memory freed by GC: {freed:.2f} MB")

def check_pdf_size(filepath):
    """Check if PDF is too large to process safely"""
    try:
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        # Get available system memory
        available_memory = psutil.virtual_memory().available / (1024 * 1024)
        
        # Calculate size threshold based on available memory
        # We need approximately 10x the PDF size in memory
        size_threshold = min(100, available_memory / 10)
        
        if file_size_mb > size_threshold:
            logger.warning(f"PDF {os.path.basename(filepath)} is {file_size_mb:.2f}MB, which may cause memory issues")
            return False, file_size_mb
        return True, file_size_mb
    except Exception as e:
        logger.error(f"Error checking PDF size: {e}")
        return False, 0

def create_converter(device : str = 'CPU', num_threads : int = 4, ocr_lang: list = ['es', 'pt'], force_ocr: bool = False) -> DocumentConverter:
    ''' Create a DocumentConverter object with the pipeline options configured''' 

    # check low memory mode
    low_mem = os.environ.get('LOW_MEMORY', '0') == '1'
    memory_pct = psutil.virtual_memory().percent
    if memory_pct > 70:  # Dynamic low memory mode 
        low_mem = True
        logger.warning(f"System memory usage high ({memory_pct}%). Enforcing low memory mode.")

    # Using cache to avoid repeatedly loading the same model
    cache_key = f"{device}_{num_threads}_{'_'.join(ocr_lang)}_{force_ocr}"
    if cache_key in _converter_cache:
        return _converter_cache[cache_key]

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True 
    pipeline_options.ocr_options.lang = ocr_lang
    pipeline_options.generate_picture_images = True
    pipeline_options.do_picture_classification = True
    pipeline_options.do_formula_enrichment = True
    
    # Aggressive scaling for low memory mode
    pipeline_options.images_scale = 0.3 if low_mem else 0.5
    
    # Set page size limit in low memory mode
    if low_mem:
        pipeline_options.page_size_limit = 5000  # Limit page dimensions
    
    if force_ocr:
        # Rapid OCR or Easy OCr
        ocr_options = EasyOcrOptions(force_full_page_ocr=True, lang=ocr_lang)
        pipeline_options.ocr_options = ocr_options
    
    # Device acceleration
    device_type = AcceleratorDevice.CUDA if device.upper() == 'CUDA' else AcceleratorDevice.CPU if device.upper() == 'CPU' else AcceleratorDevice.AUTO if device.upper() == 'AUTO' else AcceleratorDevice.AUTO
    
    if low_mem and num_threads > 2:
        num_threads = max(2, num_threads // 2) # Reduce threads in low memory mode
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=device_type)

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    _converter_cache[cache_key] = converter
    return converter

def process_pdf(source: str, output: str, image_path: str | None, doc_converter: DocumentConverter, separate_folders: bool | None = False, markdown: bool = False, progress_bar = None) -> bool:
    """Function to process a single PDF file utilizing Docling"""

    low_memory_mode = os.environ.get('LOW_MEMORY', '0') == '1' or psutil.virtual_memory().percent > 70
    start_time = time.time()
    
    # Record initial memory
    initial_memory = get_memory_usage()
    logger.debug(f"Starting PDF processing with {initial_memory:.2f}MB memory")

    filename = os.path.basename(source)
    base_filename = os.path.splitext(filename)[0]
    
    # Check if PDF is too large to process safely
    safe_to_process, file_size_mb = check_pdf_size(source)
    if not safe_to_process:
        if file_size_mb > 50:  # Very large files
            logger.error(f"PDF too large to process safely: {filename} ({file_size_mb:.2f}MB)")
            return False

    try:
        if separate_folders:
            specific_folder = os.path.join(output, base_filename)
            result = os.path.join(specific_folder, f"{base_filename}.json")
            image_folder = os.path.join(specific_folder, "images")
            os.makedirs(specific_folder, exist_ok=True)
            os.makedirs(image_folder, exist_ok=True)
        else:
            result = os.path.join(output, f"{base_filename}.json")
            image_folder = image_path

        image_folder_path = Path(image_folder)

        logger.info(f"Processing: {filename}")

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
            if num_pages > 100 and low_memory_mode:
                logger.warning(f"Large document detected: {filename} has {num_pages} pages")
                if num_pages > 300:  # Very large documents
                    logger.error(f"Document too large to process in low memory mode: {filename}")
                    return False
                
            data["metadata"] = doc.metadata
            data["metadata"]["filename"] = filename
            data["metadata"]["pages"] = num_pages
            
            # Early cleanup
            doc.close()
        
        # Check memory before conversion
        if get_memory_usage() > initial_memory + 500:  # If we've already used 500MB before conversion
            force_gc()
        
        # Converting the source file to a Docling document - memory intensive part
        try:
            if file_size_mb > 20:  # For larger files, monitor memory during conversion
                logger.debug(f"Starting conversion of larger file: {filename}")
            
            # Progressive Processing for large files
            if num_pages > 100 and low_memory_mode:
                # For large files, adapt the options to be more memory efficient
                temp_converter = create_converter(
                    device='CPU',  # Force CPU for large files
                    num_threads=2,  # Limit threads
                    force_ocr=False  # Disable forced OCR for large files
                )
                conv: ConversionResult = temp_converter.convert(source)
                del temp_converter
            else:
                conv: ConversionResult = doc_converter.convert(source)
                
            # Monitor memory after conversion
            post_conv_memory = get_memory_usage()
            memory_used = post_conv_memory - initial_memory
            logger.debug(f"Conversion used {memory_used:.2f}MB for {filename}")
            
            format_result(conv, data, base_filename, image_folder_path)
            link_subtitles(data)
            
            # Free memory after formatting
            if low_memory_mode or memory_used > 200:
                del conv
                force_gc()

        except MemoryError:
            logger.error(f"Out of memory while converting {filename}")
            force_gc()
            return False
            
        # Save Markdown if asked - after clearing conversion memory
        if markdown:
            try:
                md_filename = result.replace('.json', '.md')
                conv.document.save_as_markdown(Path(md_filename), image_mode=ImageRefMode.EMBEDDED)
            except Exception as md_error:
                logger.error(f"Error saving markdown: {md_error}")
        
        # Save JSON
        with open(Path(result), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        processing_time = time.time() - start_time
        logger.info(f"Successfully processed {filename} in {processing_time:.2f}s")
        return True
    
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
        # Clean up resources regardless of outcome
        try:
            locals_copy = dict(locals())
            for var_name in ['conv', 'data']:
                if var_name in locals_copy:
                    del locals_copy[var_name]
                    
            force_gc()  # Aggressive garbage collection

            # Monitor memory and handle critical situations
            current_memory = get_memory_usage()
            memory_change = current_memory - initial_memory
            
            if memory_change > 100:  # If we're using 100MB more than when we started
                logger.warning(f"Memory usage grew by {memory_change:.2f}MB during processing {filename}")
                force_gc()
                
            if psutil.virtual_memory().percent > 85:
                logger.critical(f"System memory critically low! ({psutil.virtual_memory().percent}%)")
                force_gc()
                time.sleep(2)  # Give more time for memory to be reclaimed

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def _worker(source, output, image_path, doc_converter, separate_folders, markdown, queue):
    try:
        # Set process name for better monitoring
        multiprocessing.current_process().name = f"PDF-Worker-{os.path.basename(source)}"
        
        # Check available memory before starting
        if psutil.virtual_memory().percent > 90:
            logger.critical(f"Worker has insufficient memory to start processing {os.path.basename(source)}")
            queue.put((False, "Insufficient memory"))
            return
            
        success = process_pdf(source, output, image_path, doc_converter, separate_folders, markdown)
        queue.put((success, None))
    except Exception as e:
        logger.error(f"Worker error processing {os.path.basename(source)}: {e}")
        queue.put((False, str(e)))

def process_with_timeout(source: str, output: str, image_path: str, doc_converter: DocumentConverter, separate_folders: bool = False, timeout: int = 600, markdown:bool = False):
    """ Process a single PDF with safety timeout """

    filename = os.path.basename(source)
    
    # Adjust timeout based on file size
    _, file_size_mb = check_pdf_size(source)
    if file_size_mb > 10:
        # For larger files, allow more time (roughly 1 minute per 10MB, capped)
        adjusted_timeout = min(timeout * 2, timeout + int(file_size_mb * 6))
        logger.info(f"Adjusted timeout to {adjusted_timeout}s for {file_size_mb:.1f}MB file {filename}")
        timeout = adjusted_timeout

    if multiprocessing.get_start_method() != 'spawn':
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            # Already set, ignore
            pass

    queue = multiprocessing.Queue()

    process = multiprocessing.Process(
        target=_worker,
        args=(source, output, image_path, doc_converter, separate_folders, markdown, queue) 
        )
    
    process.start()
    process.join(timeout)

    if process.is_alive():
        logger.error(f"Timeout after {timeout}s! Killing process for {filename}")
        process.terminate()
        process.join(2)  # Give it 2 seconds to terminate
        if process.is_alive():
            process.kill()  # Force kill if still alive
        return False
    
    try:
        if not queue.empty():
            success, error = queue.get()
            if not success and error:
                logger.error(f"Process for {filename} failed: {error}")
            return success
        return False
    except Exception as e:
        logger.error(f"Error retrieving result for {filename}: {e}")
        return False

def get_skip_files(output_dir):
    """Get list of already processed files to skip when resuming"""
    skip_files = set()
    try:
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                if file.endswith('.json'):
                    skip_files.add(os.path.splitext(file)[0])
    except Exception as e:
        logger.error(f"Error getting skip files: {e}")
    return skip_files

def process_batch(source: str | Path, output: str, image_path: str | None, separate_folders: bool = False, max_workers: int = 4, timeout:int = 600, device: str = 'AUTO', markdown: bool = False, force_ocr: bool = False, skip_files: set = None, amount: int = None) -> dict:
    """ Process a batch of PDFs at a time in parallel """

    # Check for low memory mode
    system_memory = psutil.virtual_memory()
    available_memory_gb = system_memory.available / (1024**3)
    memory_critical = system_memory.percent > 80
    
    low_memory_mode = os.environ.get('LOW_MEMORY', '0') == '1' or memory_critical or available_memory_gb < 4
    
    if low_memory_mode:
        os.environ['LOW_MEMORY'] = '1'  # Set for child processes
        
    # Adjust workers based on available memory
    if available_memory_gb < 8:
        max_workers = max(1, min(max_workers, int(available_memory_gb)))
        logger.warning(f"Limited workers to {max_workers} due to available memory ({available_memory_gb:.1f}GB)")
    elif low_memory_mode and max_workers > 2:
        max_workers = max(1, max_workers // 2)  # Reduce workers but keep at least 1
        logger.warning(f"Low memory mode: Reduced worker count to {max_workers}")

    # path config
    if not separate_folders and image_path is None:
        image_path = f"{output}/images"
    
    # Create output directories
    os.makedirs(output, exist_ok=True)
    if not separate_folders:
        os.makedirs(image_path, exist_ok=True)

    # create the doc_converter
    doc_converter = create_converter(device=device, num_threads=max(2, max_workers//2), force_ocr=force_ocr)

    # Get list of already processed files
    if skip_files is None:
        skip_files = get_skip_files(output)
        if skip_files:
            logger.info(f"Found {len(skip_files)} already processed files to skip")

    # create the list of files
    pdf_files = []
    if Path(source).is_dir():
        # Sort files by size to process smaller files first
        file_info = []
        for file in os.listdir(source):
            if file.lower().endswith('.pdf'):
                file_path = os.path.join(source, file)
                file_stem = Path(file_path).stem
                # Skip files that have already been processed if resuming
                if skip_files and file_stem in skip_files:
                    continue
                try:
                    file_size = os.path.getsize(file_path)
                    file_info.append((file_path, file_size))
                except Exception as e:
                    logger.error(f"Error getting file size for {file}: {e}")
                    continue
                    
        # Sort by file size (smallest first)
        file_info.sort(key=lambda x: x[1])
        pdf_files = [info[0] for info in file_info]
    else:
        # Redundancy for safety
        if str(source).lower().endswith('.pdf'):
            pdf_files.append(str(source))

    if amount is not None and amount > 0:
        pdf_files = pdf_files[:amount]

    total_docs = len(pdf_files)
    logger.info(f"Total documents to process: {total_docs}")

    # create the metrics
    metrics = {
        'initial_time': time.time(),
        'elapsed_time': 0,
        'total_docs': total_docs,
        'processed_docs': 0,
        'failed_docs': 0,
        'timeout_docs': 0,
        'success_rate': 0,
        'memory_peak': 0,
        'fails': []
    }

    # Track peak memory usage
    memory_tracker = psutil.Process(os.getpid())
    
    # Process in smaller batches to manage memory better
    batch_size = max(1, max_workers * 2)  # Process 2x the number of workers at a time
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(pdf_files) + batch_size - 1)//batch_size}")
        
        # Check if we should pause before starting a new batch
        if i > 0 and psutil.virtual_memory().percent > 75:
            logger.warning("Memory pressure detected, pausing before next batch")
            force_gc()
            time.sleep(5)  # Pause to let memory settle
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    process_with_timeout,
                    pdf_file,
                    str(output),
                    str(image_path),
                    doc_converter,
                    separate_folders,
                    timeout,
                    markdown
                ): pdf_file for pdf_file in batch
            }

            for future in as_completed(futures):
                pdf_file = futures[future]
                try: 
                    success = future.result()
                    if success:
                        metrics['processed_docs'] += 1
                        logger.info(f"Successfully processed {os.path.basename(pdf_file)}")
                    else:
                        metrics['processed_docs'] += 1
                        metrics['failed_docs'] += 1
                        metrics['fails'].append({
                            'file': pdf_file,
                            'error': 'unknown'
                        })
                        logger.error(f"Failed to process {os.path.basename(pdf_file)}")
                except TimeoutError:
                    logger.error(f"Timeout reached for {os.path.basename(pdf_file)}")
                    metrics['timeout_docs'] += 1
                    metrics['fails'].append({
                        'file': pdf_file,
                        'error': "Timeout reached"
                    })
                except Exception as e:
                    logger.error(f"Error processing {os.path.basename(pdf_file)}: {e}")
                    metrics['failed_docs'] += 1
                    metrics['fails'].append({
                        'file': pdf_file,
                        'error': str(e)
                    })
                
                # Track memory usage periodically
                current_memory = memory_tracker.memory_info().rss / (1024 * 1024)
                metrics['memory_peak'] = max(metrics['memory_peak'], current_memory)
                
        # After each batch, force memory cleanup
        force_gc()
        
        # Save intermediate metrics
        if i + batch_size < len(pdf_files):
            intermediate_metrics = dict(metrics)
            intermediate_metrics['elapsed_time'] = time.time() - metrics['initial_time']
            intermediate_metrics['success_rate'] = ((metrics['processed_docs'] - metrics['failed_docs'] - metrics['timeout_docs']) / metrics['processed_docs']) * 100 if metrics['processed_docs'] > 0 else 0
            
            with open(os.path.join(output, 'intermediate_metrics.json'), 'w') as f:
                json.dump(intermediate_metrics, f, indent=2)

    # Clean up the converter
    _converter_cache.clear()
    del doc_converter
    force_gc()

    # Conclude metrics
    total_time = time.time() - metrics['initial_time']
    metrics['elapsed_time'] = total_time
    metrics['success_rate'] = ((total_docs - metrics['failed_docs'] - metrics['timeout_docs']) / total_docs) * 100 if total_docs > 0 else 0

    logger.info(f"Parsing process finished! Success rate: {metrics['success_rate']:.1f}%, Time: {total_time:.1f}s")
    
    # Save final metrics
    with open(os.path.join(output, 'final_metrics.json'), 'w') as f:
        json.dump(metrics, f, indent=2)
        
    return metrics