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
import logging
import os
import traceback

class Data(TypedDict):
    metadata: Dict[str, Any]
    pages: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    captions: List[Dict[str, Any]]

def format_results(conv: ConversionResult, data: Data, filename: str, image_path: str) -> bool:
    ''' Uses the docling document to format a readable JSON result '''

    counter = 0
    try:
        for idx, (item, _) in enumerate(conv.document.iterate_items()):
            if isinstance(item, TextItem):
                page = item.prov[0].page_no
                label = item.label
                text = item.text
                content =  None
                match label:
                    case DocItemLabel.SECTION_HEADER:
                        content = f"\n# {text}\n"
                    case DocItemLabel.FORMULA:
                        content = f" Equation: {text}\n"
                    case DocItemLabel.REFERENCE:
                        content = f"\nReference: {text}\n"
                    case DocItemLabel.LIST_ITEM:
                        content = f"\n- {text}\n"
                    case DocItemLabel.CAPTION:
                        content = f" _{text}_\n"
                        data['captions'].append({
                            'self_ref' : item.self_ref,
                            'cref' : item.parent.cref,
                            'text' : text
                        })
                    case DocItemLabel.FOOTNOTE:
                        content = f"\nFootnote: {text}\n"
                    case DocItemLabel.TITLE:
                        content = f"\n## {text}\n"
                    case DocItemLabel.TEXT:
                        content = f" {text}"
                    case _:
                        content = f" {text}"

                page_found = False
                for page_dict in data['pages']:
                    if page_dict['page_number'] == page:
                        page_found = True
                        if 'content' not in page_dict:
                            page_dict['content'] = ""
                        page_dict['content'] += content
                        break
                        
                if not page_found:
                    new_page = {'page_number': page, 'content': content}
                    data['pages'].append(new_page)
    
            elif isinstance(item, TableItem):
                table = item.export_to_markdown(doc=conv.document)
                self_ref = item.self_ref
                captions = item.captions
                references = item.references
                footnotes = item.footnotes
                page = item.prov[0].page_no
    
                page_found = False
                for page_dict in data['pages']:
                    if page_dict['page_number'] == page:
                        page_found = True
                        if 'content' not in page_dict:
                            page_dict['content'] = ""
                        page_dict['content'] += f" <{self_ref}>"
                if not page_found:
                    new_page = {'page_number': page, 'content': f" <{self_ref}>"}
                    data['pages'].append(new_page)
                data['tables'].append({
                    'self_ref' : self_ref,
                    'captions' : captions,
                    'caption' : "",
                    'references' : references,
                    'footnotes' : footnotes,
                    'page' : page, 
                    'table' : table
                })
    
            elif isinstance(item, PictureItem):
                self_ref = item.self_ref
                captions = item.captions
                references = item.references
                footnotes = item.footnotes
                page = item.prov[0].page_no
                classification = None
                confidence = None
                if item.annotations:
                    for annotation in item.annotations:
                        if annotation.kind == 'classification':
                            # Find the classification with the highest confidence
                            best_class = max(
                                annotation.predicted_classes,
                                key=lambda cls: cls.confidence
                            )
                            classification = best_class.class_name,
                            confidence = best_class.confidence
                            break
                image_filename = (image_path / f"{filename}_{counter}.png")
                placeholder = f"{filename}_{counter}.png"
                with image_filename.open('wb') as file:
                    item.get_image(conv.document).save(file, "PNG")
                data['images'].append({
                    'ref': placeholder,
                    'self_ref' : self_ref,
                    'captions' : captions,
                    'caption' : "",
                    'classification' : classification,
                    'confidence' : confidence,
                    'references' : references,
                    'footnotes' : footnotes,
                    'page' : page,
                })
                counter += 1
    
                page_found = False
                for page_dict in data['pages']:
                    if page_dict['page_number'] == page:
                        page_found = True
                        if 'content' not in page_dict:
                            page_dict['content'] = ""
                        page_dict['content'] += f" <{placeholder}>"
                if not page_found:
                    new_page = {'page_number': page, 'content': f" <{placeholder}>"}
                    data['pages'].append(new_page)


        caption_dict = {caption["cref"]: caption["text"] for caption in data.get("captions", [])}
    
        for image in data.get("images", []):
            self_ref = image.get("self_ref")
            if self_ref in caption_dict:
                caption_text = caption_dict[self_ref]
                if caption_text not in image.get("caption", ""):
                    image["caption"] += f"{caption_text} "
            image.pop('captions')

        for table in data.get("tables", []):
            self_ref = table.get("self_ref")
            if self_ref in caption_dict:
                caption_text = caption_dict[self_ref]
                if caption_text not in table.get("caption", ""):
                    table["caption"] += f"{caption_text} "
            table.pop('captions')

        data.pop('captions')
        
        return True
    except Exception as e:
        print(f"\033[33mError formatting result: {e}\033[0m")
        traceback.print_exc()
        return False

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
