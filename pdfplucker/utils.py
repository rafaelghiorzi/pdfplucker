# utils.py

from docling.datamodel.document import ConversionResult
from docling_core.types.doc import (
    PictureItem,
    TableItem,
    TextItem,
    DocItemLabel,
)
from typing import TypedDict, List, Dict, Any
import warnings
import time
import sys
import threading

class AnimatedProgressBar:
    def __init__(self, desc="Processing", animation_chars="/-\\|"):
        self.desc = desc
        self.animation_chars = animation_chars
        self.running = False
        self.thread = None
        self.current = 0
        self.total = 0
        self.status = ""
    
    def start(self, total=None):
        self.running = True
        self.total = total
        self.current = 0
        self.thread = threading.Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()
    
    def update(self, n=1, status=""):
        self.current += n
        self.status = status
    
    def _animate(self):
        i = 0
        while self.running:
            if self.total:
                progress = min(self.current / self.total * 100, 100)
                sys.stdout.write(f"\r{self.desc}: [{self.animation_chars[i % len(self.animation_chars)]}] {progress:.1f}% {self.status}")
            else:
                sys.stdout.write(f"\r{self.desc}: [{self.animation_chars[i % len(self.animation_chars)]}] {self.status}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
    
    def finish(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        sys.stdout.write("\r" + " " * 80 + "\r")  # Clear the line
        sys.stdout.flush()

class Data(TypedDict):
    metadata: Dict[str, Any]
    sections: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    subtitles: List[Dict[str, Any]]

def format_result(conv: ConversionResult, data: Data, filename: str, image_path: str) -> None:
    ''' Uses the docling document to format a readable JSON result '''

    collecting = None
    counter = 0

    if len(list(conv.document.iterate_items())) > 100:
        progress = AnimatedProgressBar(desc=f"Formatting {filename}" )
        progress.start()
    else:
        progress = None

    for idx, (item, _) in enumerate(conv.document.iterate_items()):
        if progress and idx % 10 == 0:
            progress.update(1, status=f"Processing item {idx}")

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

    if progress:
        progress.finish()

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