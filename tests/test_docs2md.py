"""
Unit tests for docs2md — behavior-based, minimal code, maximum coverage.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import docs2md


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_stats():
    return {
        "dirs_processed": 0,
        "dirs_skipped": 0,
        "files_generated": 0,
        "files_committed": 0,
        "files_skipped": 0,
        "files_errors": 0,
        "files_git_identical": 0,
    }


def _make_config(**overrides):
    base = {
        "root_folder": "/root",
        "git_commit": False,
        "force_md_generation": False,
        "common": {},
    }
    base.update(overrides)
    return base


def _make_git_config(**overrides):
    base = {
        "root_folder": "/root",
        "git_commit": True,
        "git_url": "https://gitlab.example.com/proj/-/tree/main/docs",
        "force_md_generation": False,
    }
    base.update(overrides)
    return base


README_AIKB = f"# Title\n{docs2md.TAG_AIKB}\n"


# ---------------------------------------------------------------------------
# 1. Config & logging
# ---------------------------------------------------------------------------


class TestConfig(unittest.TestCase):
    """load_config, setup_logging, verify_pandoc, get_supported_extensions"""

    def test_setup_logging_returns_named_logger_with_handlers(self):
        logger = docs2md.setup_logging()
        self.assertEqual(logger.name, "docs2md")
        self.assertEqual(len(logger.handlers), 2)

    def test_load_config_success(self):
        with (
            patch(
                "builtins.open",
                new_callable=mock_open,
                read_data="root_folder: /test\n",
            ),
            patch("yaml.safe_load", return_value={"root_folder": "/test"}),
        ):
            config = docs2md.load_config()
        self.assertIn("root_folder", config)

    def test_load_config_missing_file_raises(self):
        with patch("builtins.open", side_effect=FileNotFoundError()):
            with self.assertRaises(Exception) as ctx:
                docs2md.load_config()
        self.assertIn("not found", str(ctx.exception))

    def test_load_config_yaml_error_raises(self):
        import yaml

        with patch("builtins.open", new_callable=mock_open, read_data="bad: [yaml"):
            with patch("yaml.safe_load", side_effect=yaml.YAMLError("bad")):
                with self.assertRaises(Exception) as ctx:
                    docs2md.load_config()
        self.assertIn("parse", str(ctx.exception))

    def test_verify_pandoc_success(self):
        mock_result = Mock(returncode=0, stdout="pandoc 3.0")
        with patch("subprocess.run", return_value=mock_result):
            self.assertTrue(docs2md.verify_pandoc())

    def test_verify_pandoc_not_installed(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            self.assertFalse(docs2md.verify_pandoc())

    def test_verify_pandoc_nonzero_returncode(self):
        mock_result = Mock(returncode=1, stderr="error", stdout="")
        with patch("subprocess.run", return_value=mock_result):
            self.assertFalse(docs2md.verify_pandoc())

    def test_get_supported_extensions_from_config(self):
        config = {"common": {"supported_extensions": [".docx", ".pdf"]}}
        self.assertEqual(docs2md.get_supported_extensions(config), {".docx", ".pdf"})

    def test_get_supported_extensions_fallback_none(self):
        self.assertIs(
            docs2md.get_supported_extensions(None),
            docs2md.DEFAULT_SUPPORTED_EXTENSIONS,
        )

    def test_get_supported_extensions_fallback_empty_dict(self):
        self.assertIs(
            docs2md.get_supported_extensions({}),
            docs2md.DEFAULT_SUPPORTED_EXTENSIONS,
        )

    def test_get_supported_extensions_fallback_empty_common(self):
        self.assertIs(
            docs2md.get_supported_extensions({"common": {}}),
            docs2md.DEFAULT_SUPPORTED_EXTENSIONS,
        )


# ---------------------------------------------------------------------------
# 1b. load_config — active_project resolution
# ---------------------------------------------------------------------------


class TestLoadConfigActiveProject(unittest.TestCase):
    """load_config multi-project format: active_project resolution"""

    def _load_with_yaml(self, raw: dict):
        with (
            patch("builtins.open", new_callable=mock_open, read_data=""),
            patch("yaml.safe_load", return_value=raw),
        ):
            return docs2md.load_config()

    def test_active_project_keys_merged_to_top_level(self):
        raw = {
            "active_project": "fa",
            "fa": {"root_folder": "/fa", "git_commit": True, "git_url": "http://fa"},
            "other": {"root_folder": "/other"},
            "common": {"log_level": "INFO"},
        }
        config = self._load_with_yaml(raw)
        self.assertEqual(config["root_folder"], "/fa")
        self.assertTrue(config["git_commit"])
        self.assertEqual(config["git_url"], "http://fa")

    def test_active_project_preserved_in_result(self):
        raw = {
            "active_project": "fa",
            "fa": {"root_folder": "/fa"},
        }
        config = self._load_with_yaml(raw)
        self.assertEqual(config["active_project"], "fa")

    def test_inactive_project_not_in_result(self):
        raw = {
            "active_project": "fa",
            "fa": {"root_folder": "/fa"},
            "other": {"root_folder": "/other"},
        }
        config = self._load_with_yaml(raw)
        self.assertNotIn("other", config)

    def test_invalid_active_project_raises(self):
        raw = {
            "active_project": "nonexistent",
            "fa": {"root_folder": "/fa"},
        }
        with self.assertRaises(Exception) as ctx:
            self._load_with_yaml(raw)
        self.assertIn("nonexistent", str(ctx.exception))

    def test_invalid_active_project_lists_available_projects(self):
        """Error message for wrong active_project should list available project names"""
        raw = {
            "active_project": "psaasa",
            "proj1": {"root_folder": "/p1"},
            "proj2": {"root_folder": "/p2"},
            "common": {"log_level": "INFO"},
        }
        with self.assertRaises(Exception) as ctx:
            self._load_with_yaml(raw)
        msg = str(ctx.exception)
        self.assertIn("psaasa", msg)
        self.assertIn("proj1", msg)
        self.assertIn("proj2", msg)
        self.assertIn("Available projects", msg)

    def test_no_active_project_returns_legacy_flat_config(self):
        raw = {"root_folder": "/flat", "git_commit": False}
        config = self._load_with_yaml(raw)
        self.assertEqual(config["root_folder"], "/flat")
        self.assertNotIn("active_project", config)

    def test_common_section_preserved_after_merge(self):
        raw = {
            "active_project": "fa",
            "fa": {"root_folder": "/fa"},
            "common": {"log_level": "DEBUG", "pause_before_exit": True},
        }
        config = self._load_with_yaml(raw)
        self.assertEqual(config["common"]["log_level"], "DEBUG")


# ---------------------------------------------------------------------------
# 2. README parsing (tags, masks, filtering)
# ---------------------------------------------------------------------------


class TestReadmeParsing(unittest.TestCase):
    """read_readme, check_aikb_tag, extract_masks, has_skipfile_tag,
    is_file_referenced_in_readme, get_file_reference_line, filter_files_by_readme"""

    def test_read_readme_success(self):
        with patch("builtins.open", new_callable=mock_open, read_data="content"):
            self.assertEqual(docs2md.read_readme("/p/README.md"), "content")

    def test_read_readme_error_returns_none(self):
        with patch("builtins.open", side_effect=Exception("err")):
            self.assertIsNone(docs2md.read_readme("/p/README.md"))

    def test_check_aikb_tag(self):
        self.assertTrue(docs2md.check_aikb_tag("doc2md#aikb"))
        self.assertFalse(docs2md.check_aikb_tag("no tag"))
        self.assertFalse(docs2md.check_aikb_tag(None))

    def test_glob_to_regex(self):
        """glob_to_regex converts wildcard patterns to regex equivalents"""
        import re, fnmatch

        # * matches any chars including none
        pattern = docs2md.glob_to_regex("*.docx")
        self.assertTrue(re.match(pattern, "report.docx", re.IGNORECASE))
        self.assertTrue(re.match(pattern, "Transcript - meeting.docx", re.IGNORECASE))
        self.assertFalse(re.match(pattern, "report.xlsx", re.IGNORECASE))
        # ? matches exactly one char
        pattern2 = docs2md.glob_to_regex("file?.docx")
        self.assertTrue(re.match(pattern2, "fileA.docx", re.IGNORECASE))
        self.assertFalse(re.match(pattern2, "file.docx", re.IGNORECASE))

    def test_extract_masks(self):
        """extract_masks converts glob patterns to regex"""
        import fnmatch

        content = "doc2md#mask='*.docx'\ndoc2md#mask='test*'"
        masks = docs2md.extract_masks(content)
        self.assertEqual(len(masks), 2)
        self.assertIn(fnmatch.translate("*.docx"), masks)
        self.assertIn(fnmatch.translate("test*"), masks)

    def test_extract_masks_no_quotes(self):
        """extract_masks works without quotes around the pattern"""
        import fnmatch

        content = "doc2md#mask=*Transcript.docx - some comment"
        masks = docs2md.extract_masks(content)
        self.assertEqual(len(masks), 1)
        self.assertIn(fnmatch.translate("*Transcript.docx"), masks)

    def test_extract_masks_empty(self):
        self.assertEqual(docs2md.extract_masks("no masks"), [])
        self.assertEqual(docs2md.extract_masks(None), [])

    def test_has_skipfile_tag(self):
        self.assertTrue(docs2md.has_skipfile_tag("file.docx doc2md#skipfile"))
        self.assertFalse(docs2md.has_skipfile_tag("file.docx"))

    def test_file_referenced_in_readme(self):
        self.assertTrue(
            docs2md.is_file_referenced_in_readme("test.docx", "See test.docx here")
        )
        self.assertFalse(
            docs2md.is_file_referenced_in_readme("test.docx", "See other.docx here")
        )
        self.assertFalse(docs2md.is_file_referenced_in_readme("test.docx", None))

    def test_get_file_reference_line(self):
        content = "Line 1\nSee test.docx here\nLine 3"
        line = docs2md.get_file_reference_line("test.docx", content)
        self.assertIsNotNone(line)
        self.assertIn("test.docx", line or "")
        self.assertIsNone(docs2md.get_file_reference_line("missing.docx", content))
        self.assertIsNone(docs2md.get_file_reference_line("test.docx", None))

    def test_filter_files_keeps_referenced(self):
        result = docs2md.filter_files_by_readme(
            ["test.docx", "other.docx"], "test.docx referenced", False, Mock()
        )
        self.assertIn("test.docx", result)
        self.assertNotIn("other.docx", result)

    def test_filter_files_removes_skipfile(self):
        result = docs2md.filter_files_by_readme(
            ["test.docx"], "test.docx doc2md#skipfile", True, Mock()
        )
        self.assertEqual(result, [])

    def test_filter_files_keeps_all_when_masks_active(self):
        """With masks, unreferenced files are still kept (mask already filtered them)"""
        result = docs2md.filter_files_by_readme(
            ["test.docx"], "doc2md#aikb", True, Mock()
        )
        self.assertIn("test.docx", result)

    def test_filter_files_skip_logged_at_debug_not_info(self):
        logger = Mock()
        docs2md.filter_files_by_readme(["orphan.docx"], "doc2md#aikb", False, logger)
        info_msgs = [c.args[0] for c in logger.info.call_args_list]
        self.assertFalse(any("orphan.docx" in m for m in info_msgs))


# ---------------------------------------------------------------------------
# 3. File selection (collect, apply_masks, target path, is_source_newer)
# ---------------------------------------------------------------------------


class TestFileSelection(unittest.TestCase):
    """collect_files_in_directory, apply_masks, get_target_md_path, is_source_newer"""

    @patch("os.listdir", return_value=["a.docx", "b.txt", "c.xyz_unknown"])
    @patch("os.path.isfile", return_value=True)
    def test_collect_files_uses_default_extensions(self, *_):
        files = docs2md.collect_files_in_directory("/test")
        self.assertIn("a.docx", files)
        self.assertNotIn("c.xyz_unknown", files)

    @patch("os.listdir", return_value=["a.custom", "b.docx"])
    @patch("os.path.isfile", return_value=True)
    def test_collect_files_uses_config_extensions(self, *_):
        config = {"common": {"supported_extensions": [".custom"]}}
        files = docs2md.collect_files_in_directory("/test", config)
        self.assertIn("a.custom", files)
        self.assertNotIn("b.docx", files)

    @patch("os.listdir", side_effect=Exception("denied"))
    def test_collect_files_error_returns_empty(self, *_):
        self.assertEqual(docs2md.collect_files_in_directory("/test"), [])

    def test_apply_masks_filters(self):
        import fnmatch

        files = ["test.docx", "report.docx"]
        masks = [fnmatch.translate("test*.docx")]
        self.assertEqual(docs2md.apply_masks(files, masks), ["test.docx"])

    def test_apply_masks_no_masks_returns_all(self):
        files = ["a.docx", "b.docx"]
        self.assertEqual(docs2md.apply_masks(files, []), files)

    def test_apply_masks_invalid_regex_skipped(self):
        result = docs2md.apply_masks(["test.docx"], ["[invalid"])
        self.assertEqual(result, [])

    @patch("os.listdir", return_value=[])
    def test_get_target_md_path_simple(self, *_):
        result = docs2md.get_target_md_path("test.docx", "/dir")
        self.assertTrue(result.endswith("test.md"))

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.exists", return_value=False)
    @patch("os.listdir", return_value=["test.xlsx", "test.docx"])
    def test_get_target_md_path_name_conflict(self, *_):
        result = docs2md.get_target_md_path("test.docx", "/dir")
        self.assertTrue(result.endswith("test_docx.md"))

    @patch("os.path.getmtime", side_effect=[2000, 1000])
    def test_is_source_newer_true(self, *_):
        self.assertTrue(docs2md.is_source_newer("/src", "/dst"))

    @patch("os.path.getmtime", side_effect=[1000, 2000])
    def test_is_source_newer_false(self, *_):
        self.assertFalse(docs2md.is_source_newer("/src", "/dst"))

    @patch("os.path.getmtime", side_effect=OSError("no file"))
    def test_is_source_newer_error_returns_true(self, *_):
        # on error, assume source is newer (safe default: regenerate)
        self.assertTrue(docs2md.is_source_newer("/src", "/dst"))


# ---------------------------------------------------------------------------
# 4. Conversion (convert_to_markdown + process_file)
# ---------------------------------------------------------------------------


class TestConversion(unittest.TestCase):
    """convert_to_markdown and process_file — all outcomes"""

    def setUp(self):
        self.logger = Mock()
        self.config = _make_config()

    @patch("subprocess.run", return_value=Mock(returncode=0, stdout=""))
    @patch("os.makedirs")
    def test_convert_success(self, *_):
        ok, msg = docs2md.convert_to_markdown("/src.docx", "/dst.md", self.logger)
        self.assertTrue(ok)
        self.assertIn("generated", msg)

    @patch("subprocess.run", return_value=Mock(returncode=1, stderr="pandoc error"))
    @patch("os.makedirs")
    def test_convert_failure(self, *_):
        ok, msg = docs2md.convert_to_markdown("/src.docx", "/dst.md", self.logger)
        self.assertFalse(ok)
        self.assertIn("Error", msg)

    @patch("subprocess.run", return_value=Mock(returncode=1, stderr="pandoc error"))
    @patch("os.makedirs")
    def test_convert_failure_log_includes_filename_and_command(self, *_):
        docs2md.convert_to_markdown("/path/bad.docx", "/path/bad.md", self.logger)
        combined = "\n".join(c.args[0] for c in self.logger.error.call_args_list)
        self.assertIn('"bad.docx"', combined)
        self.assertIn("pandoc", combined)

    @patch("subprocess.run", side_effect=Exception("crash"))
    @patch("os.makedirs")
    def test_convert_unexpected_exception(self, *_):
        ok, msg = docs2md.convert_to_markdown("/src.docx", "/dst.md", self.logger)
        self.assertFalse(ok)

    @patch("subprocess.run", return_value=Mock(returncode=0, stdout=""))
    @patch("os.makedirs")
    def test_convert_with_git_sync(self, *_):
        config = _make_git_config()
        with patch("docs2md.sync_to_git", return_value=True) as mock_sync:
            ok, msg = docs2md.convert_to_markdown(
                "/src.docx", "/dst.md", self.logger, config
            )
        self.assertTrue(ok)
        self.assertIn("git", msg)
        mock_sync.assert_called_once()

    @patch("subprocess.run", return_value=Mock(returncode=0, stdout=""))
    @patch("os.makedirs")
    def test_convert_with_git_identical_has_suffix(self, *_):
        """When sync_to_git returns 'no_change', message must contain 'git identical'."""
        config = _make_git_config()
        with patch("docs2md.sync_to_git", return_value="no_change"):
            ok, msg = docs2md.convert_to_markdown(
                "/src.docx", "/dst.md", self.logger, config
            )
        self.assertTrue(ok)
        self.assertIn("git identical", msg)

    @patch("subprocess.run", return_value=Mock(returncode=0, stdout=""))
    @patch("os.makedirs")
    def test_convert_git_fatal_error_propagates(self, *_):
        config = _make_git_config()
        with patch("docs2md.sync_to_git", side_effect=docs2md.GitFatalError("auth")):
            with self.assertRaises(docs2md.GitFatalError):
                docs2md.convert_to_markdown("/src.docx", "/dst.md", self.logger, config)

    @patch("docs2md.convert_to_markdown", return_value=(True, "MD generated"))
    @patch("docs2md.get_target_md_path", return_value="/dir/test.md")
    @patch("os.path.exists", return_value=False)
    def test_process_file_new(self, *_):
        ok, msg = docs2md.process_file(
            "test.docx", "/dir", False, self.logger, self.config
        )
        self.assertTrue(ok)

    @patch("docs2md.is_source_newer", return_value=False)
    @patch("docs2md.get_target_md_path", return_value="/dir/test.md")
    @patch("os.path.exists", return_value=True)
    def test_process_file_up_to_date_skipped(self, *_):
        ok, msg = docs2md.process_file(
            "test.docx", "/dir", False, self.logger, self.config
        )
        self.assertIsNone(ok)
        self.assertIn("Skipped", msg)

    @patch("docs2md.convert_to_markdown", return_value=(True, "MD generated"))
    @patch("docs2md.is_source_newer", return_value=False)
    @patch("docs2md.get_target_md_path", return_value="/dir/test.md")
    @patch("os.path.exists", return_value=True)
    def test_process_file_force_regenerates(self, *_):
        ok, _ = docs2md.process_file(
            "test.docx", "/dir", True, self.logger, self.config
        )
        self.assertTrue(ok)

    @patch("docs2md.convert_to_markdown", return_value=(True, "MD generated"))
    @patch("docs2md.is_source_newer", return_value=True)
    @patch("docs2md.get_target_md_path", return_value="/dir/test.md")
    @patch("os.path.exists", return_value=True)
    def test_process_file_outdated_regenerates(self, *_):
        ok, _ = docs2md.process_file(
            "test.docx", "/dir", False, self.logger, self.config
        )
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# 5. Directory processing (process_directory)
# ---------------------------------------------------------------------------


class TestProcessDirectory(unittest.TestCase):
    """process_directory — all branches: skip, process, file outcomes"""

    def setUp(self):
        self.logger = Mock()
        self.config = _make_config()
        self.stats = _make_stats()

    def _run(
        self,
        directory="/root",
        readme_content=README_AIKB,
        files=None,
        file_result=(True, "MD generated"),
        important_logs=None,
        root_folder="/root",
    ):
        files = files or []
        # Ensure all test files are referenced in README so filter keeps them
        content = readme_content
        if files:
            content = content + "\n" + "\n".join(files)
        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=content),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch("docs2md.collect_files_in_directory", return_value=files),
            patch("docs2md.process_file", return_value=file_result),
        ):
            docs2md.process_directory(
                directory,
                self.config,
                self.logger,
                self.stats,
                important_logs,
                root_folder,
            )

    def test_skipped_when_no_readme(self):
        with patch("os.path.exists", return_value=False):
            docs2md.process_directory(
                "/root", self.config, self.logger, self.stats, root_folder="/root"
            )
        self.assertEqual(self.stats["dirs_skipped"], 1)
        self.assertEqual(self.stats["dirs_processed"], 0)

    def test_skipped_when_no_aikb_tag(self):
        self._run(readme_content="# No tag here")
        self.assertEqual(self.stats["dirs_skipped"], 1)
        self.assertEqual(self.stats["dirs_processed"], 0)

    def test_processed_with_aikb_tag(self):
        self._run(files=["test.docx"])
        self.assertEqual(self.stats["dirs_processed"], 1)
        self.assertEqual(self.stats["files_generated"], 1)

    def test_file_error_counted(self):
        self._run(files=["bad.docx"], file_result=(False, "Error: failed"))
        self.assertEqual(self.stats["files_errors"], 1)
        self.assertEqual(self.stats["files_generated"], 0)

    def test_file_skipped_counted(self):
        self._run(
            files=["up2date.docx"],
            file_result=(None, "Skipped due to MD is up to date"),
        )
        self.assertEqual(self.stats["files_skipped"], 1)

    def test_files_git_identical_counted(self):
        """When process_file returns success with 'git identical' in message, counter increments."""
        self._run(
            files=["same.docx"],
            file_result=(True, "MD generated, git identical"),
        )
        self.assertEqual(self.stats["files_generated"], 1)
        self.assertEqual(self.stats["files_git_identical"], 1)

    def test_important_logs_success(self):
        logs = []
        self._run(files=["test.docx"], important_logs=logs)
        self.assertEqual(len(logs), 1)
        self.assertIn('"test.docx"', logs[0])
        self.assertNotIn(" in /root", logs[0])

    def test_important_logs_error(self):
        logs = []
        self._run(
            files=["bad.docx"], file_result=(False, "Error: oops"), important_logs=logs
        )
        self.assertEqual(len(logs), 1)
        self.assertIn("ERROR:", logs[0])
        self.assertIn('"bad.docx"', logs[0])

    def test_readme_commit_log_includes_relative_path(self):
        """README commit log entry must include relative path, not just 'README.md'"""
        logs = []
        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=README_AIKB),
            patch("docs2md.sync_readme_to_git", return_value=True),
            patch("docs2md.collect_files_in_directory", return_value=[]),
        ):
            docs2md.process_directory(
                "/root/sub",
                self.config,
                self.logger,
                self.stats,
                logs,
                root_folder="/root",
            )
        self.assertEqual(len(logs), 1)
        self.assertIn("README.md", logs[0])
        self.assertIn("sub", logs[0])

    def test_logs_relative_path(self):
        self._run(directory="/root/sub", root_folder="/root")
        msgs = [c.args[0] for c in self.logger.debug.call_args_list]
        self.assertTrue(any('Processing: "sub"' in m for m in msgs))

    def test_logs_dot_for_root(self):
        self._run(directory="/root", root_folder="/root")
        msgs = [c.args[0] for c in self.logger.debug.call_args_list]
        self.assertTrue(any('Processing: "."' in m for m in msgs))

    def test_processing_logged_at_debug_not_info(self):
        self._run()
        info_msgs = [c.args[0] for c in self.logger.info.call_args_list]
        self.assertFalse(any("Processing" in m for m in info_msgs))

    def test_error_logged_at_info(self):
        self._run(files=["bad.docx"], file_result=(False, "Error: pandoc failed"))
        info_msgs = [c.args[0] for c in self.logger.info.call_args_list]
        self.assertTrue(any("Error:" in m for m in info_msgs))

    def test_masks_applied(self):
        readme = f"{docs2md.TAG_AIKB}\ndoc2md#mask='keep*'\nkeep.docx\ndrop.docx"
        with (
            patch("os.path.exists", return_value=True),
            patch("docs2md.read_readme", return_value=readme),
            patch("docs2md.sync_readme_to_git", return_value=False),
            patch(
                "docs2md.collect_files_in_directory",
                return_value=["keep.docx", "drop.docx"],
            ),
            patch(
                "docs2md.process_file", return_value=(True, "MD generated")
            ) as mock_pf,
        ):
            docs2md.process_directory(
                "/root", self.config, self.logger, self.stats, root_folder="/root"
            )
        processed = [c.args[0] for c in mock_pf.call_args_list]
        self.assertIn("keep.docx", processed)
        self.assertNotIn("drop.docx", processed)


# ---------------------------------------------------------------------------
# 6. Recursive directory walk (process_directories_recursively)
# ---------------------------------------------------------------------------


class TestRecursion(unittest.TestCase):
    """process_directories_recursively — pruning and visiting"""

    def setUp(self):
        self.logger = Mock()
        self.stats = _make_stats()

    def _run(self, walk_entries, exists_map, content_map):
        with (
            patch("docs2md.os.walk", return_value=iter(walk_entries)),
            patch(
                "docs2md.os.path.exists", side_effect=lambda p: exists_map.get(p, False)
            ),
            patch("docs2md.read_readme", side_effect=lambda p: content_map.get(p, "")),
            patch("docs2md.process_directory") as mock_pd,
        ):
            docs2md.process_directories_recursively(
                "/root", {}, self.logger, self.stats
            )
        return mock_pd

    def test_prunes_subdirs_when_no_readme(self):
        readme = os.path.join("/root/parent", docs2md.README_FILENAME)
        mock_pd = self._run(
            [("/root/parent", ["child"], []), ("/root/parent/child", [], [])],
            {readme: False},
            {},
        )
        self.assertEqual(mock_pd.call_count, 0)
        # parent is skipped; child is pruned so os.walk never yields it — 1 skip
        self.assertGreaterEqual(self.stats["dirs_skipped"], 1)

    def test_prunes_subdirs_when_no_aikb_tag(self):
        readme = os.path.join("/root/parent", docs2md.README_FILENAME)
        mock_pd = self._run(
            [("/root/parent", ["child"], []), ("/root/parent/child", [], [])],
            {readme: True},
            {readme: "# no tag"},
        )
        self.assertEqual(mock_pd.call_count, 0)

    def test_visits_both_when_aikb_present(self):
        p_readme = os.path.join("/root/parent", docs2md.README_FILENAME)
        c_readme = os.path.join("/root/parent/child", docs2md.README_FILENAME)
        mock_pd = self._run(
            [("/root/parent", ["child"], []), ("/root/parent/child", [], [])],
            {p_readme: True, c_readme: True},
            {p_readme: README_AIKB, c_readme: README_AIKB},
        )
        self.assertEqual(mock_pd.call_count, 2)

    def test_skipped_dir_logged_at_debug_not_info(self):
        readme = os.path.join("/root/sub", docs2md.README_FILENAME)
        self._run([("/root/sub", [], [])], {readme: False}, {})
        info_msgs = [c.args[0] for c in self.logger.info.call_args_list]
        self.assertFalse(any("Skipped" in m for m in info_msgs))


# ---------------------------------------------------------------------------
# 7. Git sync (sync_to_git — happy path + all error paths)
# ---------------------------------------------------------------------------


class TestGitSync(unittest.TestCase):
    """sync_to_git and sync_readme_to_git — full coverage of git logic"""

    def setUp(self):
        docs2md._git_manager = None
        docs2md._git_manager_error = False
        self.logger = Mock()

    def _git_config(self, **overrides):
        return _make_git_config(**overrides)

    # --- sync_to_git: disabled ---
    def test_sync_to_git_skipped_when_disabled(self):
        result = docs2md.sync_to_git("/f.md", _make_config(), self.logger)
        self.assertFalse(result)

    # --- sync_to_git: fatal errors ---
    def test_raises_when_git_url_missing(self):
        config = {"git_commit": True, "root_folder": "/root"}
        with self.assertRaises(docs2md.GitFatalError) as ctx:
            docs2md.sync_to_git("/root/f.md", config, self.logger)
        self.assertIn("Git URL", str(ctx.exception))

    def test_raises_when_git_manager_init_fails(self):
        with patch("docs2md.GitManager", side_effect=ValueError("no token")):
            with self.assertRaises(docs2md.GitFatalError):
                docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)

    def test_raises_when_verify_path_fails(self):
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (False, {"error": "Path not found"})
        with patch("docs2md.GitManager", return_value=mock_gm):
            with self.assertRaises(docs2md.GitFatalError) as ctx:
                docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)
        self.assertIn("Path not found", str(ctx.exception))

    def test_raises_when_auth_fails(self):
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (False, {"error": "Authentication failed"})
        with patch("docs2md.GitManager", return_value=mock_gm):
            with self.assertRaises(docs2md.GitFatalError) as ctx:
                docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)
        self.assertIn("Authentication failed", str(ctx.exception))

    # --- sync_to_git: happy path ---
    def test_sync_to_git_happy_path_returns_true(self):
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (True, {"contents_count": 1})
        mock_gm.push_commit_file.return_value = (True, {"message": "created"})
        with patch("docs2md.GitManager", return_value=mock_gm):
            result = docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)
        self.assertTrue(result)
        mock_gm.push_commit_file.assert_called_once()

    def test_sync_to_git_push_failure_returns_false(self):
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (True, {"contents_count": 1})
        mock_gm.push_commit_file.return_value = (False, {"error": "push failed"})
        with patch("docs2md.GitManager", return_value=mock_gm):
            result = docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)
        self.assertFalse(result)

    def test_sync_to_git_no_change_returns_no_change(self):
        """When remote file is identical, sync_to_git must return 'no_change'."""
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (True, {"contents_count": 1})
        mock_gm.push_commit_file.return_value = (
            True,
            {"message": "File is identical to remote file in git", "no_change": True},
        )
        with patch("docs2md.GitManager", return_value=mock_gm):
            result = docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)
        self.assertEqual(result, "no_change")

    def test_sync_to_git_child_path_strips_md_dir(self):
        """Files inside an 'md/' subdir should commit to the parent path"""
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (True, {})
        mock_gm.push_commit_file.return_value = (True, {"message": "ok"})
        with patch("docs2md.GitManager", return_value=mock_gm):
            docs2md.sync_to_git(
                "/root/subdir/md/f.md",
                self._git_config(root_folder="/root"),
                self.logger,
            )
        _, call_kwargs = mock_gm.push_commit_file.call_args
        child = call_kwargs.get("git_child_path", "")
        self.assertNotIn("md", child.split(os.sep))

    def test_git_manager_reused_across_calls(self):
        """GitManager must be initialized only once across multiple sync calls"""
        mock_gm = Mock()
        mock_gm.verify_path.return_value = (True, {})
        mock_gm.push_commit_file.return_value = (True, {"message": "ok"})
        config = self._git_config()
        with patch("docs2md.GitManager", return_value=mock_gm) as mock_cls:
            docs2md.sync_to_git("/root/f1.md", config, self.logger)
            docs2md.sync_to_git("/root/f2.md", config, self.logger)
        self.assertEqual(mock_cls.call_count, 1)

    def test_skips_when_previously_errored(self):
        docs2md._git_manager_error = True
        result = docs2md.sync_to_git("/root/f.md", self._git_config(), self.logger)
        self.assertFalse(result)

    # --- sync_readme_to_git ---
    def test_sync_readme_skipped_when_git_commit_false_force_true(self):
        docs2md._git_manager = None
        docs2md._git_manager_error = False
        config = _make_config(git_commit=False, force_readme_git_commit=True)
        self.assertFalse(
            docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        )

    def test_sync_readme_skipped_when_git_commit_true_force_false(self):
        docs2md._git_manager = None
        docs2md._git_manager_error = False
        config = _make_config(git_commit=True, force_readme_git_commit=False)
        self.assertFalse(
            docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        )

    def test_sync_readme_skipped_when_both_flags_false(self):
        docs2md._git_manager = None
        docs2md._git_manager_error = False
        config = _make_config(git_commit=False, force_readme_git_commit=False)
        self.assertFalse(
            docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        )

    def test_sync_readme_skipped_when_no_file(self):
        config = _make_config(git_commit=True, force_readme_git_commit=True)
        with patch("os.path.exists", return_value=False):
            self.assertFalse(
                docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
            )

    def test_sync_readme_skipped_when_no_aikb(self):
        config = _make_config(git_commit=True, force_readme_git_commit=True)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", new_callable=mock_open, read_data="no tag"),
        ):
            self.assertFalse(
                docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
            )

    def test_sync_readme_happy_path(self):
        config = _make_config(git_commit=True, force_readme_git_commit=True)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", new_callable=mock_open, read_data=README_AIKB),
            patch("docs2md.sync_to_git", return_value=True) as mock_sync,
        ):
            result = docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        self.assertTrue(result)
        mock_sync.assert_called_once()

    def test_sync_readme_read_error_returns_false(self):
        config = _make_config(git_commit=True, force_readme_git_commit=True)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", side_effect=IOError("denied")),
        ):
            self.assertFalse(
                docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
            )
        self.logger.error.assert_called()

    # --- sync_readme_to_git: mtime vs git commit time (force=False) ---

    def _readme_mtime_patches(self, local_mtime, git_epoch, git_success=True):
        """Helper: patch os.path.exists, open, os.path.getmtime and _ensure_git_manager."""
        mock_gm = Mock()
        if git_success:
            mock_gm.get_last_commit_time.return_value = (
                True,
                {"committed_epoch": git_epoch},
            )
        else:
            mock_gm.get_last_commit_time.return_value = (
                False,
                {"error": "file not found"},
            )
        return (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", new_callable=mock_open, read_data=README_AIKB),
            patch("os.path.getmtime", return_value=local_mtime),
            patch("docs2md._ensure_git_manager", return_value=mock_gm),
            patch("docs2md._calc_child_path", return_value=""),
            patch("docs2md.sync_to_git", return_value=True),
        )

    def test_sync_readme_commits_when_local_is_newer(self):
        """force=False: local mtime newer than git commit → commit"""
        config = _make_git_config(force_readme_git_commit=False)
        patches = self._readme_mtime_patches(local_mtime=2000.0, git_epoch=1000.0)
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5] as mock_sync,
        ):
            result = docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        self.assertTrue(result)
        mock_sync.assert_called_once()

    def test_sync_readme_skipped_when_local_is_not_newer(self):
        """force=False: local mtime older than git commit → skip"""
        config = _make_git_config(force_readme_git_commit=False)
        patches = self._readme_mtime_patches(local_mtime=1000.0, git_epoch=2000.0)
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5] as mock_sync,
        ):
            result = docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        self.assertFalse(result)
        mock_sync.assert_not_called()

    def test_sync_readme_commits_when_get_last_commit_time_fails(self):
        """force=False: get_last_commit_time fails (not in git yet) → commit anyway"""
        config = _make_git_config(force_readme_git_commit=False)
        patches = self._readme_mtime_patches(
            local_mtime=1000.0, git_epoch=None, git_success=False
        )
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5] as mock_sync,
        ):
            result = docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        self.assertTrue(result)
        mock_sync.assert_called_once()

    def test_sync_readme_returns_false_when_ensure_git_manager_raises(self):
        """force=False: _ensure_git_manager raises GitFatalError → return False"""
        config = _make_git_config(force_readme_git_commit=False)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", new_callable=mock_open, read_data=README_AIKB),
            patch("os.path.getmtime", return_value=1000.0),
            patch(
                "docs2md._ensure_git_manager",
                side_effect=docs2md.GitFatalError("init failed"),
            ),
        ):
            result = docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        self.assertFalse(result)

    def test_sync_readme_returns_false_when_git_manager_error_set(self):
        """force=False: _git_manager_error already True → _ensure_git_manager returns None → False"""
        docs2md._git_manager_error = True
        config = _make_git_config(force_readme_git_commit=False)
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", new_callable=mock_open, read_data=README_AIKB),
            patch("os.path.getmtime", return_value=1000.0),
        ):
            result = docs2md.sync_readme_to_git("/root/README.md", config, self.logger)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# 8. Main orchestration
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    """main() — startup, error paths, summary output"""

    def _run_main(
        self,
        config_overrides=None,
        pandoc_ok=True,
        root_exists=True,
        process_side_effect=None,
    ):
        config = _make_config(**(config_overrides or {}))
        mock_logger = Mock()
        captured = []
        mock_logger.info.side_effect = captured.append

        patches = [
            patch("docs2md.load_config", return_value=config),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=pandoc_ok),
            patch("os.path.isabs", return_value=True),
            patch("os.path.exists", return_value=root_exists),
        ]
        if process_side_effect:
            patches.append(
                patch(
                    "docs2md.process_directories_recursively",
                    side_effect=process_side_effect,
                )
            )
        else:
            patches.append(patch("docs2md.process_directories_recursively"))

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            with patch("sys.exit") as mock_exit:
                docs2md.main()
        return captured, mock_logger, mock_exit

    def test_logs_files_path(self):
        captured, _, _ = self._run_main({"root_folder": "/test/root"})
        self.assertTrue(
            any("Files path:" in m and '"/test/root"' in m for m in captured)
        )

    def test_logs_git_path_when_enabled(self):
        captured, _, _ = self._run_main(
            {
                "git_commit": True,
                "git_url": "https://gitlab.example.com/proj/-/tree/main",
            }
        )
        self.assertTrue(any("Git path:" in m for m in captured))

    def test_no_git_path_when_disabled(self):
        captured, _, _ = self._run_main({"git_commit": False})
        self.assertFalse(any("Git path:" in m for m in captured))

    def test_exits_when_pandoc_missing(self):
        _, _, mock_exit = self._run_main(pandoc_ok=False)
        mock_exit.assert_called_with(1)

    def test_exits_when_root_folder_missing(self):
        _, _, mock_exit = self._run_main(root_exists=False)
        mock_exit.assert_called_with(1)

    def test_exits_when_root_folder_not_in_config(self):
        _, _, mock_exit = self._run_main({"root_folder": None})
        mock_exit.assert_called_with(1)

    def test_exits_on_git_fatal_error(self):
        _, _, mock_exit = self._run_main(
            {
                "git_commit": True,
                "git_url": "https://gitlab.example.com/proj/-/tree/main",
            },
            process_side_effect=docs2md.GitFatalError("auth failed"),
        )
        mock_exit.assert_called_with(1)

    def test_summary_logged(self):
        captured, _, _ = self._run_main()
        self.assertIn("SUMMARY:", captured)

    def test_summary_git_identical_line_present(self):
        """Summary must include the 'Files skipped as identical to remote ones in git' line."""
        captured, _, _ = self._run_main()
        self.assertTrue(any("identical to remote" in line for line in captured))

    def test_summary_blank_line_before_header(self):
        captured, _, _ = self._run_main()
        idx = captured.index("SUMMARY:")
        self.assertEqual(captured[idx - 1], "")

    def test_change_log_shown_when_important_logs_present(self):
        def add_log(*args, **kwargs):
            if args and isinstance(args[4], list):
                args[4].append('"test.txt" MD generated')

        captured, _, _ = self._run_main(process_side_effect=add_log)
        self.assertIn("Change log:", captured)

    def test_load_config_error_still_runs(self):
        """If load_config raises, main falls back to defaults and continues"""
        mock_logger = Mock()
        with (
            patch("docs2md.load_config", side_effect=Exception("bad yaml")),
            patch("docs2md.setup_logging", return_value=mock_logger),
            patch("docs2md.verify_pandoc", return_value=False),
            patch("sys.exit"),
        ):
            docs2md.main()  # must not raise


if __name__ == "__main__":
    unittest.main()
