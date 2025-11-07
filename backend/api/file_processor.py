import csv
import io
from typing import Dict, List, Optional, Union

import easyocr
import fitz  # PyMuPDF
from fastapi import UploadFile
from PIL import Image
import numpy as _np

# Initialize EasyOCR reader once (lazy loading on first use)
_ocr_reader: Optional[easyocr.Reader] = None


def get_ocr_reader() -> easyocr.Reader:
	"""Get or initialize EasyOCR reader (lazy initialization)."""
	global _ocr_reader
	if _ocr_reader is None:
		# Initialize with English language support
		# This will download models on first use (~100MB)
		_ocr_reader = easyocr.Reader(['en'], gpu=False)
	return _ocr_reader


def is_csv_file(filename: str) -> bool:
	"""Check if file is CSV based on extension."""
	return filename.lower().endswith(('.csv',))


def parse_csv_bytes(content: bytes, filename: str) -> Dict[str, Union[List[Dict], str]]:
	"""Parse CSV bytes and return structured data."""
	try:
		# Try to decode as UTF-8, fallback to latin-1 if needed
		try:
			text = content.decode('utf-8')
		except UnicodeDecodeError:
			text = content.decode('latin-1')

		# Parse CSV
		csv_reader = csv.DictReader(io.StringIO(text))
		rows = list(csv_reader)

		return {
			"type": "csv",
			"data": rows,
			"row_count": len(rows),
			"columns": list(rows[0].keys()) if rows else [],
			"filename": filename,
		}
	except Exception as e:
		return {
			"type": "csv",
			"error": f"Failed to parse CSV: {str(e)}",
			"data": [],
			"filename": filename,
		}


def extract_text_with_ocr_bytes(content: bytes, filename: str) -> Dict[str, Union[str, List[str]]]:
	"""Extract text from image or PDF bytes using EasyOCR."""
	try:
		# Check if it's a PDF
		if filename and filename.lower().endswith('.pdf'):
			return extract_text_from_pdf(content, filename)

		# Otherwise, treat as image
		return extract_text_from_image(content, filename)
	except Exception as e:
		return {
			"type": "ocr",
			"error": f"OCR processing failed: {str(e)}",
			"text": ""
		}


def extract_text_from_pdf(pdf_bytes: bytes, filename: str) -> Dict[str, Union[str, List[str]]]:
	"""Extract text from PDF using PyMuPDF and EasyOCR."""
	try:
		# Open PDF with PyMuPDF
		pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
		
		extracted_texts = []
		reader = get_ocr_reader()
		
		for page_num in range(len(pdf_doc)):
			page = pdf_doc[page_num]
			
			# Try to extract text directly first (faster if PDF has text layer)
			text = page.get_text()
			
			# If no text found, convert page to image and use OCR
			if not text.strip():
				# Convert page to image
				mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR quality
				pix = page.get_pixmap(matrix=mat)
				img_bytes = pix.tobytes("png")
				
				# Use EasyOCR on the image
				image = Image.open(io.BytesIO(img_bytes))
				# convert PIL image to numpy array for EasyOCR
				img_arr = _np.array(image.convert('RGB'))
				results = reader.readtext(img_arr)
				
				# Combine all detected text
				text = "\n".join([result[1] for result in results])
			
			extracted_texts.append({
				"page": page_num + 1,
				"text": text.strip()
			})
		
		pdf_doc.close()
		
		# Combine all pages
		full_text = "\n\n".join([page["text"] for page in extracted_texts])
		
		return {
			"type": "ocr",
			"source": "pdf",
			"text": full_text,
			"pages": extracted_texts,
			"page_count": len(extracted_texts)
		}
	except Exception as e:
		return {
			"type": "ocr",
			"source": "pdf",
			"error": f"PDF OCR failed: {str(e)}",
			"text": ""
		}


def extract_text_from_image(image_bytes: bytes, filename: str) -> Dict[str, str]:
	"""Extract text from image using EasyOCR (pure Python, no system deps)."""
	try:
		# Open image with PIL
		image = Image.open(io.BytesIO(image_bytes))
		
		# Get OCR reader and perform OCR
		reader = get_ocr_reader()
		# convert to numpy array (EasyOCR expects an array)
		img_arr = _np.array(image.convert('RGB'))
		results = reader.readtext(img_arr)
		
		# Combine all detected text
		text = "\n".join([result[1] for result in results])
		
		return {
			"type": "ocr",
			"source": "image",
			"text": text.strip(),
			"format": image.format,
			"detections": len(results)  # Number of text regions detected
		}
	except Exception as e:
		return {
			"type": "ocr",
			"source": "image",
			"error": f"Image OCR failed: {str(e)}",
			"text": ""
		}


async def process_uploaded_file(file: UploadFile) -> Dict[str, Union[str, List, Dict]]:
	"""Main function to process uploaded file - CSV parsing or OCR."""
	if not file.filename:
		return {
			"error": "No filename provided",
			"filename": None
		}
	# Read the entire uploaded file once (async-safe)
	content = await file.read()
	# Reset UploadFile pointer for callers that expect to re-read
	try:
		await file.seek(0)
	except Exception:
		pass

	# Check if file is CSV
	if is_csv_file(file.filename):
		result = parse_csv_bytes(content, file.filename)
		return result

	# Use OCR for non-CSV files
	result = extract_text_with_ocr_bytes(content, file.filename)
	return result

# Backwards-compatible wrappers (if other code calls the old functions)
def parse_csv(file: UploadFile):
	# synchronous wrapper: read bytes then call parse_csv_bytes
	content = file.file.read()
	return parse_csv_bytes(content, file.filename)

def extract_text_with_ocr(file: UploadFile):
	content = file.file.read()
	return extract_text_with_ocr_bytes(content, file.filename)

