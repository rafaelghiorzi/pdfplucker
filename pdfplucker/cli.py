# CLI.py
import os
import sys
import argparse
import time
import torch
import psutil
from pathlib import Path
from pdfplucker.core import pdfplucker

def create_parser():
    '''
    Create the argument parser for the command line interface.
    '''

    parser = argparse.ArgumentParser(
        description='Docling wrapper for extracting PDF information.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Arguments
    parser.add_argument(
        '-s', '--source',
        help='Path to the PDF files (directory or just a single file)'
    )

    parser.add_argument(
        '-o', '--output',
        help='Path to save the processed information',
        default='./results'
    )

    parser.add_argument(
        '-f', '--folder-separation',
        action='store_true',
        help='Create separate folders for each PDF'
    )

    parser.add_argument(
        '-i', '--images',
        help='Path to save the extracted images (ignore if --folder-separation is active)'
    )

    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=600, # 10 minutes
        help='Time limit in seconds for processing each PDF'
    )

    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        help='Number of paralels processes (threads)'
    )

    # For forcing ocr use
    parser.add_argument(
        '-ocr', '--force-ocr',
        action='store_true',
        help='Force OCR even if the PDF is not scanned'
    )

    parser.add_argument(
        '-d', '--device',
        choices=['CPU', 'CUDA', 'AUTO', 'cpu', 'cuda', 'auto'],
        type=str,
        default='AUTO',
        help='Type of device for processing (CUDA, CPU or AUTO)'
    )

    parser.add_argument(
        '-m', '--markdown',
        action='store_true',
        help='Export the document in an aditional markdown file'
    )

    parser.add_argument(
        '-a', '--amount',
        type=int,
        default=0,
        help='Amount of files to process'
    )

    return parser

def validate_args(args: argparse.Namespace):
    '''This function check the many arguments needs'''

    # Checking for the source path
    source_path = Path(args.source)
    if not source_path.exists():
        return False, f"Source path not found: {args.source}"
    
    # Checking if source, as a directory, contains PDFs
    if Path(source_path).is_dir():
        pdf_files = list(source_path.glob("*.pdf"))
        if not pdf_files:
            return False, f"No PDF files found: {args.source}"
        
    # Checkging if source, as a file, is a PDF
    elif not source_path.name.lower().endswith('.pdf'):
        return False, f"Source path is neither a PDF, nor a directory: {args.source}"
    
    # Check number of workers
    if args.workers < 1:
        return False, f"Number of workers must be greater than 0: {args.workers}"
    
    # Optimize amount of processors
    cpu_count = psutil.cpu_count(logical=False) or 4
    if args.workers > cpu_count + 1:
        print(f"\033[33mWarning: Number of workers is greater than available CPU cores ({cpu_count}). Using {args.workers} instead.\033[0m")
        print(f"\033[33mConsider using {cpu_count} workers instead.\033[0m")
    
    # Check timeout
    if args.timeout < 1:
        return False, f"Timeout must be greater than 0: {args.timeout}"
    
    # Check if output path is a directory, and create if necessary
    output_path = Path(args.output)
    if output_path.exists() and not output_path.is_dir():
        return False, f"Output path is not a directory: {args.output}"
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"\033[33mWarning: Output path doesn't exist, creating at source directory: {args.output}\033[0m")

    # Check if images path is a directory, and create if necessary
    if args.images:
        images_path = Path(args.images)
        if images_path.exists() and not images_path.is_dir():
            return False, f"Images path is not a directory: {args.images}"
        if not images_path.exists():
            images_path.mkdir(parents=True, exist_ok=True)
            print(f"\033[32mImages path created: {args.images}\033[0m")
    
    # Check if the user wants to use folder separation and images path at the same time
    if args.folder_separation and args.images:
        return False, "Folder separation and images path cannot be used at the same time."
    
    # Check, if not using folder separation, if image_path is set, and create if necessary
    if not args.folder_separation and not args.images:
        print("\033[33mWarning: Images path not set. Using default path.\033[0m")
        images_path = output_path / 'images'
        if not images_path.exists():
            images_path.mkdir(parents=True, exist_ok=True)

    if not args.folder_separation and args.images:
        if not images_path.exists():
            images_path.mkdir(parents=True, exist_ok=True)
            print(f"\033[33mImages path created: {args.images}\033[0m")

    if args.device.upper() == 'CUDA':
        try:
            if not torch.cuda.is_available():
                return False, "CUDA is not available on this device. Please use CPU or AUTO."
        except Exception as e:
            print(f"\033[33mWarning: Error checking CUDA availability: {e}\033[0m")
            args.device = 'CPU'
            print("\033[33mFalling back to CPU processing\033[0m")

    mem = psutil.virtual_memory()
    if mem.percent > 80:
        print("\033[33mWarning: Memory usage is high. Consider closing other applications.\033[0m")
        print
    
    return True, None

