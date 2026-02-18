"""
docs2md - Tool to synchronize documents to markdown files
Converts various document formats to .md files using pandoc
"""

import os
import re
import sys
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import yaml


# Constants
CONFIG_FILE = 'docs2md.yaml'
LOG_DIR = 'logs'
LOG_FILE = os.path.join(LOG_DIR, 'docs2md.log')
LOG_MAX_BYTES = 32*4096  # 32KB
README_FILENAME = 'README.md'
MD_DIR_NAME = 'md'
TAG_SKIPDIR = 'doc2md#skipdir'
TAG_SKIPFILE = 'doc2md#skipfile'
TAG_MASK_PREFIX = 'doc2md#mask='

SUPPORTED_EXTENSIONS = {
    '.asciidoc', '.biblatex', '.bibtex', '.bits', '.commonmark', '.commonmark_x',
    '.creole', '.csljson', '.csv', '.djot', '.docbook', '.docx', '.dokuwiki',
    '.endnotexml', '.epub', '.fb2', '.gfm', '.haddock', '.html', '.ipynb', '.jats',
    '.jira', '.json', '.latex', '.man', '.markdown', '.markdown_github',
    '.markdown_mmd', '.markdown_phpextra', '.markdown_strict', '.mdoc', '.mediawiki',
    '.muse', '.native', '.odt', '.opml', '.org', '.pod', '.pptx', '.ris', '.rst',
    '.rtf', '.t2t', '.textile', '.tikiwiki', '.tsv', '.twiki', '.typst', '.vimwiki',
    '.xlsx', '.xml'
}


