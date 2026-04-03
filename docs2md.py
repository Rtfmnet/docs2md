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

# Import GitManager
from git_sync import GitManager


class GitFatalError(Exception):
    """Raised when a critical git error occurs that should stop all processing."""

    pass


# Class variable to track GitManager initialization status
_git_manager = None
_git_manager_error = False

# Constants
CONFIG_FILE = "docs2md.yaml"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "docs2md.log")
LOG_MAX_BYTES = 32 * 4096  # 32KB
LOG_DEFAULT_LEVEL = "INFO"
README_FILENAME = "README.md"
MD_DIR_NAME = "md"
TAG_AIKB = "doc2md#aikb"
TAG_SKIPFILE = "doc2md#skipfile"
TAG_MASK_PREFIX = "doc2md#mask="

DEFAULT_SUPPORTED_EXTENSIONS = {
    ".asciidoc",
    ".biblatex",
    ".bibtex",
    ".bits",
    ".commonmark",
    ".commonmark_x",
    ".creole",
    ".csljson",
    ".csv",
    ".djot",
    ".docbook",
    ".docx",
    ".dokuwiki",
    ".eml",
    ".endnotexml",
    ".epub",
    ".fb2",
    ".gfm",
    ".haddock",
    ".html",
    ".ipynb",
    ".jats",
    ".jira",
    ".json",
    ".latex",
    ".man",
    ".markdown",
    ".markdown_github",
    ".markdown_mmd",
    ".markdown_phpextra",
    ".markdown_strict",
    ".mdoc",
    ".mediawiki",
    ".muse",
    ".native",
    ".odt",
    ".opml",
    ".org",
    ".pod",
    ".pptx",
    ".ris",
    ".rst",
    ".rtf",
    ".t2t",
    ".textile",
    ".tikiwiki",
    ".tsv",
    ".twiki",
    ".typst",
    ".vimwiki",
    ".xlsx",
    ".xml",
    ".txt",
}


def setup_logging(log_level="INFO"):
    """Initialize logging configuration with configurable log level"""
    # Configure root logger to prevent duplicate logs
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Configure the docs2md logger
    logger = logging.getLogger("docs2md")
    # Remove existing handlers if any
    logger.handlers = []

    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Ensure logs directory exists
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        print(f"Error creating logs directory: {e}")

    # Rotating file handler
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=5
        )
        file_handler.setLevel(numeric_level)
    except Exception as e:
        print(f"Error setting up file handler: {e}")
        file_handler = None

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)

    # Formatter
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    if file_handler:
        file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    if file_handler:
        logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger


def load_config():
    """Load configuration from YAML file.

    Supports two formats:
    1. Legacy flat format: root_folder, git_url, etc. at top level.
    2. Multi-project format: active_project key + named project sections.
       The active project's keys are merged into the top-level config.
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise Exception(f"ERROR - Config file '{CONFIG_FILE}' not found")
    except yaml.YAMLError as e:
        raise Exception(f"ERROR - Failed to parse config file: {e}")

    # Multi-project format: resolve active_project
    active_project = config.get("active_project")
    if active_project:
        project_config = config.get(active_project)
        if not isinstance(project_config, dict):
            raise Exception(
                f"ERROR - active_project '{active_project}' not found in config"
            )
        # Collect known non-project keys: scalars and 'common'
        # Project keys are any dict values that are not 'common'
        non_project_keys = {
            k: v for k, v in config.items() if k == "common" or not isinstance(v, dict)
        }
        # Merge: non-project base + active project keys
        merged = {**non_project_keys, **project_config}
        merged["active_project"] = active_project
        return merged

    return config


def verify_pandoc():
    """Verify if pandoc is installed and accessible"""
    try:
        # Run pandoc --version to check if pandoc is installed
        result = subprocess.run(
            ["pandoc", "--version"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            # Extract version information
            version_info = "Unknown version"
            if hasattr(result, "stdout") and result.stdout:
                version_info = result.stdout.strip().split("\n")[0]
            logging.info(f"Pandoc found: {version_info}")
            return True
        else:
            error_output = "Unknown error"
            if hasattr(result, "stderr") and result.stderr:
                error_output = result.stderr
            logging.error(
                "Pandoc command failed with error code: " + str(result.returncode)
            )
            logging.error("Error output: " + error_output)
            return False
    except FileNotFoundError:
        logging.error("Pandoc is not installed or not in the system PATH")
        return False
    except Exception as e:
        logging.error(f"Error checking for Pandoc: {str(e)}")
        return False


def read_readme(readme_path):
    """Read README.md file content"""
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return None


def check_aikb_tag(readme_content):
    """Check if README content contains the doc2md#aikb tag (directory should be processed)"""
    if readme_content and TAG_AIKB in readme_content:
        return True
    return False


