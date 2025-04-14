from docling.datamodel.document import ConversionResult
from docling_core.types.doc import (
    PictureItem,
    TableItem,
    TextItem,
    DocItemLabel,
)
from typing import TypedDict, List, Dict, Any

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

    for item, _, in conv.document.iterate_items():
        if isinstance(item, TextItem):
            if item.label == DocItemLabel.SECTION_HEADER:
                if collecting is not None:
                    data['sections'].append(collecting)
                collecting = {'title': item.text, 'text': ''}
            else:
                if collecting is not None:
                    collecting['text'] += '\n' + item.text if collecting['text'] else item.text
        elif isinstance(item, TableItem):
            table = item.export_to_dataframe()
            data['tables'].append({
                'self_ref' : item.self_ref,
                'subtitle' : '',
                'table' : table.to_dict()
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

def link_subtitles(data: Data) -> None:
    ''' 
    Try associating subtitles with images or tables
    based on refs saved on the Docling document
    '''
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
    
    del subtitles, tables, images