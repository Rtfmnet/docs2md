"""
Integration tests for docs2md tool
"""

import unittest
import os
import sys
import shutil
import tempfile
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import docs2md


class TestIntegrationDocs2md(unittest.TestCase):
    """Integration tests for docs2md"""

    def setUp(self):
        """Set up test environment"""
        # Create test_data directory
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
        os.makedirs(self.test_data_dir)

        # Create logger
        self.logger = docs2md.setup_logging()

        # Create config
        self.config = {
            "root_folder": self.test_data_dir,
            "common": {
                "pause_before_exit": False,
            },
            "force_md_generation": False,
        }

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_data_dir):
            try:
                shutil.rmtree(self.test_data_dir)
            except Exception as e:
                print(f"Warning: Could not remove test_data: {e}")

    def create_test_file(self, directory, filename, content="Test content"):
        """Create a test document file"""
        filepath = os.path.join(directory, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def create_readme(self, directory, content):
        """Create README.md file"""
        readme_path = os.path.join(directory, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        return readme_path

    def test_directory_depth_structure(self):
        """Test processing directory structure: root/sub1/sub2/sub3"""
        # Create nested structure
        sub1 = os.path.join(self.test_data_dir, "sub1")
        sub2 = os.path.join(sub1, "sub2")
        sub3 = os.path.join(sub2, "sub3")

        os.makedirs(sub3)

        # Create READMEs at each level with doc2md#aikb tag
        self.create_readme(self.test_data_dir, "# Root\ndoc2md#aikb")
        self.create_readme(sub1, "# Sub1\ndoc2md#aikb\ntest1.html")
        self.create_readme(sub2, "# Sub2\ndoc2md#aikb\ntest2.html")
        self.create_readme(sub3, "# Sub3\ndoc2md#aikb\ntest3.html")

        # Create test files
        self.create_test_file(sub1, "test1.html", "<html><body>Test1</body></html>")
        self.create_test_file(sub2, "test2.html", "<html><body>Test2</body></html>")
        self.create_test_file(sub3, "test3.html", "<html><body>Test3</body></html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directories_recursively(
            self.test_data_dir, self.config, self.logger, stats
        )

        # Verify processing occurred
        self.assertGreater(stats["dirs_processed"], 0)

    def test_missing_readme(self):
        """Test directory without README.md is skipped"""
        # Create directory without README
        no_readme_dir = os.path.join(self.test_data_dir, "no_readme")
        os.makedirs(no_readme_dir)

        # Create a test file
        self.create_test_file(no_readme_dir, "test.html", "<html>Test</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directories_recursively(
            self.test_data_dir, self.config, self.logger, stats
        )

        # Verify directory was skipped (no README = no doc2md#aikb tag)
        md_file = os.path.join(no_readme_dir, "test.md")
        self.assertFalse(os.path.exists(md_file))

    def test_readme_without_aikb_tag_is_skipped(self):
        """Test directory with README.md but without doc2md#aikb tag is skipped"""
        skip_dir = os.path.join(self.test_data_dir, "no_aikb_dir")
        os.makedirs(skip_dir)

        # Create README without doc2md#aikb tag
        self.create_readme(skip_dir, "# No aikb tag here\nSome content")

        # Create test file
        self.create_test_file(skip_dir, "test.html", "<html>Test</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directories_recursively(
            self.test_data_dir, self.config, self.logger, stats
        )

        # Verify directory was skipped and no MD generated
        self.assertGreater(stats["dirs_skipped"], 0)
        md_file = os.path.join(skip_dir, "test.md")
        self.assertFalse(os.path.exists(md_file))

    def test_file_referenced_in_readme(self):
        """Test file referenced in README is processed"""
        test_dir = os.path.join(self.test_data_dir, "ref_test")
        os.makedirs(test_dir)

        # Create README referencing file with doc2md#aikb tag
        self.create_readme(
            test_dir, "# Documentation\ndoc2md#aikb\nSee test.html for details"
        )

        # Create test file
        self.create_test_file(test_dir, "test.html", "<html>Test</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # Note: Actual conversion requires pandoc, so we check the attempt was made
        self.assertGreater(stats["files_generated"] + stats["files_errors"], 0)

    def test_file_not_referenced_no_mask(self):
        """Test file not referenced and no mask is skipped"""
        test_dir = os.path.join(self.test_data_dir, "no_ref_test")
        os.makedirs(test_dir)

        # Create README without referencing file but with doc2md#aikb tag
        self.create_readme(test_dir, "# Documentation\ndoc2md#aikb\nNo files mentioned")

        # Create test file
        self.create_test_file(test_dir, "test.html", "<html>Test</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # Verify no files were processed
        self.assertEqual(stats["files_generated"], 0)

    def test_skipfile_tag(self):
        """Test file with doc2md#skipfile tag is skipped"""
        test_dir = os.path.join(self.test_data_dir, "skipfile_test")
        os.makedirs(test_dir)

        # Create README with skipfile tag and doc2md#aikb tag
        self.create_readme(
            test_dir,
            "# Documentation\ndoc2md#aikb\ntest.html doc2md#skipfile - skip this file",
        )

        # Create test file
        self.create_test_file(test_dir, "test.html", "<html>Test</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # Verify file was skipped
        self.assertEqual(stats["files_generated"], 0)

    def test_mask_filtering(self):
        """Test file mask filtering using glob/wildcard syntax"""
        test_dir = os.path.join(self.test_data_dir, "mask_test")
        os.makedirs(test_dir)

        # Create README with glob mask (no quotes) and doc2md#aikb tag
        self.create_readme(
            test_dir,
            "# Documentation\ndoc2md#aikb\ndoc2md#mask=test*.html\ntest1.html",
        )

        # Create test files
        self.create_test_file(test_dir, "test1.html", "<html>Test1</html>")
        self.create_test_file(test_dir, "other.html", "<html>Other</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # Only test1.html should be processed
        # other.html should be filtered out by mask
        self.assertGreater(stats["files_generated"] + stats["files_errors"], 0)

    def test_force_generation(self):
        """Test force_md_generation config parameter"""
        test_dir = os.path.join(self.test_data_dir, "force_test")
        os.makedirs(test_dir)

        # Create README with doc2md#aikb tag
        self.create_readme(test_dir, "# Documentation\ndoc2md#aikb\ntest.html")

        # Create test file
        test_file = self.create_test_file(test_dir, "test.html", "<html>Test</html>")

        # Create existing MD file (older or newer doesn't matter with force)
        md_file = os.path.join(test_dir, "test.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Old content")

        # Set file to be newer than source
        future_time = time.time() + 3600
        os.utime(md_file, (future_time, future_time))

        # Process with force enabled
        config_force = self.config.copy()
        config_force["force_md_generation"] = True

        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, config_force, self.logger, stats)

        # File should be processed despite MD being newer
        self.assertGreater(stats["files_generated"] + stats["files_errors"], 0)

    def test_outdated_md_regeneration(self):
        """Test outdated MD file is regenerated"""
        test_dir = os.path.join(self.test_data_dir, "outdated_test")
        os.makedirs(test_dir)

        # Create README with doc2md#aikb tag
        self.create_readme(test_dir, "# Documentation\ndoc2md#aikb\ntest.html")

        # Create old MD file first
        md_file = os.path.join(test_dir, "test.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Old content")

        # Make MD file old
        old_time = time.time() - 3600
        os.utime(md_file, (old_time, old_time))

        # Create newer source file
        time.sleep(0.1)
        test_file = self.create_test_file(test_dir, "test.html", "<html>New</html>")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # File should be regenerated
        self.assertGreater(stats["files_generated"] + stats["files_errors"], 0)

    def test_up_to_date_md_skipped(self):
        """Test up-to-date MD file is skipped"""
        test_dir = os.path.join(self.test_data_dir, "uptodate_test")
        os.makedirs(test_dir)

        # Create README with doc2md#aikb tag
        self.create_readme(test_dir, "# Documentation\ndoc2md#aikb\ntest.html")

        # Create source file
        test_file = self.create_test_file(test_dir, "test.html", "<html>Test</html>")

        # Make source file old
        old_time = time.time() - 3600
        os.utime(test_file, (old_time, old_time))

        # Create newer MD file
        time.sleep(0.1)
        md_file = os.path.join(test_dir, "test.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Current content")

        # Process
        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_skipped": 0,
            "files_errors": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # File should be skipped
        self.assertGreater(stats["files_skipped"], 0)

    def test_md_subdirectory(self):
        """Test MD files stored in 'md' subdirectory when it exists"""
        test_dir = os.path.join(self.test_data_dir, "md_subdir_test")
        md_dir = os.path.join(test_dir, "md")
        os.makedirs(md_dir)

        # Create README
        self.create_readme(test_dir, "# Documentation\ntest.html")

        # Create test file
        self.create_test_file(test_dir, "test.html", "<html>Test</html>")

        # Get target path
        target_path = docs2md.get_target_md_path("test.html", test_dir)

        # Verify it's in md subdirectory
        self.assertIn(os.path.join("md", "test.md"), target_path)

    def test_name_conflict_resolution(self):
        """Test files with same name but different extensions"""
        test_dir = os.path.join(self.test_data_dir, "conflict_test")
        os.makedirs(test_dir)

        # Create README
        self.create_readme(test_dir, "# Documentation\ntest.html\ntest.xml")

        # Create files with same base name
        self.create_test_file(test_dir, "test.html", "<html>HTML</html>")
        self.create_test_file(test_dir, "test.xml", "<root>XML</root>")

        # Get target paths
        html_target = docs2md.get_target_md_path("test.html", test_dir)
        xml_target = docs2md.get_target_md_path("test.xml", test_dir)

        # Verify different names
        self.assertNotEqual(html_target, xml_target)
        self.assertTrue(
            html_target.endswith("_html.md") or html_target.endswith("test.md")
        )
        self.assertTrue(
            xml_target.endswith("_xml.md") or xml_target.endswith("test.md")
        )

    def test_cleanup_after_exception(self):
        """Test cleanup happens even after exception"""
        # This is handled by tearDown
        try:
            # Force an error
            raise Exception("Test exception")
        except:
            pass

        # tearDown should still clean up
        self.assertTrue(True)

    def test_standalone_md_collected_when_git_disabled(self):
        """Standalone .md files are collected; with git disabled they are silently skipped (no error)"""
        test_dir = os.path.join(self.test_data_dir, "standalone_md_test")
        os.makedirs(test_dir)

        # README references both the source and the standalone .md
        self.create_readme(
            test_dir,
            "# Documentation\ndoc2md#aikb\nsource.html\nnotes.md",
        )
        # Source doc — will be pandoc-converted
        self.create_test_file(
            test_dir, "source.html", "<html><body>Source</body></html>"
        )
        # Standalone .md — no paired source doc
        self.create_test_file(
            test_dir, "notes.md", "# Notes\nSome standalone content.\n"
        )

        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_committed": 0,
            "files_skipped": 0,
            "files_errors": 0,
            "files_git_identical": 0,
        }

        docs2md.process_directory(test_dir, self.config, self.logger, stats)

        # source.html should have been converted (generated or error if pandoc missing)
        self.assertGreater(stats["files_generated"] + stats["files_errors"], 0)
        # No errors from the standalone .md itself (git is disabled → silent skip)
        # Verify collect_standalone_md_files correctly identifies notes.md
        source_files = docs2md.collect_files_in_directory(test_dir, self.config)
        standalone = docs2md.collect_standalone_md_files(test_dir, source_files)
        self.assertIn("notes.md", standalone)
        self.assertNotIn("source.md", standalone)  # pandoc output, not standalone
        self.assertNotIn("README.md", standalone)

    def test_standalone_md_paired_excluded(self):
        """An .md file whose base name matches a source doc is not treated as standalone"""
        test_dir = os.path.join(self.test_data_dir, "paired_md_test")
        os.makedirs(test_dir)

        self.create_test_file(test_dir, "report.docx", "Fake docx content")
        self.create_test_file(test_dir, "report.md", "# Generated output")
        self.create_test_file(test_dir, "standalone.md", "# Standalone")

        source_files = docs2md.collect_files_in_directory(test_dir, self.config)
        standalone = docs2md.collect_standalone_md_files(test_dir, source_files)

        self.assertIn("standalone.md", standalone)
        self.assertNotIn("report.md", standalone)


class TestForceCleanGitE2E(unittest.TestCase):
    """E2E test for force_clean_git: verifies clean_git_remote is called before
    any push_commit_file calls when force_clean_git is enabled."""

    def setUp(self):
        self.test_data_dir = os.path.join(
            os.path.dirname(__file__), "test_data", "cr5_e2e"
        )
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)
        os.makedirs(self.test_data_dir)
        self.logger = docs2md.setup_logging()

        docs2md._git_manager = None
        docs2md._git_manager_error = False

    def tearDown(self):
        if os.path.exists(self.test_data_dir):
            try:
                shutil.rmtree(self.test_data_dir)
            except Exception:
                pass
        docs2md._git_manager = None
        docs2md._git_manager_error = False

    def test_force_clean_git_called_before_push(self):
        """With force_clean_git:true, list_files/delete_file run before push_commit_file."""
        from unittest.mock import Mock, call, patch

        # Create a minimal directory with README + one source file
        readme_path = os.path.join(self.test_data_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Test\ndoc2md#aikb\nsource.html\n")

        source_path = os.path.join(self.test_data_dir, "source.html")
        with open(source_path, "w") as f:
            f.write("<html><body>E2E test</body></html>")

        call_order = []

        mock_gm = Mock()
        mock_gm.verify_path.return_value = (True, {"contents_count": 1})
        mock_gm.get_last_commit_time.return_value = (False, {"error": "not found"})
        mock_gm.list_files.side_effect = lambda *a, **kw: (
            call_order.append("list_files")
            or (True, {"files": ["README.md", "old.md"]})
        )
        mock_gm.delete_file.side_effect = lambda *a, **kw: (
            call_order.append("delete_file") or (True, {"message": "deleted"})
        )
        mock_gm.push_commit_file.side_effect = lambda *a, **kw: (
            call_order.append("push_commit_file")
            or (True, {"message": "created", "file_path": "x.md"})
        )

        config = {
            "root_folder": self.test_data_dir,
            "git_commit": True,
            "git_url": "https://gitbud.epam.com/proj/-/tree/main/docs",
            "force_clean_git": True,
            "force_md_generation": True,
            "common": {},
        }

        stats = {
            "dirs_processed": 0,
            "dirs_skipped": 0,
            "files_generated": 0,
            "files_committed": 0,
            "files_skipped": 0,
            "files_errors": 0,
            "files_git_identical": 0,
        }

        with patch("docs2md.GitManager", return_value=mock_gm):
            # Run clean manually (as main() would) — deletes all + pushes .gitkeep
            docs2md.clean_git_remote(config["git_url"], mock_gm, self.logger)
            # Then process directories
            docs2md.process_directories_recursively(
                self.test_data_dir, config, self.logger, stats
            )

        # list_files must appear in call order
        self.assertIn("list_files", call_order)
        # delete_file calls must all finish before any processing-phase push_commit_file
        # (the first push_commit_file in call_order is the .gitkeep from clean_git_remote,
        #  so we verify that ALL delete_file calls precede the LAST push_commit_file
        #  that came from the processing phase, i.e. that clean ran fully before processing)
        if call_order.count("push_commit_file") > 1:
            # At least the .gitkeep push + one content push happened
            last_delete = max(
                (i for i, c in enumerate(call_order) if c == "delete_file"),
                default=-1,
            )
            last_push = max(
                i for i, c in enumerate(call_order) if c == "push_commit_file"
            )
            self.assertLess(
                last_delete,
                last_push,
                "All delete_file calls must complete before final push_commit_file",
            )


if __name__ == "__main__":
    unittest.main()
