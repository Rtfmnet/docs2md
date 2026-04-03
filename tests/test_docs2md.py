"""
Unit tests for docs2md tool
"""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock
import os
import sys
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import docs2md


class TestSetupLogging(unittest.TestCase):
    """Test logging setup"""

    def test_setup_logging_positive(self):
        """Test successful logging setup"""
        logger = docs2md.setup_logging()
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "docs2md")
        self.assertEqual(len(logger.handlers), 2)

    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns a valid logger"""
        logger = docs2md.setup_logging()
        self.assertTrue(hasattr(logger, "info"))
        self.assertTrue(hasattr(logger, "error"))


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading"""

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="root_folder: /test\ncommon:\n  pause_before_exit: true\n  log_level: INFO",
    )
    @patch("yaml.safe_load")
    def test_load_config_positive(self, mock_yaml, mock_file):
        """Test successful config loading"""
        mock_yaml.return_value = {
            "root_folder": "/test",
            "common": {"pause_before_exit": True, "log_level": "INFO"},
        }
        config = docs2md.load_config()
        self.assertIsNotNone(config)
        self.assertIn("root_folder", config)

    def test_load_config_file_not_found(self):
        """Test config loading with missing file"""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            with self.assertRaises(Exception) as context:
                docs2md.load_config()
            self.assertIn("not found", str(context.exception))


class TestVerifyPandoc(unittest.TestCase):
    """Test pandoc verification"""

    @patch("subprocess.run")
    def test_verify_pandoc_positive(self, mock_run):
        """Test successful pandoc verification"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Pandoc 2.7.3"
        mock_run.return_value = mock_result
        result = docs2md.verify_pandoc()
        self.assertTrue(result)

    @patch("subprocess.run")
    def test_verify_pandoc_not_installed(self, mock_run):
        """Test pandoc not installed"""
        mock_run.side_effect = FileNotFoundError()
        result = docs2md.verify_pandoc()
        self.assertFalse(result)


class TestReadReadme(unittest.TestCase):
    """Test README reading"""

    @patch("builtins.open", new_callable=mock_open, read_data="Test content")
    def test_read_readme_positive(self, mock_file):
        """Test successful README reading"""
        content = docs2md.read_readme("/test/README.md")
        self.assertEqual(content, "Test content")

    @patch("builtins.open", side_effect=Exception("File error"))
    def test_read_readme_error(self, mock_file):
        """Test README reading with error"""
        content = docs2md.read_readme("/test/README.md")
        self.assertIsNone(content)


class TestCheckAikbTag(unittest.TestCase):
    """Test doc2md#aikb tag checking"""

    def test_check_aikb_tag_positive(self):
        """Test aikb tag is found"""
        content = "Some text\ndoc2md#aikb\nMore text"
        result = docs2md.check_aikb_tag(content)
        self.assertTrue(result)

    def test_check_aikb_tag_negative(self):
        """Test aikb tag is not found"""
        content = "Some text\nNo special tags\nMore text"
        result = docs2md.check_aikb_tag(content)
        self.assertFalse(result)

    def test_check_aikb_tag_none_content(self):
        """Test aikb tag check with None content"""
        result = docs2md.check_aikb_tag(None)
        self.assertFalse(result)


class TestExtractMasks(unittest.TestCase):
    """Test mask extraction from README"""

    def test_extract_masks_positive(self):
        """Test successful mask extraction"""
        content = "doc2md#mask='^.*\\.docx$'\nOther text\ndoc2md#mask='^test.*$'"
        masks = docs2md.extract_masks(content)
        self.assertEqual(len(masks), 2)
        self.assertIn("^.*\\.docx$", masks)

    def test_extract_masks_no_masks(self):
        """Test extraction with no masks"""
        content = "Some text without masks"
        masks = docs2md.extract_masks(content)
        self.assertEqual(len(masks), 0)


class TestCollectFilesInDirectory(unittest.TestCase):
    """Test file collection in directory"""

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_collect_files_positive(self, mock_isfile, mock_listdir):
        """Test successful file collection"""
        mock_listdir.return_value = ["file1.docx", "file2.txt", "file3.pdf"]
        mock_isfile.return_value = True
        files = docs2md.collect_files_in_directory("/test")
        self.assertIn("file1.docx", files)

    @patch("os.listdir", side_effect=Exception("Access denied"))
    def test_collect_files_error(self, mock_listdir):
        """Test file collection with error"""
        files = docs2md.collect_files_in_directory("/test")
        self.assertEqual(len(files), 0)


class TestApplyMasks(unittest.TestCase):
    """Test mask application to files"""

    def test_apply_masks_positive(self):
        """Test successful mask application"""
        files = ["test.docx", "report.docx", "data.xlsx"]
        masks = ["^test.*$"]
        result = docs2md.apply_masks(files, masks)
        self.assertIn("test.docx", result)
        self.assertNotIn("report.docx", result)

    def test_apply_masks_no_masks(self):
        """Test with no masks provided"""
        files = ["test.docx", "report.docx"]
        masks = []
        result = docs2md.apply_masks(files, masks)
        self.assertEqual(result, files)


class TestIsFileReferencedInReadme(unittest.TestCase):
    """Test file reference checking in README"""

    def test_is_file_referenced_positive(self):
        """Test file is referenced"""
        content = "See file test.docx for details"
        result = docs2md.is_file_referenced_in_readme("test.docx", content)
        self.assertTrue(result)

    def test_is_file_referenced_negative(self):
        """Test file is not referenced"""
        content = "See file report.docx for details"
        result = docs2md.is_file_referenced_in_readme("test.docx", content)
        self.assertFalse(result)