def setup_logging():
    """Initialize logging configuration"""
    logger = logging.getLogger('docs2md')
    logger.setLevel(logging.INFO)

    # Ensure logs directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def load_config():
    """Load configuration from YAML file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        raise Exception(f"ERROR - Config file '{CONFIG_FILE}' not found")
    except yaml.YAMLError as e:
        raise Exception(f"ERROR - Failed to parse config file: {e}")


def verify_pandoc():
    """Verify if pandoc is installed and accessible"""
    try:
        result = subprocess.run(
            ['pandoc', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def read_readme(readme_path):
    """Read README.md file content"""
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return None


def check_skipdir(readme_content):
    """Check if directory should be skipped based on README content"""
    if readme_content and TAG_SKIPDIR in readme_content:
        return True
    return False


def extract_masks(readme_content):
    """Extract file masks from README content"""
    masks = []
    if not readme_content:
        return masks
    
    for line in readme_content.split('\n'):
        if TAG_MASK_PREFIX in line:
            # Extract regex pattern from doc2md#mask='pattern' format
            match = re.search(rf"{re.escape(TAG_MASK_PREFIX)}['\"]([^'\"]+)['\"]", line)
            if match:
                masks.append(match.group(1))
    return masks


def collect_files_in_directory(directory):
    """Collect all files with supported extensions in current directory only"""
    files = []
    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    files.append(item)
    except Exception as e:
        return []
    return files


def apply_masks(files, masks):
    """Apply regex masks to filter files"""
    if not masks:
        return files
    
    filtered = []
    for file in files:
        for mask in masks:
            try:
                if re.match(mask, file):
                    filtered.append(file)
                    break
            except re.error:
                continue
    return filtered


def is_file_referenced_in_readme(filename, readme_content):
    """Check if file is referenced in README (case insensitive, word boundary)"""
    if not readme_content:
        return False
    
    # Get filename with and without extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Create patterns with word boundaries
    patterns = [
        rf'\b{re.escape(filename)}\b',
        rf'\b{re.escape(name_without_ext)}\b'
    ]
    
    for pattern in patterns:
        if re.search(pattern, readme_content, re.IGNORECASE):
            return True
    return False


def get_file_reference_line(filename, readme_content):
    """Extract first line where file is referenced in README"""
    if not readme_content:
        return None
    
    name_without_ext = os.path.splitext(filename)[0]
    patterns = [
        rf'\b{re.escape(filename)}\b',
        rf'\b{re.escape(name_without_ext)}\b'
    ]
    
    for line in readme_content.split('\n'):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return line
    return None


def has_skipfile_tag(line):
    """Check if line contains skipfile tag"""
    if line and TAG_SKIPFILE.lower() in line.lower():
        return True
    return False


def filter_files_by_readme(files, readme_content, has_masks):
    """Filter files based on README content"""
    filtered = []
    
    for file in files:
        is_referenced = is_file_referenced_in_readme(file, readme_content)
        
        # If no masks and file is not referenced, skip it
        if not has_masks and not is_referenced:
            continue
        
        # If file is referenced, check for skipfile tag
        if is_referenced:
            ref_line = get_file_reference_line(file, readme_content)
            if ref_line and has_skipfile_tag(ref_line):
                continue
        
        filtered.append(file)
    
    return filtered


def get_target_md_path(source_file, directory):
    """Determine target MD file path"""
    base_name = os.path.splitext(source_file)[0]
    ext = os.path.splitext(source_file)[1]

    # Check if 'md' subdirectory exists
    md_dir = os.path.join(directory, MD_DIR_NAME)
    target_dir = md_dir if os.path.exists(md_dir) else directory

    # Check for name conflicts (same base name, different extension)
    potential_conflicts = []
    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            # Only check files, not directories
            try:
                if os.path.isfile(item_path):
                    item_base = os.path.splitext(item)[0]
                    item_ext = os.path.splitext(item)[1].lower()
                    if item_base == base_name and item_ext in SUPPORTED_EXTENSIONS and item != source_file:
                        potential_conflicts.append(item)
            except:
                # If we can't check if it's a file in mock, try by extension
                item_base = os.path.splitext(item)[0]
                item_ext = os.path.splitext(item)[1].lower()
                if item_base == base_name and item_ext in SUPPORTED_EXTENSIONS and item != source_file:
                    potential_conflicts.append(item)
    except:
        pass

    # If conflicts exist, add extension to filename
    if potential_conflicts:
        md_filename = f"{base_name}{ext.replace('.', '_')}.md"
    else:
        md_filename = f"{base_name}.md"

    return os.path.join(target_dir, md_filename)


def is_source_newer(source_path, target_path):
    """Check if source file is newer than target file"""
    try:
        source_mtime = os.path.getmtime(source_path)
        target_mtime = os.path.getmtime(target_path)
        return source_mtime > target_mtime
    except:
        return True


def convert_to_markdown(source_path, target_path, logger):
    """Convert document to markdown using pandoc"""
    try:
        # Ensure target directory exists
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)
        
        result = subprocess.run(
            ['pandoc', source_path, '-o', target_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            return True, "MD generated"
        else:
            logger.error(f"Pandoc conversion failed for {source_path}: {result.stderr}")
            return False, f"Error: {result.stderr[:100]}"
    except subprocess.TimeoutExpired:
        logger.error(f"Pandoc conversion timeout for {source_path}")
        return False, "Error: Conversion timeout"
    except Exception as e:
        logger.error(f"Failed to convert {source_path}: {str(e)}")
        return False, f"Error: {str(e)[:100]}"


def process_file(file, directory, force_generation, logger):
    """Process a single file for conversion"""
    source_path = os.path.join(directory, file)
    target_path = get_target_md_path(file, directory)
    
    target_exists = os.path.exists(target_path)
    
    should_process = False
    skip_reason = None
    
    if not target_exists:
        should_process = True
    elif force_generation:
        should_process = True
    elif is_source_newer(source_path, target_path):
        should_process = True
    else:
        skip_reason = "MD is up to date"
    
    if should_process:
        success, message = convert_to_markdown(source_path, target_path, logger)
        return success, message
    else:
        return None, f"Skipped due to {skip_reason}"


def process_directory(directory, config, logger, stats):
    """Process a single directory"""
    logger.info(directory)
    
    dir_stats = {'skipped': 0, 'generated': 0, 'errors': 0}
    
    # Check for README.md
    readme_path = os.path.join(directory, README_FILENAME)
    if not os.path.exists(readme_path):
        logger.info(f"Skipped due to missing {README_FILENAME}")
        stats['dirs_skipped'] += 1
        return
    
    # Read README content
    readme_content = read_readme(readme_path)
    
    # Check for skipdir tag
    if check_skipdir(readme_content):
        logger.info(f"Skipped due to {TAG_SKIPDIR} tag")
        stats['dirs_skipped'] += 1
        return
    
    # Extract masks
    masks = extract_masks(readme_content)
    
    # Collect files
    files = collect_files_in_directory(directory)
    
    # Apply masks
    if masks:
        files = apply_masks(files, masks)
    
    # Filter by README
    files = filter_files_by_readme(files, readme_content, bool(masks))
    
    # Process each file
    for file in files:
        success, message = process_file(
            file,
            directory,
            config.get('force_md_generation', False),
            logger
        )
        
        logger.info(f"{file} {message}")
        
        if success is True:
            dir_stats['generated'] += 1
            stats['files_generated'] += 1
        elif success is False:
            dir_stats['errors'] += 1
            stats['files_errors'] += 1
        else:
            dir_stats['skipped'] += 1
            stats['files_skipped'] += 1
    
    if files:
        logger.info(f"Skipped: {dir_stats['skipped']}; Generated: {dir_stats['generated']}; Errors: {dir_stats['errors']}")
    
    stats['dirs_processed'] += 1


def process_directories_recursively(root_folder, config, logger, stats):
    """Process all directories recursively starting from root"""
    skip_dirs = set()
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # Check if current directory should be skipped
        should_skip = False
        for skip_dir in skip_dirs:
            if dirpath.startswith(skip_dir):
                should_skip = True
                break
        
        if should_skip:
            continue
        
        # Check if this directory has skipdir tag
        readme_path = os.path.join(dirpath, README_FILENAME)
        if os.path.exists(readme_path):
            readme_content = read_readme(readme_path)
            if check_skipdir(readme_content):
                skip_dirs.add(dirpath)
                logger.info(dirpath)
                logger.info(f"Skipped due to {TAG_SKIPDIR} tag")
                stats['dirs_skipped'] += 1
                continue
        
        process_directory(dirpath, config, logger, stats)


def main():
    """Main function"""
    logger = setup_logging()
    
    try:
        # Log start time
        logger.info(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Load config
        config = load_config()
        
        # Verify pandoc
        if not verify_pandoc():
            logger.error("Pandoc is not installed or not accessible")
            sys.exit(1)
        
        # Get root folder
        root_folder = config.get('root_folder')
        if not root_folder:
            logger.error("root_folder not specified in config")
            sys.exit(1)
        
        # Handle relative/absolute paths
        if not os.path.isabs(root_folder):
            root_folder = os.path.abspath(root_folder)
        
        # Verify root folder exists
        if not os.path.exists(root_folder):
            logger.error(f"Root folder does not exist: {root_folder}")
            sys.exit(1)
        
        logger.info(root_folder)
        
        # Process directories
        stats = {
            'dirs_processed': 0,
            'dirs_skipped': 0,
            'files_generated': 0,
            'files_skipped': 0,
            'files_errors': 0
        }
        
        process_directories_recursively(root_folder, config, logger, stats)
        
        # Pause if configured
        if config.get('pause_before_exit', False):
            input('Press any key to exit...')
    
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
