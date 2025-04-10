import sys
import argparse
import time
import json

from pathlib import Path
#from src.processor import process_batch, process_pdf, create_converter
#from src.utils import ensure_path

from processor import process_batch, process_pdf, create_converter

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

    parser.add_argument(
        '-d', '--device',
        choices=['CPU', 'CUDA', 'AUTO'],
        default='AUTO',
        help='Type of device for processing (CUDA, CPU or AUTO)'
    )

    parser.add_argument(
        '-m', '--markdown',
        action='store_true',
        help='Export the document in an aditional markdown file'
    )

    return parser

def validate_args(args: argparse.Namespace):
    '''This function check the many arguments needs'''

    # Checking for the source path
    source_path = Path(args.source)
    if not source_path.exists():
        return False, f"Source path not found: {args.source}"
    
    # Checking if source, as a directory, contains PDFs
    if source_path.is_dir():
        pdf_files = list(source_path.glob("*.pdf"))
        if not pdf_files:
            return False, f"No PDF files found: {args.source}"
        
    # Checkging if source, as a file, is a PDF
    elif not source_path.name.lower().endswith('.pdf'):
        return False, f"Source path is neither a PDF, nor a directory: {args.source}"
    
    # Check number of workers
    if args.workers < 1:
        return False, f"Number of workers must be greater than 0: {args.workers}"
    
    # Check timeout
    if args.timeout < 1:
        return False, f"Timeout must be greater than 0: {args.timeout}"
    
    # Check if output path is a directory, and create if necessary
    output_path = Path(args.output)
    if output_path.exists() and not output_path.is_dir():
        return False, f"Output path is not a directory: {args.output}"
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"\033[33mWarning: Output path doesn't existing, creating: {args.output}\033[0m")

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
    
    return True, None

def process_single_file(args: argparse.Namespace):
    '''Process a single PDF file and save the results'''
    source_path = Path(args.source)
    output_path = Path(args.output)

    if args.folder_separation:
        images_path = output_path / source_path.stem / 'images'
    elif args.images:
        images_path = Path(args.images)
    else:
        images_path = output_path / 'images'
    
    # Create the images path if it doesn't exist
    if not images_path.exists():
        images_path.mkdir(parents=True, exist_ok=True)
        print(f"\033[32mImages path created: {images_path}\033[0m")

    doc_converter = create_converter(
        device=args.device.upper(),
        num_threads=args.workers
    )

    start_time = time.time()
    success = process_pdf(
        str(source_path),
        str(output_path),
        str(images_path),
        doc_converter,
        args.folder_separation,
        args.markdown,
    )
    elapsed_time = time.time() - start_time
    if success:
        print(f"\033[32mProcessing completed successfully in {elapsed_time:.2f} seconds\033[0m")
        print("=" * 50)
        print(f"Output path: {output_path}")
        print(f"Images path: {images_path}")
    else:
        print(f"\033[31mProcessing failed\033[0m")
    return success

def main():
    '''Main CLI function'''
    parser = create_parser()
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

    # Print the main information
    print("=" * 50)
    print("\033[34mPDFPlucker CLI - Docling Wrapper\033[0m")
    print("=" * 50)
    print(f"Source path: {args.source}")
    print(f"Output path: {args.output}")
    print(f"Device type: {args.device}")
    print(f"Number of workers: {args.workers}")
    print(f"Timeout: {args.timeout} seconds")
    print(f"Save markdown: {'yes' if args.markdown else 'no'}")
    print(f"Folder separation: {'yes' if args.folder_separation else 'no'}")
    print(f"Images path: {args.images if args.images else 'not used'}")
    print("=" * 50)
    print("Starting...")

    # Start the processing
    try:
        if Path(args.source).is_file():
            # Process a single PDF file
            sucess =  process_single_file(args)
            sys.exit(0 if sucess else 1)
        else:
            metrics = process_batch(
                source=args.source,
                output=args.output,
                image_path=args.images,
                separate_folders=args.folder_separation,
                max_workers=args.workers,
                timeout=args.timeout,
                device=args.device.upper(),
                markdown=args.markdown,
            )

        # Save metrics to JSON file
        metrics_path = Path(args.output) / f"{Path(args.source).name}_metrics.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4, ensure_ascii=False)

        # Print the metrics
        print("=" * 50)
        print("\033[32mProcessing completed successfully\033[0m")
        print(f"\033[32mMetrics saved to: {metrics_path}\033[0m")      
        print("=" * 50)
        print(f"Total amount of files: {metrics['total_docs']}")
        print(f"Successfully processed: {metrics['processed_docs']}")
        print(f"Failed processes: {metrics['failed_docs'] + metrics['timeout_docs']}")
        print(f"Success rate: {metrics['success_rate']}")
        print(f"Total time elapsed: {metrics['elapsed_time']:.2f} seconds")
        print("=" * 50)
    
    except KeyboardInterrupt:
        print("\033[31mProcess interrupted by user\033[0m")
        sys.exit(1)
    except Exception as e:
        print(f"\033[31mAn error occurred: {e}\033[0m")
        sys.exit(1)

if __name__ == "__main__":
    main()