class TestGetFileReferenceLine(unittest.TestCase):
    """Test file reference line extraction"""

    def test_get_file_reference_line_positive(self):
        """Test successful line extraction"""
        content = "Line 1\nSee test.docx here\nLine 3"
        line = docs2md.get_file_reference_line("test.docx", content)
        self.assertIsNotNone(line)
        self.assertIn("test.docx", line)

    def test_get_file_reference_line_not_found(self):
        """Test line extraction when file not referenced"""
        content = "Line 1\nNo file here\nLine 3"
        line = docs2md.get_file_reference_line("test.docx", content)
        self.assertIsNone(line)


class TestHasSkipfileTag(unittest.TestCase):
    """Test skipfile tag checking"""

    def test_has_skipfile_tag_positive(self):
        """Test skipfile tag is found"""
        line = "test.docx doc2md#skipfile should be skipped"
        result = docs2md.has_skipfile_tag(line)
        self.assertTrue(result)

    def test_has_skipfile_tag_negative(self):
        """Test skipfile tag is not found"""
        line = "test.docx should be processed"
        result = docs2md.has_skipfile_tag(line)
        self.assertFalse(result)


class TestFilterFilesByReadme(unittest.TestCase):
    """Test file filtering based on README"""

    def test_filter_files_positive(self):
        """Test successful file filtering"""
        files = ["test.docx", "report.docx"]
        content = "Process test.docx"
        logger = Mock()
        result = docs2md.filter_files_by_readme(files, content, True, logger)
        self.assertIn("test.docx", result)

    def test_filter_files_with_skipfile(self):
        """Test filtering with skipfile tag"""
        files = ["test.docx"]
        content = "test.docx doc2md#skipfile"
        logger = Mock()
        result = docs2md.filter_files_by_readme(files, content, True, logger)
        self.assertEqual(len(result), 0)


class TestGetTargetMdPath(unittest.TestCase):
    """Test MD target path determination"""

    @patch("os.path.exists")
    @patch("os.listdir")
    def test_get_target_md_path_no_md_dir(self, mock_listdir, mock_exists):
        """Test target path without md directory"""
        mock_exists.return_value = False
        mock_listdir.return_value = []
        result = docs2md.get_target_md_path("test.docx", "/dir")
        self.assertTrue(result.endswith("test.md"))

    @patch("os.path.isfile")
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_get_target_md_path_with_conflict(
        self, mock_listdir, mock_exists, mock_isfile
    ):
        """Test target path with name conflict"""
        mock_exists.return_value = False
        mock_listdir.return_value = ["test.xlsx", "test.docx"]
        mock_isfile.return_value = True
        result = docs2md.get_target_md_path("test.docx", "/dir")
        self.assertTrue(result.endswith("test_docx.md"))


class TestIsSourceNewer(unittest.TestCase):
    """Test source file timestamp comparison"""

    @patch("os.path.getmtime")
    def test_is_source_newer_positive(self, mock_getmtime):
        """Test source is newer than target"""
        mock_getmtime.side_effect = [2000, 1000]
        result = docs2md.is_source_newer("/source", "/target")
        self.assertTrue(result)

    @patch("os.path.getmtime")
    def test_is_source_newer_negative(self, mock_getmtime):
        """Test source is not newer than target"""
        mock_getmtime.side_effect = [1000, 2000]
        result = docs2md.is_source_newer("/source", "/target")
        self.assertFalse(result)


class TestConvertToMarkdown(unittest.TestCase):
    """Test markdown conversion"""

    @patch("subprocess.run")
    @patch("os.makedirs")
    def test_convert_to_markdown_positive(self, mock_makedirs, mock_run):
        """Test successful conversion"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        logger = Mock()
        success, message = docs2md.convert_to_markdown("/src.docx", "/dst.md", logger)
        self.assertTrue(success)
        self.assertIn("generated", message)

    @patch("subprocess.run")
    @patch("os.makedirs")
    def test_convert_to_markdown_failure(self, mock_makedirs, mock_run):
        """Test conversion failure"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error occurred"
        mock_run.return_value = mock_result
        logger = Mock()
        success, message = docs2md.convert_to_markdown("/src.docx", "/dst.md", logger)
        self.assertFalse(success)
        self.assertIn("Error", message)


class TestProcessFile(unittest.TestCase):
    """Test file processing"""

    @patch("docs2md.convert_to_markdown")
    @patch("docs2md.get_target_md_path")
    @patch("os.path.exists")
    def test_process_file_new_file(self, mock_exists, mock_get_path, mock_convert):
        """Test processing new file"""
        mock_exists.return_value = False
        mock_get_path.return_value = "/dir/test.md"
        mock_convert.return_value = (True, "MD generated")
        logger = Mock()
        config = {"git_commit": False}
        success, message = docs2md.process_file(
            "test.docx", "/dir", False, logger, config
        )
        self.assertTrue(success)

    @patch("docs2md.is_source_newer")
    @patch("docs2md.get_target_md_path")
    @patch("os.path.exists")
    def test_process_file_up_to_date(self, mock_exists, mock_get_path, mock_newer):
        """Test processing up-to-date file"""
        mock_exists.return_value = True
        mock_get_path.return_value = "/dir/test.md"
        mock_newer.return_value = False
        logger = Mock()
        config = {"git_commit": False}
        success, message = docs2md.process_file(
            "test.docx", "/dir", False, logger, config
        )
        self.assertIsNone(success)
        self.assertIn("Skipped", message)


