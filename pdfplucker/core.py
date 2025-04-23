# pdfplucker/core.py
from pathlib import Path
from pdfplucker.processor import process_batch, process_pdf, create_converter

def pdfplucker(
    source: str | Path,
    output: str | Path ="./results",
    folder_separation: bool = False,
    images: str | Path | None = None,
    timeout: int = 600,
    workers: int = 4,
    force_ocr: bool = False,
    device: str = "AUTO",
    markdown: bool = False,
    amount: int = 0,
):
    """
    Process PDF files and extract information.
    
    Parameters:
    -----------
    source : str or Path
        Path to the PDF files (directory or just a single file)
    output : str or Path, default="./results"
        Path to save the processed information
    folder_separation : bool, default=False
        Create separate folders for each PDF
    images : str or Path, optional
        Path to save the extracted images (ignore if folder_separation is active)
    timeout : int, default=600
        Time limit in seconds for processing each PDF
    workers : int, default=4
        Number of parallel processes (threads)
    force_ocr : bool, default=False
        Force OCR even if the PDF is not scanned
    device : str, default="AUTO"
        Type of device for processing ("CUDA", "CPU" or "AUTO")
    markdown : bool, default=False
        Export the document in an additional markdown file
    amount : int, default=0
        Amount of files to process (0 for all)
    
    Returns:
    --------
    dict or bool
        If processing a batch, returns metrics dictionary
        If processing a single file, returns success status (bool)
    """
    
    source_path = Path(source)
    output_path = Path(output)
    image_path = Path(images) if images else None

    # Normalize paths for Windows compatibility
    #source_path = Path(str(source_path).replace('\\', '/'))
    #output_path = Path(str(output_path).replace('\\', '/'))
    #if image_path:
    #    image_path = Path(str(image_path).replace('\\', '/'))
    
    if source_path.is_file():
        # Process single PDF
        doc_converter = create_converter(
            device=device.upper(),
            num_threads=workers,
            force_ocr=force_ocr,
        )
        
        if folder_separation:
            images_path = output_path / source_path.stem / "images"
        else:
            images_path = image_path or output_path / "images"
        
        images_path.mkdir(parents=True, exist_ok=True)
        
        sucess = process_pdf(
            source_path,
            output_path,
            images_path,
            doc_converter,
            folder_separation,
            markdown,
        )
        return sucess
    else:
        # Process batch of PDFs
        return process_batch(
            source=source_path,
            output=output_path,
            image_path=image_path,
            separate_folders=folder_separation,
            max_workers=workers,
            timeout=timeout,
            device=device.upper(),
            markdown=markdown,
            force_ocr=force_ocr,
            amount=amount if amount > 0 else None,
        )