def extract_masks(readme_content):
    """Extract file masks from README content"""
    masks = []
    if not readme_content:
        return masks

    for line in readme_content.split("\n"):
        if TAG_MASK_PREFIX in line:
            # Extract regex pattern from doc2md#mask='pattern' format
            match = re.search(rf"{re.escape(TAG_MASK_PREFIX)}['\"]([^'\"]+)['\"]", line)
            if match:
                masks.append(match.group(1))
    return masks


def get_supported_extensions(config=None):
    """Return the set of supported extensions from config if available, else fall back to the hardcoded set"""
    if config:
        extensions = config.get("common", {}).get("supported_extensions")
        if extensions:
            return set(extensions)
    return DEFAULT_SUPPORTED_EXTENSIONS


def collect_files_in_directory(directory, config=None):
    """Collect all files with supported extensions in current directory only"""
    supported = get_supported_extensions(config)
    files = []
    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in supported:
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
    patterns = [rf"\b{re.escape(filename)}\b", rf"\b{re.escape(name_without_ext)}\b"]

    for pattern in patterns:
        if re.search(pattern, readme_content, re.IGNORECASE):
            return True
    return False


def get_file_reference_line(filename, readme_content):
    """Extract first line where file is referenced in README"""
    if not readme_content:
        return None

    name_without_ext = os.path.splitext(filename)[0]
    patterns = [rf"\b{re.escape(filename)}\b", rf"\b{re.escape(name_without_ext)}\b"]

    for line in readme_content.split("\n"):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return line
    return None


def has_skipfile_tag(line):
    """Check if line contains skipfile tag"""
    if line and TAG_SKIPFILE.lower() in line.lower():
        return True
    return False


def filter_files_by_readme(files, readme_content, has_masks, logger=None, rel_dir=None):
    """Filter files based on README content"""
    filtered = []

    for file in files:
        rel_file = os.path.join(rel_dir, file) if rel_dir and rel_dir != "." else file
        is_referenced = is_file_referenced_in_readme(file, readme_content)

        # If no masks and file is not referenced, skip it
        if not has_masks and not is_referenced:
            if logger:
                logger.debug(f'"{rel_file}" Skipped due to not listed in README.md')
            continue

        # If file is referenced, check for skipfile tag
        if is_referenced:
            ref_line = get_file_reference_line(file, readme_content)
            if ref_line and has_skipfile_tag(ref_line):
                if logger:
                    logger.debug(f'"{rel_file}" Skipped due to `{TAG_SKIPFILE}` tag')
                continue

        filtered.append(file)

    return filtered


def get_target_md_path(source_file, directory, config=None):
    """Determine target MD file path"""
    supported = get_supported_extensions(config)
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
                    if (
                        item_base == base_name
                        and item_ext in supported
                        and item != source_file
                    ):
                        potential_conflicts.append(item)
            except:
                # If we can't check if it's a file in mock, try by extension
                item_base = os.path.splitext(item)[0]
                item_ext = os.path.splitext(item)[1].lower()
                if (
                    item_base == base_name
                    and item_ext in supported
                    and item != source_file
                ):
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


def sync_readme_to_git(readme_path, config, logger):
    """
    Synchronize a README.md file to git repository if configured

    Args:
        readme_path (str): Path to the README.md file to sync
        config (dict): Configuration dictionary
        logger (logging.Logger): Logger instance

    Returns:
        bool: True if sync was successful or not needed, False if it failed
    """
    # Check if git commit and force_readme_git_commit are enabled
    if not config.get("git_commit", False) or not config.get(
        "force_readme_git_commit", False
    ):
        logger.debug("README git commit not enabled in config, skipping sync")
        return False

    # Check if file exists and contains aikb tag
    try:
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = f.read()
                if not check_aikb_tag(readme_content):
                    logger.debug(f"Skipping README sync: {TAG_AIKB} tag not found")
                    return False
        else:
            logger.debug("README file doesn't exist, skipping sync")
            return False
    except Exception as e:
        logger.error(f"Error reading README file: {str(e)}")
        return False

    # Use the existing sync_to_git function to commit the README
    logger.debug(f"Syncing README file to git: {readme_path}")
    result = sync_to_git(readme_path, config, logger)
    if result:
        logger.debug(f"README.md commited to git")
    else:
        logger.error(f"Failed to commit README.md to git")
    return result