class TestSyncReadmeToGit(unittest.TestCase):
    """Test sync_readme_to_git function — validates force_readme_git_commit behaviour"""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _config(self, git_commit=True, force_readme=True):
        return {
            "git_commit": git_commit,
            "force_readme_git_commit": force_readme,
            "git_url": "https://example.com/repo/-/tree/main/docs",
            "root_folder": "/root",
        }

    # ------------------------------------------------------------------
    # gate: both flags must be True
    # ------------------------------------------------------------------
    def test_skipped_when_git_commit_false(self):
        """Returns False immediately when git_commit is False, regardless of force_readme_git_commit"""
        logger = Mock()
        config = self._config(git_commit=False, force_readme=True)
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)

    def test_skipped_when_force_readme_false(self):
        """Returns False immediately when force_readme_git_commit is False"""
        logger = Mock()
        config = self._config(git_commit=True, force_readme=False)
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)

    def test_skipped_when_both_flags_false(self):
        """Returns False when both git_commit and force_readme_git_commit are False"""
        logger = Mock()
        config = self._config(git_commit=False, force_readme=False)
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # gate: readme file presence
    # ------------------------------------------------------------------
    @patch("os.path.exists", return_value=False)
    def test_skipped_when_readme_missing(self, _mock_exists):
        """Returns False when the README.md file does not exist on disk"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # gate: doc2md#aikb tag must be present
    # ------------------------------------------------------------------
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="Some content without aikb tag",
    )
    @patch("os.path.exists", return_value=True)
    def test_skipped_when_aikb_tag_missing(self, _mock_exists, _mock_file):
        """Returns False when README.md does not contain the doc2md#aikb tag"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="Intro\nSome content\nMore content",
    )
    @patch("os.path.exists", return_value=True)
    def test_aikb_tag_missing_mid_file_is_detected(self, _mock_exists, _mock_file):
        """Correctly detects absence of doc2md#aikb tag anywhere in the file"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # happy path: delegates to sync_to_git
    # ------------------------------------------------------------------
    @patch("docs2md.sync_to_git", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="doc2md#aikb\nNormal README content",
    )
    @patch("os.path.exists", return_value=True)
    def test_calls_sync_to_git_when_all_conditions_met(
        self, _mock_exists, _mock_file, mock_sync
    ):
        """Delegates to sync_to_git and returns True when all conditions are satisfied"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertTrue(result)
        mock_sync.assert_called_once_with("/root/README.md", config, logger)

    @patch("docs2md.sync_to_git", return_value=False)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="doc2md#aikb\nNormal README content",
    )
    @patch("os.path.exists", return_value=True)
    def test_returns_false_when_sync_to_git_fails(
        self, _mock_exists, _mock_file, mock_sync
    ):
        """Returns False and logs an error when the underlying sync_to_git call fails"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)
        logger.error.assert_called()

    # ------------------------------------------------------------------
    # robustness: error reading readme
    # ------------------------------------------------------------------
    @patch("builtins.open", side_effect=IOError("Permission denied"))
    @patch("os.path.exists", return_value=True)
    def test_returns_false_on_read_error(self, _mock_exists, _mock_file):
        """Returns False and logs an error when README.md cannot be read"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertFalse(result)
        logger.error.assert_called()

    # ------------------------------------------------------------------
    # readme contains aikb tag mid-file — still detected
    # ------------------------------------------------------------------
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="Intro\ndoc2md#aikb\nMore content",
    )
    @patch("os.path.exists", return_value=True)
    @patch("docs2md.sync_to_git", return_value=True)
    def test_aikb_tag_mid_file_is_detected(self, mock_sync, _mock_exists, _mock_file):
        """Detects doc2md#aikb anywhere in the file, not just the first line"""
        logger = Mock()
        config = self._config()
        result = docs2md.sync_readme_to_git("/root/README.md", config, logger)
        self.assertTrue(result)


class TestGetSupportedExtensions(unittest.TestCase):
    """Test get_supported_extensions helper"""

    def test_returns_config_extensions_when_present(self):
        """Returns the set from config['common']['supported_extensions'] when provided"""
        config = {"common": {"supported_extensions": [".docx", ".pdf"]}}
        result = docs2md.get_supported_extensions(config)
        self.assertEqual(result, {".docx", ".pdf"})

    def test_falls_back_to_constant_when_config_is_none(self):
        """Falls back to SUPPORTED_EXTENSIONS constant when config is None"""
        result = docs2md.get_supported_extensions(None)
        self.assertIs(result, docs2md.DEFAULT_SUPPORTED_EXTENSIONS)

    def test_falls_back_to_constant_when_no_common_key(self):
        """Falls back to SUPPORTED_EXTENSIONS constant when config has no 'common' key"""
        result = docs2md.get_supported_extensions({})
        self.assertIs(result, docs2md.DEFAULT_SUPPORTED_EXTENSIONS)

    def test_falls_back_to_constant_when_no_supported_extensions_key(self):
        """Falls back to SUPPORTED_EXTENSIONS constant when config has 'common' but no 'supported_extensions'"""
        result = docs2md.get_supported_extensions({"common": {}})
        self.assertIs(result, docs2md.DEFAULT_SUPPORTED_EXTENSIONS)

    def test_config_extensions_are_returned_as_set(self):
        """Ensures the returned value is always a set"""
        config = {"common": {"supported_extensions": [".txt", ".rst", ".txt"]}}
        result = docs2md.get_supported_extensions(config)
        self.assertIsInstance(result, set)
        self.assertEqual(result, {".txt", ".rst"})


