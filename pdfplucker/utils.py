# utils.py
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from docling.datamodel.document import ConversionResult
from docling_core.types.doc import (
    PictureItem,
    TableItem,
    TextItem,
    DocItemLabel,
)
from typing import TypedDict, List, Dict, Any
import warnings
import logging
import os

class Data(TypedDict):
    metadata: Dict[str, Any]
    sections: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    subtitles: List[Dict[str, Any]]

def format_result(conv: ConversionResult, data: Data, filename: str, image_path: str) -> None:
    try:
        ''' Uses the docling document to format a readable JSON result '''

        collecting = None
        counter = 0

        for idx, (item, _) in enumerate(conv.document.iterate_items()):
            if isinstance(item, TextItem):
                if item.label == DocItemLabel.SECTION_HEADER:
                    if collecting is not None:
                        data['sections'].append(collecting)
                    collecting = {'title': item.text, 'text': ''}
                elif item.label == DocItemLabel.FORMULA:
                    if collecting is not None:
                        collecting['text'] += '\n' + "Equation:" + item.text if collecting['text'] else item.text
                else:
                    if collecting is not None:
                        collecting['text'] += '\n' + item.text if collecting['text'] else item.text
            elif isinstance(item, TableItem):
                table = item.export_to_dataframe()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    table_dict = table.to_dict()
                data['tables'].append({
                    'self_ref' : item.self_ref,
                    'subtitle' : '',
                    'table' : table_dict
                })
            elif isinstance(item, PictureItem):
                classification = None
                if item.annotations:
                    for annotation in item.annotations:
                        if annotation.kind == 'classification':
                            # Find the classification with the highest confidence
                            best_class = max(
                                annotation.predicted_classes,
                                key=lambda cls: cls.confidence
                            )
                            classification = {
                                'class_name': best_class.class_name,
                                'confidence': best_class.confidence
                            }
                            break

                image_filename = (image_path  / f"{filename}_{counter}.png")
                with image_filename.open('wb') as f:
                    item.get_image(conv.document).save(f, "PNG")
                data['images'].append({
                    'ref': f"{filename}_{counter}.png",
                    'self_ref' : item.self_ref,
                    'classification' : classification,
                    'subtitle' : ''
                })
                counter += 1

        # Collecting the results after all iterations
        if collecting is not None:
            data['sections'].append(collecting)
        for text in conv.document.texts:
            if text.label == 'caption':
                data['subtitles'].append({
                    'ref' : text.parent.cref,
                    'text' : text.text
                })
    except Exception as e:
        print(f"\033[33mError formatting result: {e}\033[0m")

def link_subtitles(data: Data) -> None:
    ''' 
    Try associating subtitles with images or tables
    based on refs saved on the Docling document
    '''
    try:
        images = data.get('images', [])
        tables = data.get('tables', [])
        subtitles = data.get('subtitles', [])

        # iterate over all images and all subtitles
        for img in images:
            self_ref = img.get('self_ref')
            if self_ref is None:
                continue
            
            # For each image, try to find a ref equals to the image self ref
            for sub in subtitles[:]:
                ref = sub.get('ref')
                if self_ref == ref:
                    img['subtitle'] = sub.get('text', '')
                    img.pop('item', None)
                    # remove the subtitle to be sure
                    subtitles.remove(sub)
                    break 

        # iterate over all tables and the remaining subtitles
        for tab in tables:
            self_ref = tab.get('self_ref')
            if self_ref is None:
                continue

            # For each table, try to find a ref equals to the table self ref
            for sub in subtitles[:]:
                ref = sub.get('ref')
                if self_ref == ref:
                    tab['subtitle'] = sub.get('text', '')
                    subtitles.remove(sub)
                    break

        for sub in subtitles:
            data['images'].append({
                'ref': sub.get('ref'),
                'self_ref' : None,
                'subtitle' : sub.get('text', '')
            })

        data.pop('subtitles')
    except Exception as e:
        print(f"\033[33mError linking subtitles: {e}\033[0m]")
    finally:
        if 'subtitles' in locals():
            del subtitles
        if 'images' in locals():
            del images
        if 'tables' in locals():
            del tables

def get_safe_executor(max_workers=None):
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        # Method might already be set
        pass
        
    return ProcessPoolExecutor(max_workers=max_workers)

class ColorfulFormatter(logging.Formatter):
    COLOURS = {
        'DEBUG': '\033[94m',  # Blue
        'INFO': '\033[92m',   # Green
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',  # Red
        'CRITICAL': '\033[95m',  # Magenta
    }
    RESET = '\033[0m'  # Reset to default color

    def format(self, record):
        log_color = self.COLOURS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
   
        return super().format(record)

def setup_logging(level=logging.INFO):
    # Create formatters
    detailed_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    simple_formatter = ColorfulFormatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create file handlers
    log_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    pdfplucker_file = logging.FileHandler(os.path.join(log_dir, 'pdfplucker.log'))
    pdfplucker_file.setFormatter(detailed_formatter)
    
    # Create console handler
    console = logging.StreamHandler()
    console.setFormatter(simple_formatter)
    
    # Create a third-party log file for docling
    third_party_file = logging.FileHandler(os.path.join(log_dir, 'dependencies.log'))
    third_party_file.setFormatter(detailed_formatter)
    third_party_file.setLevel(logging.DEBUG)  # All levels
    
    # Configure the root logger (for third-party libraries)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # All levels
    
    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(third_party_file)
    
    # Configure your package's logger
    pdfplucker_logger = logging.getLogger('pdfplucker')
    pdfplucker_logger.setLevel(level)
    
    # Remove any existing handlers to avoid duplicates
    for handler in pdfplucker_logger.handlers[:]:
        pdfplucker_logger.removeHandler(handler)
    
    pdfplucker_logger.addHandler(pdfplucker_file)
    pdfplucker_logger.addHandler(console)
    
    # Make sure your logger doesn't propagate to root
    pdfplucker_logger.propagate = False
    
    return pdfplucker_logger

logger = setup_logging()