def sync_to_git(file_path, config, logger):
    """
    Synchronize a file to git repository if configured

    Args:
        file_path (str): Path to the file to sync
        config (dict): Configuration dictionary
        logger (logging.Logger): Logger instance

    Returns:
        bool: True if sync was successful or not needed, False if it failed
    """
    global _git_manager, _git_manager_error

    # Check if git commit is enabled in config
    if not config.get("git_commit", False):
        logger.debug("Git commit not enabled in config, skipping sync")
        return False

    # Check for initialization with error
    if _git_manager_error:
        logger.debug("GitManager previously failed to initialize, skipping sync")
        return False

    # Initialize GitManager if needed
    if _git_manager is None:
        # Read git URL from config
        git_url = config.get("git_url")
        if not git_url:
            logger.error("Git URL not specified in config")
            _git_manager_error = True
            raise GitFatalError("Git URL not specified in config")

        # Initialize GitManager
        logger.debug("Initializing GitManager")
        try:
            _git_manager = GitManager()
        except Exception as e:
            logger.error(f"Failed to initialize GitManager: {str(e)}")
            _git_manager_error = True
            raise GitFatalError(f"Failed to initialize GitManager: {str(e)}") from e

        # Verify git path
        logger.debug(f"Verifying git path: {git_url}")
        success, details = _git_manager.verify_path(git_url)

        if not success:
            error_msg = details.get("error", "Unknown error")
            logger.error(f"Git path verification failed: {error_msg}")
            _git_manager_error = True
            raise GitFatalError(f"Git path verification failed: {error_msg}")

        logger.debug("Git path verified successfully")

    # Calculate child_path
    try:
        # Get root folder from config
        root_folder = config.get("root_folder")
        if not root_folder:
            logger.error("root_folder not specified in config")
            return False

        # Handle relative/absolute paths for root_folder
        if not os.path.isabs(root_folder):
            root_folder = os.path.abspath(root_folder)

        # Ensure file_path is absolute
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        # Calculate relative path from root to file
        try:
            # Normalize paths to handle different slash formats
            norm_root = os.path.normpath(root_folder)
            norm_file = os.path.normpath(file_path)

            # Make sure file path starts with root path
            if not norm_file.startswith(norm_root):
                logger.error(
                    f"File path {norm_file} is not under root folder {norm_root}"
                )
                return False

            # Calculate child path
            child_path = os.path.relpath(os.path.dirname(norm_file), norm_root)

            # Normalize '.' (file is directly in root_folder) to empty string
            if child_path == ".":
                child_path = ""

            # Remove 'md' dir if it's the last dir
            if (
                child_path.endswith(os.path.sep + MD_DIR_NAME)
                or child_path == MD_DIR_NAME
            ):
                child_path = os.path.dirname(child_path)

            logger.debug(f"Calculated child path: {child_path}")

        except Exception as e:
            logger.error(f"Failed to calculate child path: {str(e)}")
            return False

        # Commit and push file
        git_url = config.get("git_url")
        commit_message = "doc2md#sync"

        logger.debug(f"Pushing file {os.path.basename(file_path)} to git")
        success, details = _git_manager.push_commit_file(
            file_path, git_url, commit_message, git_child_path=child_path
        )

        if success:
            logger.debug(f"Git push successful: {details.get('message', '')}")
            return True
        else:
            error_msg = details.get("error", "Unknown error")
            logger.error(f"Git push failed: {error_msg}")
            return False

    except Exception as e:
        logger.error(f"Failed to sync file to git: {str(e)}")
        return False