class TestCollectFilesWithConfigExtensions(unittest.TestCase):
    """Test that collect_files_in_directory respects config-driven extensions"""

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_collect_files_uses_config_extensions(self, mock_isfile, mock_listdir):
        """collect_files_in_directory filters by config extensions, not the hardcoded set"""
        mock_listdir.return_value = ["doc.custom_ext", "doc.docx"]
        mock_isfile.return_value = True
        config = {"common": {"supported_extensions": [".custom_ext"]}}
        files = docs2md.collect_files_in_directory("/test", config)
        self.assertIn("doc.custom_ext", files)
        self.assertNotIn("doc.docx", files)

    @patch("os.listdir")
    @patch("os.path.isfile")
    def test_collect_files_falls_back_without_config(self, mock_isfile, mock_listdir):
        """collect_files_in_directory falls back to SUPPORTED_EXTENSIONS when no config given"""
        mock_listdir.return_value = ["doc.docx", "doc.xyz_unknown"]
        mock_isfile.return_value = True
        files = docs2md.collect_files_in_directory("/test")
        self.assertIn("doc.docx", files)
        self.assertNotIn("doc.xyz_unknown", files)


class TestLoadConfigCommonSection(unittest.TestCase):
    """Test that load_config correctly parses the 'common' section"""

    def test_load_config_returns_common_section(self):
        """load_config returns a dict containing a 'common' key with supported_extensions"""
        yaml_content = "common:\n  supported_extensions:\n    - .docx\n    - .txt\n"
        with patch("builtins.open", new_callable=mock_open, read_data=yaml_content):
            config = docs2md.load_config()
        self.assertIn("common", config)
        self.assertIn("supported_extensions", config["common"])
        self.assertIn(".docx", config["common"]["supported_extensions"])
        self.assertIn(".txt", config["common"]["supported_extensions"])

    def test_load_config_common_extensions_used_by_get_supported_extensions(self):
        """Extensions loaded from config are correctly consumed by get_supported_extensions"""
        yaml_content = "common:\n  supported_extensions:\n    - .docx\n    - .pdf\n"
        with patch("builtins.open", new_callable=mock_open, read_data=yaml_content):
            config = docs2md.load_config()
        exts = docs2md.get_supported_extensions(config)
        self.assertEqual(exts, {".docx", ".pdf"})


class TestProcessDirectoriesRecursively(unittest.TestCase):
    """Test subdirectory pruning in process_directories_recursively"""

    def _make_walk_result(self, entries):
        """Helper: build os.walk-style list of (dirpath, dirnames, filenames)"""
        return iter(entries)

    def _run(self, walk_entries, readme_exists_map, readme_content_map):
        """
        Run process_directories_recursively with controlled os.walk and filesystem mocks.

        walk_entries: list of (dirpath, dirnames_list, filenames_list)
                      dirnames_list must be a plain list so in-place mutation works.
        readme_exists_map: dict {path: bool} for os.path.exists
        readme_content_map: dict {path: str} for read_readme
        """
        visited = []

        def mock_process_directory(directory, *args, **kwargs):
            visited.append(directory)

        logger = Mock()
        config = {}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        with (
            patch("docs2md.os.walk", return_value=iter(walk_entries)),
            patch(
                "docs2md.os.path.exists",
                side_effect=lambda p: readme_exists_map.get(p, False),
            ),
            patch(
                "docs2md.read_readme",
                side_effect=lambda p: readme_content_map.get(p, ""),
            ),
            patch("docs2md.process_directory", side_effect=mock_process_directory),
        ):
            docs2md.process_directories_recursively("/root", config, logger, stats)

        return visited, stats

    def test_subdir_skipped_when_parent_has_no_readme(self):
        """Subdirectory must not be visited when parent has no README.md"""
        parent = "/root/parent"
        child = "/root/parent/child"
        parent_readme = os.path.join(parent, docs2md.README_FILENAME)

        # os.walk returns parent with child in dirnames; child also listed separately
        walk_entries = [
            (parent, ["child"], []),
            (child, [], []),
        ]
        readme_exists_map = {parent_readme: False}
        readme_content_map = {}

        visited, stats = self._run(walk_entries, readme_exists_map, readme_content_map)

        self.assertNotIn(
            parent, visited, "parent without README should not be processed"
        )
        self.assertNotIn(
            child, visited, "child of parent without README should not be visited"
        )

    def test_subdir_skipped_when_parent_readme_has_no_aikb_tag(self):
        """Subdirectory must not be visited when parent README lacks doc2md#aikb tag"""
        parent = "/root/parent"
        child = "/root/parent/child"
        parent_readme = os.path.join(parent, docs2md.README_FILENAME)

        walk_entries = [
            (parent, ["child"], []),
            (child, [], []),
        ]
        readme_exists_map = {parent_readme: True}
        readme_content_map = {parent_readme: "# No aikb tag here"}

        visited, stats = self._run(walk_entries, readme_exists_map, readme_content_map)

        self.assertNotIn(
            parent, visited, "parent without aikb tag should not be processed"
        )
        self.assertNotIn(
            child, visited, "child of parent without aikb tag should not be visited"
        )

    def test_subdir_visited_when_parent_has_readme_with_aikb(self):
        """Subdirectory must be visited when parent README has doc2md#aikb tag"""
        parent = "/root/parent"
        child = "/root/parent/child"
        parent_readme = os.path.join(parent, docs2md.README_FILENAME)
        child_readme = os.path.join(child, docs2md.README_FILENAME)

        walk_entries = [
            (parent, ["child"], []),
            (child, [], []),
        ]
        readme_exists_map = {parent_readme: True, child_readme: True}
        readme_content_map = {
            parent_readme: f"# Test\n{docs2md.TAG_AIKB}\n",
            child_readme: f"# Test\n{docs2md.TAG_AIKB}\n",
        }

        visited, stats = self._run(walk_entries, readme_exists_map, readme_content_map)

        self.assertIn(parent, visited, "parent with aikb should be processed")
        self.assertIn(child, visited, "child of parent with aikb should be visited")
        self.assertEqual(stats["dirs_skipped"], 0)


