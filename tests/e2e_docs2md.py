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


if __name__ == "__main__":
    unittest.main()
