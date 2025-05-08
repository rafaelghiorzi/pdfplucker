# PdfPlucker

[![PyPI version](https://badge.fury.io/py/pdfplucker.svg)](https://badge.fury.io/py/pdfplucker)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<div style="display: flex; justify-content: center; margin: 20px">
  <img src="logo.png" alt="PdfPlucker (AI generated)" width="300">
</div>

PdfPlucker is a powerful wrapper for the Docling library, specifically designed for batch processing PDF files. It provides users with fine-grained control over processing parameters and output configuration through a simple command-line interface.

## Features

- **Comprehensive Extraction**: Extract text, tables, and images from PDF files with high fidelity
- **Structured Outputs**: Get results in well-organized JSON and Markdown formats
- **High Performance**: Process multiple documents simultaneously with parallel processing
- **Hardware Acceleration**: Support for both CPU and CUDA for faster processing
- **Simple Interface**: Intuitive CLI commands for easy parameter control
- **Batch Processing**: Handle directories of PDFs effortlessly

## Installation

PdfPlucker requires Python 3.12 or higher and Torch 2.6.0 or higher. To install, simply run the following command:

```bash
pip install pdfplucker
```

_Note: For GPU support, you may need to install the PyTorch version that matches your CUDA version._
_Check your CUDA version with `nvidia-smi` and visit https://pytorch.org/get-started/locally/ for instructions_

Or install from source:

```bash
git clone https://github.com/ipeadata-lab/pdfplucker.git
cd pdfplucker
pip install -r requirements.txt
```

## Requirements

- Python 3.12+
- For CUDA support: An NVIDIA GPU with drivers up to date
- Additional dependencies are automatically installed with the package

## Basic Usage

PdfPlucker has a built-in CLI to run the processor. The basic command structure is:

```bash
pdfplucker --source /path/to/pdf
```

This will process the PDF file and save the results to `./results` by default.

## Command-line Options

| Option | Description |
|--------|-------------|
| `-s, --source` | Path to PDF files (directory or single file) |
| `-o, --output` | Path to save processed information (default: `./results`) |
| `-f, --folder-separation` | Create separate folders for each PDF |
| `-i, --images` | Path to save extracted images (ignored if `--folder-separation` is active) |
| `-t, --timeout` | Time limit in seconds for processing each PDF (default: 600) |
| `-w, --workers` | Number of parallel processes (default: 4) |
| `-d, --device` | Processing device: CPU, CUDA, or AUTO (default: AUTO) |
| `-m, --markdown` | Export the document in an additional markdown file |
| `-ocr, --force-ocr` | Force text recognition using ocr even with digital documents | 

### Markdown Output

When enabled with the `--markdown` flag, PdfPlucker will generate a readable Markdown file that includes:
- Formatted document text
- Tables rendered in Markdown syntax
- Embedded images with base64 encoding

### Force OCR option

Docling will extract text from natively digital PDFs. If you wish to force the use of OCR tools to scan the file text, run the command with the `--force-ocr` flag.

### Amount of workers

When processing large amounts of files, note that many workers might lead to RAM shortage and memory leaks, mainly when paired with forced ocr. Try balancing the amount of workers with the amount of available memory and power of your computer.

## Alternative function

Alternatively to the CLI, you can also the pdfplucker built-in function to integrate inside your code. The function structure is as follows:

```python
import pdfplucker

metrics = pdfplucker.pdfplucker(
    source: str | Path, # either directory of pdfs or a single pdf
    output: str | Path ="./results",
    folder_separation: bool = False,
    images: str | Path | None = None,
    timeout: int = 600,
    workers: int = 4,
    force_ocr: bool = False,
    device: str = "AUTO",
    markdown: bool = False,
    amount: int = 0,
)
```

This will either return _true_ or _false_ if source is a single PDF, or a metrics json that has the following example structure:

```json
{
    "initial_time": 1744817807.3165462,
    "elapsed_time": 84290.00611519814,
    "total_docs": 115,
    "processed_docs": 115,
    "failed_docs": 50,
    "timeout_docs": 0,
    "success_rate": 56.52173913043478,
    "fails": [
        {
            "file": "/path/to/failed_file.pdf",
            "error": "Type of error"
        },
    ]
}
```


## Examples

### Process a single PDF file:

```bash
pdfplucker --source document.pdf
```

### Process all PDFs in a directory:

```bash
pdfplucker --source ./documents/ --output ./extracted_data
```

### Create separate folders for each PDF and include markdown output:

```bash
pdfplucker --source ./documents/ --folder-separation --markdown
```

### Specify output location for extracted images:

```bash
pdfplucker --source document.pdf --images ./images
```

### Use CUDA for processing with 8 workers:

```bash
pdfplucker --source ./documents/ --device CUDA --workers 8
```

## Advanced Usage

For processing large batches of PDFs, you can use the folder separation option combined with multiple workers:

```bash
pdfplucker --source ./pdf_collection/ --folder-separation --workers 8 --timeout 300 --force-ocr
```

This will create a separate folder for each PDF, use 8 parallel processes, set a timeout of 5 minutes per PDF and force ocr usage for text recognition.

## Output Structure

PdfPlucker generates structured outputs in the following formats:

### Custom JSON Output

The JSON output contains:
- Document metadata,
- Extracted text divided into pages,
- Pages in markdown format, with externally referenced tables and images
- Table data with preserved structure,
- References to extracted images with preserved structure.

Example structure:
```json
{
    "metadata": {
        "format": "PDF 1.7",
        "title": null,
        "..." : "...",
        "modDate": "D:20240707100910Z",
        "filename": "sample.pdf",
        "pageAmount": 5
    },
    "pages": [
        {
            "page_number": 1,
            "content": " <sample_0.png>\n# Sample PDF text!\nIt comes in markdown format!"
        },
        {
          "other pages" : "..."
        },
        {
            "page_number": 5,
            "content": "<#/tables/0> This a referenced table and <sample_2.png> this is a referenced image"
        }
    ],
    "images": [
        {
            "ref": "sample_0.png",
            "self_ref": "#/pictures/0",
            "caption": "",
            "classification": [
                "logo"
            ],
            "confidence": 0.999339759349823,
            "references": [],
            "footnotes": [],
            "page": 1
        },
        {
          "..." : "..."
        },
        {
            "ref": "sample_2.png",
            "self_ref": "#/pictures/2",
            "caption": "",
            "classification": [
                "bar_chart"
            ],
            "confidence": 0.9979164004325867,
            "references": [],
            "footnotes": [],
            "page": 5
        }
    ],
    "tables": [
        {
            "self_ref": "#/tables/0",
            "caption": "",
            "references": [],
            "footnotes": [],
            "page": 3,
            "table": "The table comes in markdown format!"
        },
        {
          "..." : "..."
        }
    ]
}
```

## Troubleshooting

### Common Issues

- **MemoryError**: Try reducing the number of workers or processing larger PDFs individually
- **CUDA not detected**: Ensure you have compatible NVIDIA drivers installed and visible to Python
- **Timeout errors**: Increase the timeout value for complex or large documents
- **Missing images**: Check file permissions in the output directory

### Getting Help

If you encounter issues not covered here, please open an issue on GitHub with:
- The command you ran
- The error message
- Your system specifications (OS, Python version, etc.)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, please:

1. Check existing issues and pull requests
2. Fork the repository
3. Create a new branch for your feature
4. Add your changes
5. Submit a pull request

## Acknowledgments

- [Docling](https://github.com/docling-project/docling) for the core PDF processing capabilities
- All contributors and users of PdfPlucker
