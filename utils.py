
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import logging
from collections import defaultdict
import shutil

logger = logging.getLogger(__name__)

def find_raw_files(selected_dir: Path):
    raw_extensions = {
        '.cr2',
        '.cr3',
        '.nef',
        '.arw',
    }

    raw_files = []

    for root, dirs, files in os.walk(selected_dir):
        logger.critical(f"Root: {root} -> Dir: {dirs} -> Files: {files}")
        for file in files:
            if Path(file).suffix.lower() in raw_extensions:
                raw_files.append(Path(root)/file)

    return raw_files


def is_valid_xmp_file(xmp_file_path):
    """
    Check if an XMP file is valid and not a system/hidden file.
    Returns True if the file appears to be a valid XMP file.
    """
    # Skip macOS resource fork files and other hidden files
    if xmp_file_path.name.startswith('._') or xmp_file_path.name.startswith('.'):
        return False

    # Check if file is empty or too small to be valid XMP
    try:
        if xmp_file_path.stat().st_size < 10:
            return False
    except OSError:
        return False

    # Try to read the first few bytes to check for XML declaration
    try:
        with open(xmp_file_path, 'rb') as f:
            first_bytes = f.read(100)

        # Check for XML declaration or common XMP markers
        first_text = first_bytes.decode('utf-8', errors='ignore').lower()

        # Valid XMP files should contain XML-like content
        if any(marker in first_text for marker in ['<?xml', '<x:xmpmeta', '<rdf:', 'xmlns']):
            return True

        # If it doesn't look like XML, it's probably not a valid XMP file
        return False

    except (UnicodeDecodeError, OSError):
        return False


def find_xmp_file(raw_file_path):
    """
    Find the corresponding XMP file for a raw file.
    Checks for both sidecar (.xmp) files and filters out invalid files.
    """
    # Check for sidecar XMP file
    xmp_sidecar = raw_file_path.with_suffix(raw_file_path.suffix + '.xmp')
    if xmp_sidecar.exists() and is_valid_xmp_file(xmp_sidecar):
        return xmp_sidecar

    # Alternative naming pattern: filename.xmp (without raw extension)
    xmp_alt = raw_file_path.with_suffix('.xmp')
    if xmp_alt.exists() and is_valid_xmp_file(xmp_alt):
        return xmp_alt

    return None

def parse_xmp_flag(xmp_file_path) -> str | None:
    try:
        if not is_valid_xmp_file(xmp_file_path):
            return None

        tree = ET.parse(xmp_file_path)
        root = tree.getroot()

        namespaces = {
            'x': 'adobe:ns:meta/',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'xmp': 'http://ns.adobe.com/xap/1.0/'
        }

        label_elements = root.findall('.//xmp:Label', namespaces)
        if not label_elements:
            label_elements = root.findall('.//{http://ns.adobe.com/xap/1.0/}Label')

        if not label_elements:
            rdf_descriptions = root.findall('.//rdf:Description', namespaces)
            for desc in rdf_descriptions:
                # Check for xmp:Label as an attribute
                xmp_label = desc.get('{http://ns.adobe.com/xap/1.0/}Label')
                if xmp_label:
                    label_value = xmp_label.lower().strip()

                    # Check for red flags
                    if label_value in ['red', 'reject']:
                        return 'red'

                    # Check for green flags
                    if label_value in ['green', 'approved', 'select']:
                        return 'green'

                # Process found label elements
        for element in label_elements:
            if element.text:
                label_value = element.text.lower().strip()

                # Check for red flags
                if label_value in ['red', 'reject']:
                    return 'red'

                # Check for green flags
                if label_value in ['green', 'approved', 'select']:
                    return 'green'

    except ET.ParseError as e:
        logger.error(f"Warning: Skipping malformed XMP File: {xmp_file_path.name}: {e}")
    except UnicodeDecodeError as e:
        logger.error(f"Warning: Encoding error in XMP File: {xmp_file_path.name}: {e}")
    except Exception as e:
        logger.error(f"Warning: Error processing XMP file: {xmp_file_path.name}: {e}")

    return None


def analyze_photos(directory):
    """
    Main function to analyze photos in the directory.
    Only processes files that have corresponding XMP sidecar files.
    Returns a dictionary with counts of red, green, and unflagged photos.
    """
    raw_files = find_raw_files(directory)
    results = {
        'red': 0,
        'green': 0,
        'unflagged': 0,
        'total_files': 0,  # Only count files with XMP
        'skipped_no_xmp': 0
    }

    detailed_results = defaultdict(list)

    print(f"Found {len(raw_files)} raw photo files...")
    print("Analyzing only files with valid XMP sidecar files...\n")

    for raw_file in raw_files:
        xmp_file = find_xmp_file(raw_file)

        if xmp_file:
            results['total_files'] += 1
            flag = parse_xmp_flag(xmp_file)
            if flag == 'red':
                results['red'] += 1
                detailed_results['red'].extend([raw_file, xmp_file])
            elif flag == 'green':
                results['green'] += 1
                detailed_results['green'].extend([raw_file, xmp_file])
            else:
                results['unflagged'] += 1
                detailed_results['unflagged'].extend([raw_file, xmp_file])
        else:
            results['skipped_no_xmp'] += 1

    return results, detailed_results


def move_by_flag_and_copy_dir_structure(*, source_dir: Path, flag: str, destination_dir: Path):
    folders_under_source_dir = [f.name for f in source_dir.iterdir() if f.is_dir()]
    # Create the same folder structure under the destination_dir if it does not exist.

    _, detailed_results = analyze_photos(source_dir)
    target_photos: list[Path] = detailed_results[flag]
    print(f"Moving {len(target_photos)} to {destination_dir}")
    for photo in target_photos:
        # match the mid level dir:
        dir_name = Path(destination_dir / photo.parents[0].name)
        dir_name.mkdir(exist_ok=True, parents=True)
        shutil.move(str(photo), str(dir_name / photo.name))


def delete_by_flag(*, source_dir: Path, flag: str, simulate: bool = False):
    _, detailed_results = analyze_photos(source_dir)
    target_photos: list[Path] = detailed_results[flag]

    if not simulate:
        for photo in target_photos:
            photo.unlink()

        print(f"Deleted {len(target_photos)/2} photos")
    else:
        print(f"Simulated run would have deleted {len(target_photos)/2} photos")