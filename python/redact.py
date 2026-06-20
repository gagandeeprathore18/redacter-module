import os
import sys
import argparse

# Ensure local imports work correctly
python_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(python_dir)
sys.path.insert(0, python_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from docx_processor import process_docx
from pdf_processor import process_pdf
from pptx_processor import process_pptx
from image_processor import process_image

def main():
    parser = argparse.ArgumentParser(description="Document Drafting & Redaction Engine - Phase 1 (POC)")
    parser.add_argument("input_path", help="Path to the source document to redact")
    parser.add_argument("output_path", help="Path to save the redacted output document")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_path):
        print(f"Error: Input file '{args.input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    ext = os.path.splitext(args.input_path)[1].lower()
    
    print(f"Processing '{args.input_path}' with extension '{ext}'...")
    
    try:
        if ext == ".docx":
            process_docx(args.input_path, args.output_path)
        elif ext == ".pdf":
            process_pdf(args.input_path, args.output_path)
        elif ext == ".pptx":
            process_pptx(args.input_path, args.output_path)
        elif ext in (".jpg", ".jpeg", ".png"):
            process_image(args.input_path, args.output_path)
        else:
            print(f"Error: Unsupported file format '{ext}'. Supported formats: DOCX, PDF, PPTX, JPG, JPEG, PNG.", file=sys.stderr)
            sys.exit(1)
            
        print("Redaction completed successfully!")
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"Error during redaction: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
