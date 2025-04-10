# PdfPlucker

[![PyPI version](https://badge.fury.io/py/pdfplucker.svg)](https://badge.fury.io/py/pdfplucker)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PdfPlucker is a powerful wrapper for the Docling library, specifically designed for batch processing PDF files. It provides users with fine-grained control over processing parameters and output configuration through a simple command-line interface.

## Features

- **Comprehensive Extraction**: Extract text, tables, and images from PDF files with high fidelity
- **Structured Outputs**: Get results in well-organized JSON and Markdown formats
- **High Performance**: Process multiple documents simultaneously with parallel processing
- **Hardware Acceleration**: Support for both CPU and CUDA for faster processing
- **Simple Interface**: Intuitive CLI commands for easy parameter control
- **Batch Processing**: Handle directories of PDFs effortlessly

## Installation

PdfPlucker requires Python 3.9 or higher. To install, simply run the following command:

```bash
pip install pdfplucker
```

Or install from source:

```bash
git clone https://github.com/rafaelghiorzi/pdfplucker.git
cd pdfplucker
pip install -r requirements.txt
```

## Requirements

- Python 3.9+
- For CUDA support: NVIDIA GPU with CUDA drivers installed
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
pdfplucker --source ./pdf_collection/ --folder-separation --workers 8 --timeout 300
```

This will create a separate folder for each PDF, use 8 parallel processes, and set a timeout of 5 minutes per PDF.

## Output Structure

PdfPlucker generates structured outputs in the following formats:

### JSON Output

The JSON output contains:
- Document metadata (title, author, date, etc.)
- Extracted text divided into sections (title, text)
- Table data with structure preserved and subtitles, if they exist
- References to extracted images, with subtitles, if they exist

Example structure:
```json
{
    "metadata": {
        "format": "PDF 1.7",
        "title": "Microsoft Word - Sample Title",
        "..."
        "producer": "Microsoft: Print To PDF",
        "creationDate": "D:20250401144737-03'00'",
        "filename": "file.pdf"
    },
    "sections": [
        {
            "title": "Big Title!",
            "text": "Following text after title"
        },
    ],
    "images": [
      {
        "self_ref" : "#picture/1",
        "ref" : "path/to/image.png",
        "subtitle" : "possible subtitle"
      }
    ],
    "tables": [
      {
        "self_ref" : "#table/1",
        "subtitle" : "possible subtitle",
        "table" : {"table in dict format"}
      }
    ]
}
```

### Markdown Output

When enabled with the `--markdown` flag, PdfPlucker will generate a readable Markdown file that includes:
- Formatted document text
- Tables rendered in Markdown syntax
- Embedded images with base64 encoding

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

## Version History

- **0.1.5**: Initial test
- **0.1.6**: Correct JSON formatting
- **0.1.7**: Fixing modules versions and import
- **0.2.0**: Formatting terminal outputs

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