def convert_to_markdown(source_path, target_path, logger, config=None):
    """Convert document to markdown using pandoc"""
    try:
        # Ensure target directory exists
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)

        # Use pandoc to convert the file
        cmd = ["pandoc", source_path, "-o", target_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        # Check if conversion was successful
        if result.returncode == 0:
            # This is kept as INFO per requirements (log file conversions)
            logger.debug(f"Created markdown file for {source_path}")

            # Sync to git if configured
            commited_to_git = False
            if config:
                commited_to_git = sync_to_git(target_path, config, logger)

            return True, f"MD generated{', commited to git' if commited_to_git else ''}"
        else:
            error_msg = (
                result.stderr.strip()
                if hasattr(result, "stderr") and result.stderr
                else "Unknown error"
            )
            source_name = os.path.basename(source_path)
            cmd_str = " ".join(cmd)
            logger.error(
                f'Pandoc conversion failed for "{source_name}": {error_msg}\n'
                f"  Command: {cmd_str}"
            )
            return False, f"Error: {error_msg[:100]}"

    except GitFatalError:
        raise
    except Exception as e:
        logger.error(f"Failed to convert {source_path}: {str(e)}")
        return False, f"Error: {str(e)[:100]}"


def process_file(file, directory, force_generation, logger, config):
    """Process a single file for conversion"""
    source_path = os.path.join(directory, file)
    target_path = get_target_md_path(file, directory, config)

    logger.debug(f"Processing file: {file} in {directory}")
    logger.debug(f"Target MD path: {target_path}")

    target_exists = os.path.exists(target_path)
    logger.debug(f"Target exists: {target_exists}")

    should_process = False
    skip_reason = None

    if not target_exists:
        should_process = True
        logger.debug("Target doesn't exist, will generate")
    elif force_generation:
        should_process = True
        logger.debug("Force generation enabled, will regenerate")
    elif is_source_newer(source_path, target_path):
        should_process = True
        logger.debug("Source is newer than target, will regenerate")
    else:
        skip_reason = "MD is up to date"
        logger.debug("MD is up to date, skipping")

    if should_process:
        logger.debug(f"Converting {file} to markdown")
        success, message = convert_to_markdown(source_path, target_path, logger, config)
        logger.debug(f"Conversion result: {success}, {message}")
        return success, message
    else:
        logger.debug(f"Skipping {file} due to: {skip_reason}")
        return None, f"Skipped due to {skip_reason}"


def process_directory(
    directory, config, logger, stats, important_logs=None, root_folder=None
):
    """Process a single directory"""
    # Compute relative path label for logging
    if root_folder:
        try:
            rel_dir = os.path.relpath(directory, root_folder)
        except ValueError:
            rel_dir = directory
    else:
        rel_dir = directory

    logger.debug(f'Processing: "{rel_dir}"')

    dir_stats = {"skipped": 0, "generated": 0, "errors": 0}

    # Check for README.md
    readme_path = os.path.join(directory, README_FILENAME)
    if not os.path.exists(readme_path):
        logger.debug(f"Skipped due to missing {README_FILENAME}")
        stats["dirs_skipped"] += 1
        return

    # Read README content
    readme_content = read_readme(readme_path)
    logger.debug(f"README content found: '{readme_content}'")

    # Check for doc2md#aikb tag — skip directory if tag is missing
    if not check_aikb_tag(readme_content):
        logger.debug(f"Skipped due to missing {TAG_AIKB} tag in {README_FILENAME}")
        stats["dirs_skipped"] += 1
        return

    # Sync README to Git if configured
    result = sync_readme_to_git(readme_path, config, logger)
    # Save important logs for summary
    if result and important_logs is not None:
        important_logs.append('"README.md" commited to git')

    # Extract masks
    masks = extract_masks(readme_content)
    if masks:
        logger.debug(f"Masks found: {masks}")

    # Collect files
    files = collect_files_in_directory(directory, config)
    logger.debug(f"Files with supported extensions: {files}")

    # Apply masks
    if masks:
        filtered_files = apply_masks(files, masks)
        logger.debug(f"Files after applying masks: {filtered_files}")
        files = filtered_files

    # Filter by README
    filtered_files = filter_files_by_readme(
        files, readme_content, bool(masks), logger, rel_dir=rel_dir
    )
    logger.debug(f"Files after README filtering: {filtered_files}")
    files = filtered_files

    # Process each file
    for file in files:
        rel_file = os.path.join(rel_dir, file) if rel_dir and rel_dir != "." else file
        success, message = process_file(
            file, directory, config.get("force_md_generation", False), logger, config
        )

        if success is True:
            dir_stats["generated"] += 1
            stats["files_generated"] += 1
            logger.debug(f'"{rel_file}" {message}')
            # Save important logs for summary
            if important_logs is not None:
                important_logs.append(f'"{rel_file}" {message}')
        elif success is False:
            dir_stats["errors"] += 1
            stats["files_errors"] += 1
            logger.info(f'"{rel_file}" {message}')
            # Save error logs for summary
            if important_logs is not None:
                important_logs.append(f'ERROR: "{rel_file}" {message}')
        else:
            dir_stats["skipped"] += 1
            stats["files_skipped"] += 1
            logger.debug(f'"{rel_file}" {message}')

    if files:
        logger.debug(
            f"Skipped: {dir_stats['skipped']}; Generated: {dir_stats['generated']}; Errors: {dir_stats['errors']}"
        )
    else:
        logger.debug("No files to process in this directory.")

    stats["dirs_processed"] += 1


def process_directories_recursively(
    root_folder, config, logger, stats, important_logs=None
):
    """Process all directories recursively starting from root"""
    for dirpath, dirnames, filenames in os.walk(root_folder):
        try:
            rel_dirpath = os.path.relpath(dirpath, root_folder)
        except ValueError:
            rel_dirpath = dirpath
        readme_path = os.path.join(dirpath, README_FILENAME)
        if not os.path.exists(readme_path):
            logger.debug(f'"{rel_dirpath}" — Skipped (no {README_FILENAME})')
            stats["dirs_skipped"] += 1
            dirnames[:] = []
            continue
        readme_content = read_readme(readme_path)
        if not check_aikb_tag(readme_content):
            logger.debug(f'"{rel_dirpath}" — Skipped (no {TAG_AIKB} tag)')
            stats["dirs_skipped"] += 1
            dirnames[:] = []
            continue
        process_directory(
            dirpath, config, logger, stats, important_logs, root_folder=root_folder
        )


def main():
    """Main function"""
    # Load config early to get log level
    try:
        config = load_config()
        log_level = config.get("common", {}).get("log_level", LOG_DEFAULT_LEVEL)
    except Exception as e:
        print(f"ERROR loading config: {e}")
        log_level = LOG_DEFAULT_LEVEL

    # Initialize logging with config-specified level
    logger = setup_logging(log_level)

    # List to store important log messages for summary
    important_logs = []

    try:
        # Log start time - kept as INFO per requirements
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(start_time)

        # Verify pandoc
        if not verify_pandoc():
            logger.error("Pandoc is not installed or not accessible")
            sys.exit(1)

        # Get root folder
        root_folder = config.get("root_folder")
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

        # Root folder log - kept as INFO per requirements
        active_project = config.get("active_project")
        if active_project:
            logger.info(f"Active project: {active_project}")
        logger.info(f'Files path: "{root_folder}"')
        if config.get("git_commit", False):
            git_url = config.get("git_url", "")
            logger.info(f'Git path: "{git_url}"')

        # Process directories
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        process_directories_recursively(
            root_folder, config, logger, stats, important_logs
        )

        # Show summary of results - kept as INFO per requirements
        logger.info("")
        logger.info("SUMMARY:")
        logger.info(f"Directories processed: {stats['dirs_processed']}")
        logger.info(f"Directories skipped: {stats['dirs_skipped']}")
        logger.info(f"Files generated: {stats['files_generated']}")
        logger.info(f"Files skipped as actual: {stats['files_skipped']}")
        logger.info(f"Files with errors: {stats['files_errors']}")

        # Show important logs in summary
        if important_logs:
            logger.info("")
            logger.info("Change log:")
            for log in important_logs:
                logger.info(log)
        logger.debug("Execution complete.")

        # Pause if configured
        if config.get("common", {}).get("pause_before_exit", False):
            input("Press any key to exit...")

    except GitFatalError as e:
        logger.error(f"Critical git error — stopping processing: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(str(e))
        print(f"ERROR: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Remove the basicConfig as we're setting up logging in setup_logging()
    try:
        main()
    except Exception as e:
        print(f"Program failed with error: {e}")