def process_single_file(args: argparse.Namespace):
    '''Process a single PDF file and save the results'''
    source_path = args.source
    output_path = args.output

    if args.folder_separation:
        # Get the filename without extension to use as folder name
        base_filename = os.path.splitext(os.path.basename(source_path))[0]
        pdf_folder = os.path.join(output_path, base_filename)
        images_path = os.path.join(pdf_folder, "images")
        
        # Create both parent directory and images directory
        os.makedirs(pdf_folder, exist_ok=True)
        os.makedirs(images_path, exist_ok=True)
        print(f"\033[32mCreated folder: {pdf_folder}\033[0m")
    else:
        images_path = args.images if args.images else os.path.join(output_path, "images")
        os.makedirs(images_path, exist_ok=True)

    start_time = time.time()
    success = pdfplucker(
        source=source_path,
        output=output_path,
        folder_separation=args.folder_separation,
        images=images_path,
        timeout=args.timeout,
        workers=args.workers,
        force_ocr=args.force_ocr,
        device=args.device,
        markdown=args.markdown,
    )

    elapsed_time = time.time() - start_time
    if success:
        print(f"\033[32mProcessing completed successfully in {elapsed_time:.2f} seconds\033[0m")
        print("=" * 50)
        print(f"Output path: {output_path}")
        print(f"Images path: {images_path}")

        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        print(f"Memory usage: {memory_mb:.2f} MB")
    else:
        print(f"\033[31mProcessing failed\033[0m")
    return success

def main():
    '''Main CLI function'''
    parser = create_parser()

    if len(sys.argv) == 1:
        print("\033[34mPdfPlucker CLI - Docling Wrapper\033[0m")
        print("A tool for extracting information from PDF files.")
        print("Use the `--help` flag to see available options.")
        sys.exit(0)

    args = parser.parse_args()
    # Format the arguments
    for arg_name, arg_value in vars(args).items():
        if isinstance(arg_value, str):
            vars(args)[arg_name] = arg_value.replace('\\', '/') # For Windows compatibility
    # Validate the arguments
    valid_args, error = validate_args(args)
    if not valid_args:
        print(f"\033[91mError: {error}\033[0m")
        sys.exit(1)

    # Start the processing
    try:
        if Path(args.source).is_file():
            # Process a single PDF file
            sucess = process_single_file(args)
            sys.exit(0 if sucess else 1)
        else:
            metrics = pdfplucker(
                source=args.source,
                output=args.output,
                folder_separation=args.folder_separation,
                images=args.images,
                timeout=args.timeout,
                workers=args.workers,
                force_ocr=args.force_ocr,
                device=args.device.upper(),
                markdown=args.markdown,
                amount=args.amount if args.amount > 0 else 0,
            )

        # Print the metrics
        print("=" * 50)
        print("\033[32mProcessing completed successfully\033[0m")
        print(f"\033[32mMetrics in output path as final_metrics.json\033[0m")      
        print("=" * 50)
        print(f"Total amount of files: {metrics['total_docs']}")
        print(f"Successfully processed: {metrics['processed_docs']}")
        print(f"Failed processes: {metrics['failed_docs']}")
        print(f"Success rate: {metrics['success_rate']}")
        print(f"Total time elapsed: {metrics['elapsed_time']:.2f} seconds")
        print("=" * 50)

        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        print(f"Memory usage: {memory_mb:.2f} MB")
        print("=" * 50)
    
    except KeyboardInterrupt:
        print("\033[31mProcess interrupted by user\033[0m")
        sys.exit(1)
    except Exception as e:
        print(f"\033[31mAn error occurred: {e}\033[0m")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()