class TestGitFatalError(unittest.TestCase):
    """Test GitFatalError is raised on critical git errors and stops processing"""

    def setUp(self):
        """Reset GitManager module-level state before each test"""
        docs2md._git_manager = None
        docs2md._git_manager_error = False

    def _config(self):
        return {
            "git_commit": True,
            "git_url": "https://gitlab.example.com/proj/-/tree/main",
            "root_folder": "/root",
        }

    # ------------------------------------------------------------------
    # sync_to_git raises GitFatalError on missing token
    # ------------------------------------------------------------------
    def test_sync_to_git_raises_on_missing_token(self):
        """GitFatalError is raised when GIT_ACCESS_TOKEN is not set (GitManager init fails)"""
        logger = Mock()
        config = self._config()
        with patch(
            "docs2md.GitManager", side_effect=ValueError("'GIT_ACCESS_TOKEN' not found")
        ):
            with self.assertRaises(docs2md.GitFatalError) as ctx:
                docs2md.sync_to_git("/root/file.md", config, logger)
        self.assertIn("GitManager", str(ctx.exception))
        logger.error.assert_called()

    # ------------------------------------------------------------------
    # sync_to_git raises GitFatalError on authentication failure
    # ------------------------------------------------------------------
    def test_sync_to_git_raises_on_auth_failure(self):
        """GitFatalError is raised when verify_path returns an authentication error"""
        logger = Mock()
        config = self._config()
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (
            False,
            {"error": "Authentication failed. Check your Git access token."},
        )
        with patch("docs2md.GitManager", return_value=mock_gm):
            with self.assertRaises(docs2md.GitFatalError) as ctx:
                docs2md.sync_to_git("/root/file.md", config, logger)
        self.assertIn("Authentication failed", str(ctx.exception))
        logger.error.assert_called()

    # ------------------------------------------------------------------
    # sync_to_git raises GitFatalError on invalid path
    # ------------------------------------------------------------------
    def test_sync_to_git_raises_on_invalid_path(self):
        """GitFatalError is raised when verify_path returns a path-not-found error"""
        logger = Mock()
        config = self._config()
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (
            False,
            {"error": "Path not found: /some/path"},
        )
        with patch("docs2md.GitManager", return_value=mock_gm):
            with self.assertRaises(docs2md.GitFatalError) as ctx:
                docs2md.sync_to_git("/root/file.md", config, logger)
        self.assertIn("Path not found", str(ctx.exception))

    # ------------------------------------------------------------------
    # sync_to_git raises GitFatalError when git_url is missing from config
    # ------------------------------------------------------------------
    def test_sync_to_git_raises_on_missing_git_url(self):
        """GitFatalError is raised when git_url is absent from config"""
        logger = Mock()
        config = {"git_commit": True, "root_folder": "/root"}  # no git_url
        with self.assertRaises(docs2md.GitFatalError) as ctx:
            docs2md.sync_to_git("/root/file.md", config, logger)
        self.assertIn("Git URL", str(ctx.exception))
        logger.error.assert_called()

    # ------------------------------------------------------------------
    # GitFatalError propagates through convert_to_markdown
    # ------------------------------------------------------------------
    @patch("subprocess.run")
    @patch("os.makedirs")
    def test_git_fatal_error_propagates_through_convert_to_markdown(
        self, mock_makedirs, mock_run
    ):
        """GitFatalError raised in sync_to_git is not swallowed by convert_to_markdown"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        logger = Mock()
        config = self._config()
        with patch(
            "docs2md.sync_to_git",
            side_effect=docs2md.GitFatalError("auth failed"),
        ):
            with self.assertRaises(docs2md.GitFatalError):
                docs2md.convert_to_markdown("/src.docx", "/dst.md", logger, config)

    # ------------------------------------------------------------------
    # main() catches GitFatalError and exits with code 1
    # ------------------------------------------------------------------
    def test_main_exits_on_git_fatal_error(self):
        """main() catches GitFatalError, logs the error, and calls sys.exit(1)"""
        with (
            patch(
                "docs2md.load_config",
                return_value={
                    "root_folder": "/root",
                    "git_commit": True,
                    "git_url": "https://gitlab.example.com/proj/-/tree/main",
                    "common": {},
                },
            ),
            patch("docs2md.verify_pandoc", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=True),
            patch(
                "docs2md.process_directories_recursively",
                side_effect=docs2md.GitFatalError("Authentication failed"),
            ),
            patch("sys.exit") as mock_exit,
        ):
            docs2md.main()
            mock_exit.assert_called_with(1)


class TestOutputLogFormatting(unittest.TestCase):
    """Test refined log output formatting"""

    # ------------------------------------------------------------------
    # process_directory: Processing: "<relative_path>"
    # ------------------------------------------------------------------
    def test_process_directory_logs_relative_path(self):
        """process_directory logs 'Processing: \"<rel_path>\"' using root_folder param"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = f"doc2md#aikb\n"

        with (
            patch("os.path.join", side_effect=os.path.join),
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=[]),
        ):
            docs2md.process_directory(
                "/root/subdir",
                config,
                logger,
                stats,
                important_logs=None,
                root_folder="/root",
            )

        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('Processing: "subdir"' in m for m in logged_msgs),
            f"Expected 'Processing: \"subdir\"' in logs, got: {logged_msgs}",
        )

    def test_process_directory_logs_dot_for_root_itself(self):
        """process_directory logs 'Processing: \".\"' when directory == root_folder"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\n"

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=[]),
        ):
            docs2md.process_directory(
                "/root", config, logger, stats, important_logs=None, root_folder="/root"
            )

        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('Processing: "."' in m for m in logged_msgs),
            f"Expected 'Processing: \".\"' in logs, got: {logged_msgs}",
        )

    # ------------------------------------------------------------------
    # process_directories_recursively: skipped dir uses relative path
    # ------------------------------------------------------------------
    def test_skipped_dir_log_uses_relative_path(self):
        """Skipped dir log shows relative path in quotes, not full absolute path"""
        logger = Mock()
        config = {}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        walk_entries = [("/root/sub1", [], [])]

        with (
            patch("docs2md.os.walk", return_value=iter(walk_entries)),
            patch("docs2md.os.path.exists", return_value=False),
        ):
            docs2md.process_directories_recursively("/root", config, logger, stats)

        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        # Should contain relative path in quotes, NOT full absolute path as-is
        self.assertTrue(
            any('"sub1"' in m for m in logged_msgs),
            f"Expected '\"sub1\"' in skipped log, got: {logged_msgs}",
        )
        self.assertFalse(
            any("subdirectories will not be traversed" in m for m in logged_msgs),
            "Old format 'subdirectories will not be traversed' should not appear",
        )

    # ------------------------------------------------------------------
    # filter_files_by_readme: filenames use relative path when rel_dir provided
    # ------------------------------------------------------------------
    def test_filter_files_skipped_log_uses_quotes(self):
        """Skipped file log contains filename in double quotes at DEBUG level (no rel_dir — bare name)"""
        logger = Mock()
        files = ["orphan.docx"]
        content = "doc2md#aikb\nsome other content"
        docs2md.filter_files_by_readme(files, content, False, logger)
        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('"orphan.docx"' in m for m in logged_msgs),
            f"Expected '\"orphan.docx\"' in debug logs, got: {logged_msgs}",
        )

    def test_filter_files_skipfile_log_uses_quotes(self):
        """Skipfile log contains filename in double quotes at DEBUG level (no rel_dir — bare name)"""
        logger = Mock()
        files = ["skip_me.docx"]
        content = "doc2md#aikb\nskip_me.docx doc2md#skipfile"
        docs2md.filter_files_by_readme(files, content, True, logger)
        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('"skip_me.docx"' in m for m in logged_msgs),
            f"Expected '\"skip_me.docx\"' in debug logs, got: {logged_msgs}",
        )

    def test_filter_files_skipped_log_uses_relative_path(self):
        """Skipped file log uses rel_dir/filename at DEBUG level when rel_dir is provided"""
        logger = Mock()
        files = ["orphan.docx"]
        content = "doc2md#aikb\nsome other content"
        docs2md.filter_files_by_readme(
            files, content, False, logger, rel_dir="subs/sub1"
        )
        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('"subs/sub1' in m and "orphan.docx" in m for m in logged_msgs),
            f"Expected relative path in debug skip log, got: {logged_msgs}",
        )

    def test_filter_files_skipfile_log_uses_relative_path(self):
        """Skipfile log uses rel_dir/filename at DEBUG level when rel_dir is provided"""
        logger = Mock()
        files = ["skip_me.docx"]
        content = "doc2md#aikb\nskip_me.docx doc2md#skipfile"
        docs2md.filter_files_by_readme(
            files, content, True, logger, rel_dir="subs/sub1"
        )
        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('"subs/sub1' in m and "skip_me.docx" in m for m in logged_msgs),
            f"Expected relative path in debug skipfile log, got: {logged_msgs}",
        )

    # ------------------------------------------------------------------
    # convert_to_markdown: error log includes filename and command
    # ------------------------------------------------------------------
    @patch("subprocess.run")
    @patch("os.makedirs")
    def test_convert_to_markdown_error_log_includes_filename_and_command(
        self, mock_makedirs, mock_run
    ):
        """On pandoc failure, error log includes quoted source filename and pandoc command"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "couldn't unpack docx container"
        mock_run.return_value = mock_result
        logger = Mock()
        docs2md.convert_to_markdown(
            "/some/path/empty.docx", "/some/path/empty.md", logger
        )
        error_calls = [call.args[0] for call in logger.error.call_args_list]
        combined = "\n".join(error_calls)
        self.assertIn('"empty.docx"', combined)
        self.assertIn("Command:", combined)
        self.assertIn("pandoc", combined)

    # ------------------------------------------------------------------
    # process_directory: per-file log uses relative path (subdir case)
    # ------------------------------------------------------------------
    def test_process_directory_file_log_uses_quotes(self):
        """Per-file log uses bare filename when directory == root_folder"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\ntest.txt"

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=["test.txt"]),
            patch("docs2md.process_file", return_value=(True, "MD generated")),
        ):
            docs2md.process_directory(
                "/root", config, logger, stats, important_logs=[], root_folder="/root"
            )

        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertTrue(
            any('"test.txt"' in m for m in logged_msgs),
            f"Expected '\"test.txt\"' in logs, got: {logged_msgs}",
        )

    def test_process_directory_file_log_uses_relative_path_for_subdir(self):
        """Per-file log uses rel_dir/filename when directory is a subdirectory of root"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\nsub-text.txt"

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=["sub-text.txt"]),
            patch("docs2md.process_file", return_value=(True, "MD generated")),
        ):
            docs2md.process_directory(
                "/root/subs/sub",
                config,
                logger,
                stats,
                important_logs=[],
                root_folder="/root",
            )

        logged_msgs = [call.args[0] for call in logger.debug.call_args_list]
        # Should log relative path like "subs\sub\sub-text.txt" (or subs/sub/sub-text.txt)
        self.assertTrue(
            any("subs" in m and "sub-text.txt" in m for m in logged_msgs),
            f"Expected relative path with 'subs' and 'sub-text.txt' in logs, got: {logged_msgs}",
        )

    # ------------------------------------------------------------------
    # important_logs: no path suffix, quoted filenames
    # ------------------------------------------------------------------
    def test_important_logs_no_directory_suffix(self):
        """important_logs entries contain quoted filename but no 'in <directory>' suffix"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\ntest.txt"
        important_logs = []

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=["test.txt"]),
            patch("docs2md.process_file", return_value=(True, "MD generated")),
        ):
            docs2md.process_directory(
                "/root",
                config,
                logger,
                stats,
                important_logs=important_logs,
                root_folder="/root",
            )

        self.assertEqual(len(important_logs), 1)
        self.assertIn('"test.txt"', important_logs[0])
        self.assertNotIn(" in /root", important_logs[0])
        self.assertNotIn(" in C:\\", important_logs[0])

    def test_important_logs_error_no_directory_suffix(self):
        """important_logs error entries contain quoted filename but no 'in <directory>' suffix"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\nbad.docx"
        important_logs = []

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=["bad.docx"]),
            patch(
                "docs2md.process_file", return_value=(False, "Error: something failed")
            ),
        ):
            docs2md.process_directory(
                "/root",
                config,
                logger,
                stats,
                important_logs=important_logs,
                root_folder="/root",
            )

        self.assertEqual(len(important_logs), 1)
        self.assertIn("ERROR:", important_logs[0])
        self.assertIn('"bad.docx"', important_logs[0])
        self.assertNotIn(" in /root", important_logs[0])

    # ------------------------------------------------------------------
    # main(): Files path and Git path in start logs
    # ------------------------------------------------------------------
    def test_main_logs_files_path_with_quotes(self):
        """main() logs 'Files path: \"<path>\"' instead of 'Root: <path>'"""
        captured_logs = []

        def fake_info(msg):
            captured_logs.append(msg)

        mock_logger = Mock()
        mock_logger.info.side_effect = fake_info

        with (
            patch(
                "docs2md.load_config",
                return_value={
                    "root_folder": "/test/root",
                    "git_commit": False,
                    "common": {},
                },
            ),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=True),
            patch("docs2md.process_directories_recursively"),
        ):
            docs2md.main()

        self.assertTrue(
            any("Files path:" in m and '"/test/root"' in m for m in captured_logs),
            f"Expected 'Files path: \"/test/root\"' in logs, got: {captured_logs}",
        )
        self.assertFalse(
            any(m.startswith("Root:") for m in captured_logs),
            "Old 'Root:' prefix should not appear",
        )

    def test_main_logs_git_path_when_git_commit_enabled(self):
        """main() logs 'Git path: \"<url>\"' when git_commit is True"""
        captured_logs = []

        def fake_info(msg):
            captured_logs.append(msg)

        mock_logger = Mock()
        mock_logger.info.side_effect = fake_info

        with (
            patch(
                "docs2md.load_config",
                return_value={
                    "root_folder": "/test/root",
                    "git_commit": True,
                    "git_url": "https://gitlab.example.com/proj/-/tree/main/docs",
                    "common": {},
                },
            ),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=True),
            patch("docs2md.process_directories_recursively"),
        ):
            docs2md.main()

        self.assertTrue(
            any("Git path:" in m and "gitlab.example.com" in m for m in captured_logs),
            f"Expected 'Git path: \"...\"' in logs, got: {captured_logs}",
        )

    def test_main_does_not_log_git_path_when_git_commit_disabled(self):
        """main() does NOT log 'Git path:' when git_commit is False"""
        captured_logs = []

        def fake_info(msg):
            captured_logs.append(msg)

        mock_logger = Mock()
        mock_logger.info.side_effect = fake_info

        with (
            patch(
                "docs2md.load_config",
                return_value={
                    "root_folder": "/test/root",
                    "git_commit": False,
                    "common": {},
                },
            ),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=True),
            patch("docs2md.process_directories_recursively"),
        ):
            docs2md.main()

        self.assertFalse(
            any("Git path:" in m for m in captured_logs),
            f"'Git path:' should not appear when git_commit is False, got: {captured_logs}",
        )

    # ------------------------------------------------------------------
    # SUMMARY: blank line and header are separate log calls (no embedded \n)
    # ------------------------------------------------------------------
    def test_summary_blank_line_is_separate_log_call(self):
        """SUMMARY blank line separator is a standalone logger.info('') call, not embedded \\n"""
        captured_logs = []

        def fake_info(msg):
            captured_logs.append(msg)

        mock_logger = Mock()
        mock_logger.info.side_effect = fake_info

        with (
            patch(
                "docs2md.load_config",
                return_value={
                    "root_folder": "/test/root",
                    "git_commit": False,
                    "common": {},
                },
            ),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=True),
            patch("docs2md.process_directories_recursively"),
        ):
            docs2md.main()

        # "SUMMARY:" must appear as its own clean log entry (no leading \n)
        self.assertIn(
            "SUMMARY:",
            captured_logs,
            "'SUMMARY:' must be a standalone log entry without embedded newline",
        )
        # The blank separator must also be its own entry
        summary_idx = captured_logs.index("SUMMARY:")
        self.assertGreater(summary_idx, 0)
        self.assertEqual(
            captured_logs[summary_idx - 1],
            "",
            "The entry immediately before 'SUMMARY:' must be a blank '' log call",
        )

    def test_detailed_changes_blank_line_is_separate_log_call(self):
        """'Change log:' blank line separator is standalone, no embedded \\n"""
        captured_logs = []

        def fake_info(msg):
            captured_logs.append(msg)

        mock_logger = Mock()
        mock_logger.info.side_effect = fake_info

        with (
            patch(
                "docs2md.load_config",
                return_value={
                    "root_folder": "/test/root",
                    "git_commit": False,
                    "common": {},
                },
            ),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=True),
            patch(
                "docs2md.process_directories_recursively",
                side_effect=lambda *a, **kw: a[4].append('"test.txt" MD generated'),
            ),
        ):
            docs2md.main()

        self.assertIn(
            "Change log:",
            captured_logs,
            "'Change log:' must be a standalone log entry without embedded newline",
        )
        dc_idx = captured_logs.index("Change log:")
        self.assertGreater(dc_idx, 0)
        self.assertEqual(
            captured_logs[dc_idx - 1],
            "",
            "The entry immediately before 'Change log:' must be a blank '' log call",
        )

    # ------------------------------------------------------------------
    # filter_files_by_readme: skip logs must NOT appear at INFO level
    # ------------------------------------------------------------------
    def test_filter_files_skip_not_in_readme_is_debug_not_info(self):
        """'Skipped due to not listed in README' must log at DEBUG, not INFO"""
        logger = Mock()
        files = ["orphan.docx"]
        content = "doc2md#aikb\nsome other content"
        docs2md.filter_files_by_readme(files, content, False, logger)
        info_msgs = [call.args[0] for call in logger.info.call_args_list]
        self.assertFalse(
            any("orphan.docx" in m for m in info_msgs),
            f"Skip message must not appear at INFO level, got: {info_msgs}",
        )

    def test_filter_files_skipfile_tag_is_debug_not_info(self):
        """'Skipped due to skipfile tag' must log at DEBUG, not INFO"""
        logger = Mock()
        files = ["skip_me.docx"]
        content = "doc2md#aikb\nskip_me.docx doc2md#skipfile"
        docs2md.filter_files_by_readme(files, content, True, logger)
        info_msgs = [call.args[0] for call in logger.info.call_args_list]
        self.assertFalse(
            any("skip_me.docx" in m for m in info_msgs),
            f"Skipfile message must not appear at INFO level, got: {info_msgs}",
        )

    # ------------------------------------------------------------------
    # Verbose/duplicate messages must be DEBUG, not INFO
    # ------------------------------------------------------------------
    def test_file_success_message_is_debug_not_info(self):
        """Per-file success message must be logged at DEBUG, not INFO"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\ntest.txt"

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=["test.txt"]),
            patch("docs2md.process_file", return_value=(True, "MD generated")),
        ):
            docs2md.process_directory(
                "/root", config, logger, stats, important_logs=[], root_folder="/root"
            )

        info_msgs = [call.args[0] for call in logger.info.call_args_list]
        debug_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertFalse(
            any("MD generated" in m for m in info_msgs),
            f"Success message must not appear at INFO, got: {info_msgs}",
        )
        self.assertTrue(
            any("MD generated" in m for m in debug_msgs),
            f"Success message must appear at DEBUG, got: {debug_msgs}",
        )

    def test_file_error_message_is_info_not_debug(self):
        """Per-file error message must be logged at INFO, not only DEBUG"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\nbad.docx"

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=["bad.docx"]),
            patch("docs2md.process_file", return_value=(False, "Error: pandoc failed")),
        ):
            docs2md.process_directory(
                "/root", config, logger, stats, important_logs=[], root_folder="/root"
            )

        info_msgs = [call.args[0] for call in logger.info.call_args_list]
        self.assertTrue(
            any("Error:" in m for m in info_msgs),
            f"Error message must appear at INFO, got: {info_msgs}",
        )

    def test_processing_dir_message_is_debug_not_info(self):
        """'Processing: ...' message must be logged at DEBUG, not INFO"""
        logger = Mock()
        config = {"force_md_generation": False, "git_commit": False}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        readme_content = "doc2md#aikb\n"

        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme_content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=[]),
        ):
            docs2md.process_directory(
                "/root", config, logger, stats, root_folder="/root"
            )

        info_msgs = [call.args[0] for call in logger.info.call_args_list]
        debug_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertFalse(
            any("Processing" in m for m in info_msgs),
            f"'Processing' must not appear at INFO, got: {info_msgs}",
        )
        self.assertTrue(
            any("Processing" in m for m in debug_msgs),
            f"'Processing' must appear at DEBUG, got: {debug_msgs}",
        )

    def test_skipped_dir_recursive_is_debug_not_info(self):
        """Skipped directory messages in recursive walk must be DEBUG, not INFO"""
        logger = Mock()
        config = {}
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }
        walk_entries = [("/root/noreadme", [], [])]

        with (
            patch("docs2md.os.walk", return_value=iter(walk_entries)),
            patch("docs2md.os.path.exists", return_value=False),
        ):
            docs2md.process_directories_recursively("/root", config, logger, stats)

        info_msgs = [call.args[0] for call in logger.info.call_args_list]
        debug_msgs = [call.args[0] for call in logger.debug.call_args_list]
        self.assertFalse(
            any("Skipped" in m for m in info_msgs),
            f"Skipped dir message must not appear at INFO, got: {info_msgs}",
        )
        self.assertTrue(
            any("Skipped" in m for m in debug_msgs),
            f"Skipped dir message must appear at DEBUG, got: {debug_msgs}",
        )


if __name__ == "__main__":
    unittest.main()
