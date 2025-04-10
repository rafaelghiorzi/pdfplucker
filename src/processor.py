import os
import gc
import json
import fitz
import time
import multiprocessing
from pathlib import Path
from utils import format_result, link_subtitles, Data
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling_core.types.doc import ImageRefMode
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
)

def create_converter(device : str = 'CPU', num_threads : int = 4, ocr_lang: list = ['es']) -> DocumentConverter:
    ''' Create a DocumentConverter object with the pipeline options configured''' 

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True 
    pipeline_options.ocr_options.lang = ocr_lang
    pipeline_options.generate_picture_images = True
    # pipeline_options.generate_table_images = True in case is useful in the future
    pipeline_options.images_scale = 2.0
    # Device acceleration
    device_type = AcceleratorDevice.CUDA if device.upper() == 'CUDA' else AcceleratorDevice.CPU if device.upper() == 'CPU' else AcceleratorDevice.AUTO if device.upper() == 'AUTO' else AcceleratorDevice.AUTO
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=device_type)

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

def process_pdf(source: str, output: str, image_path: str | None, doc_converter: DocumentConverter, separate_folders: bool | None = False, markdown: bool = False) -> bool:
    """Function to process a single PDF file utilizing Docling"""

    filename = os.path.basename(source)
    base_filename = os.path.splitext(filename)[0]

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

        print(f"\033[33mProcessing: {filename}\033[0m")

        data: Data = {
            "metadata": {},
            "sections" : [],
            "images": [],
            "tables": [],
            "subtitles" : []
        }

        with fitz.open(source) as doc:
            data["metadata"] = doc.metadata
            data["metadata"]["filename"] = filename

        # Converting the source file to a Docling document
        conv: ConversionResult = doc_converter.convert(source)
        format_result(conv, data, base_filename, image_folder_path)
        link_subtitles(data)

        # Save Markdown if asked
        if markdown:
            md_filename = result.replace('.json', '.md')
            conv.document.save_as_markdown(md_filename, image_mode=ImageRefMode.EMBEDDED)
        
        # Save JSON
        with open(result, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return True
    
    except (fitz.FileDataError, fitz.EmptyFileError) as e:
        print(f"\033[31mFailed to process {filename}: {e}\033[0m")
        return False
    except IOError as e:
        print(f"\033[31mI/O error while processing: {e}\033[0m")
        return False
    except Exception as e:
        print(f"\033[31mAn error has occurred: {e}\033[0m") 
        return False
    
    finally:
        try:
            if 'conv' in locals():
                del conv
            if 'data' in locals():
                del data
            gc.collect()
        except Exception as e:
            print(f"\033[31mAn error has occurred while trying to free memory: {e}\033[0m")

def _worker(source, output, image_path, doc_converter, separate_folders, markdown, queue):
    try:
        success = process_pdf(source, output, image_path, doc_converter, separate_folders, markdown)
        queue.put(success)
    except Exception as e:
        print(f"\033[31mNon treated error at _worker: {e}\033[0m")
        queue.put(False)

def process_with_timeout(source: str, output: str, image_path: str, doc_converter: DocumentConverter, separate_folders: bool = False, timeout: int = 600, markdown:bool = False):
    """ Process a single PDF with safety timeout """

    if multiprocessing.get_start_method() != 'spawn':
        multiprocessing.set_start_method('spawn', force=True)

    queue = multiprocessing.Queue()

    process = multiprocessing.Process(
        target=_worker,
        args=(source, output, image_path, doc_converter, separate_folders, markdown, queue) 
        )
    
    process.start()
    process.join(timeout)

    if process.is_alive():
        filename = os.path.basename(source)
        print(f"\033[31mTimeout after {timeout}s! Killing process for {filename}\033[0m")
        process.terminate()
        process.join()
        return False
    
    try:
        if not queue.empty():
            return queue.get()
        return False
    except Exception:
        return False

def process_batch(source: str | Path, output: str, image_path: str | None, separate_folders: bool = False, max_workers: int = 4, timeout:int = 600, device: str = 'AUTO', markdown: bool = False) -> dict:
    """ Process a batch of PDFs at a time in paralel """

    source = Path(source)
    output = Path(output)

    # path config
    if not separate_folders and image_path is None:
        image_path = output / "images"
    elif image_path is not None:
        image_path = Path(image_path)

    # create the doc_converter
    doc_converter = create_converter(device=device, num_threads=max_workers)

    # create the list of files
    pdf_files = []
    if source.is_dir():
        for file in os.listdir(source):
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(source, file))
    else:
        # Redundancy for safety
        if source.suffix.lower() == '.pdf':
            pdf_files.append(str(source))

    total_docs = len(pdf_files)
    print(f"\033[33mTotal amount of documents to be processed: {total_docs}\033[0m")

    # create the metrics
    metrics = {
        'initial_time' : time.time(),
        'elapsed_time': 0,
        'total_docs' : total_docs,
        'processed_docs': 0,
        'failed_docs': 0,
        'timeout_docs': 0,
        'success_rate' : 0.1,
        'fails': []
    }

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures  = {
            executor.submit(
                process_with_timeout,
                pdf_file,
                str(output),
                str(image_path),
                doc_converter,
                separate_folders,
                timeout,
                markdown
            ) : pdf_file for pdf_file in pdf_files
        }

        for future in as_completed(futures):
            pdf_file = futures[future]
            try: 
                success = future.result()
                if success:
                    metrics['processed_docs'] += 1
                    print(f"\033[32mSuccessfuly processed {os.path.basename(pdf_file)}\033[0m")
                else:
                    metrics['processed_docs'] += 1
                    metrics['failed_docs'] += 1
                    metrics['fails'].append({
                        'file' : pdf_file,
                        'error': 'unknown'
                    })
                    print(f"\033[31m{pdf_file} failed\033[0m")
            except TimeoutError:
                print(f"\033[31m{os.path.basename(pdf_file)} reached time limit! Killing process\033[0m")
                metrics['timeout_docs'] += 1
                metrics['fails'].append({
                    'file' : pdf_file,
                    'error': "Timeout reached"
                })

            except Exception as e:
                print(f"\033[31mAn error has occurred while processing {os.path.basename(pdf_file)}: {e}\033[0m")
                metrics['failed_docs'] += 1
                metrics['fails'].append({
                    'file' : pdf_file,
                    'error': str(e)
                })

    # Conclude metrics
    total_time = time.time() - metrics['initial_time']
    metrics['elapsed_time'] = total_time
    metrics['success_rate'] = (metrics['failed_docs'] + metrics['timeout_docs']) / total_docs * 100

    print(f"\033[32mParsing process has finished!\033[0m")
    return metrics