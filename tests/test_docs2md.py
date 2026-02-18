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
        self.assertEqual(logger.name, 'docs2md')
        self.assertEqual(len(logger.handlers), 2)
    
    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns a valid logger"""
        logger = docs2md.setup_logging()
        self.assertTrue(hasattr(logger, 'info'))
        self.assertTrue(hasattr(logger, 'error'))


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='root_folder: /test\npause_before_exit: true')
    @patch('yaml.safe_load')
    def test_load_config_positive(self, mock_yaml, mock_file):
        """Test successful config loading"""
        mock_yaml.return_value = {'root_folder': '/test', 'pause_before_exit': True}
        config = docs2md.load_config()
        self.assertIsNotNone(config)
        self.assertIn('root_folder', config)
    
    def test_load_config_file_not_found(self):
        """Test config loading with missing file"""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            with self.assertRaises(Exception) as context:
                docs2md.load_config()
            self.assertIn('not found', str(context.exception))


class TestVerifyPandoc(unittest.TestCase):
    """Test pandoc verification"""
    
    @patch('subprocess.run')
    def test_verify_pandoc_positive(self, mock_run):
        """Test successful pandoc verification"""
        mock_run.return_value = Mock(returncode=0)
        result = docs2md.verify_pandoc()
        self.assertTrue(result)
    
    @patch('subprocess.run')
    def test_verify_pandoc_not_installed(self, mock_run):
        """Test pandoc not installed"""
        mock_run.side_effect = FileNotFoundError()
        result = docs2md.verify_pandoc()
        self.assertFalse(result)


class TestReadReadme(unittest.TestCase):
    """Test README reading"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='Test content')
    def test_read_readme_positive(self, mock_file):
        """Test successful README reading"""
        content = docs2md.read_readme('/test/README.md')
        self.assertEqual(content, 'Test content')
    
    @patch('builtins.open', side_effect=Exception('File error'))
    def test_read_readme_error(self, mock_file):
        """Test README reading with error"""
        content = docs2md.read_readme('/test/README.md')
        self.assertIsNone(content)


class TestCheckSkipdir(unittest.TestCase):
    """Test skipdir tag checking"""
    
    def test_check_skipdir_positive(self):
        """Test skipdir tag is found"""
        content = 'Some text\ndoc2md#skipdir\nMore text'
        result = docs2md.check_skipdir(content)
        self.assertTrue(result)
    
    def test_check_skipdir_negative(self):
        """Test skipdir tag is not found"""
        content = 'Some text\nNo special tags\nMore text'
        result = docs2md.check_skipdir(content)
        self.assertFalse(result)


class TestExtractMasks(unittest.TestCase):
    """Test mask extraction from README"""
    
    def test_extract_masks_positive(self):
        """Test successful mask extraction"""
        content = "doc2md#mask='^.*\\.docx$'\nOther text\ndoc2md#mask='^test.*$'"
        masks = docs2md.extract_masks(content)
        self.assertEqual(len(masks), 2)
        self.assertIn('^.*\\.docx$', masks)
    
    def test_extract_masks_no_masks(self):
        """Test extraction with no masks"""
        content = "Some text without masks"
        masks = docs2md.extract_masks(content)
        self.assertEqual(len(masks), 0)


class TestCollectFilesInDirectory(unittest.TestCase):
    """Test file collection in directory"""
    
    @patch('os.listdir')
    @patch('os.path.isfile')
    def test_collect_files_positive(self, mock_isfile, mock_listdir):
        """Test successful file collection"""
        mock_listdir.return_value = ['file1.docx', 'file2.txt', 'file3.pdf']
        mock_isfile.return_value = True
        files = docs2md.collect_files_in_directory('/test')
        self.assertIn('file1.docx', files)
    
    @patch('os.listdir', side_effect=Exception('Access denied'))
    def test_collect_files_error(self, mock_listdir):
        """Test file collection with error"""
        files = docs2md.collect_files_in_directory('/test')
        self.assertEqual(len(files), 0)


class TestApplyMasks(unittest.TestCase):
    """Test mask application to files"""
    
    def test_apply_masks_positive(self):
        """Test successful mask application"""
        files = ['test.docx', 'report.docx', 'data.xlsx']
        masks = ['^test.*$']
        result = docs2md.apply_masks(files, masks)
        self.assertIn('test.docx', result)
        self.assertNotIn('report.docx', result)
    
    def test_apply_masks_no_masks(self):
        """Test with no masks provided"""
        files = ['test.docx', 'report.docx']
        masks = []
        result = docs2md.apply_masks(files, masks)
        self.assertEqual(result, files)


class TestIsFileReferencedInReadme(unittest.TestCase):
    """Test file reference checking in README"""
    
    def test_is_file_referenced_positive(self):
        """Test file is referenced"""
        content = 'See file test.docx for details'
        result = docs2md.is_file_referenced_in_readme('test.docx', content)
        self.assertTrue(result)
    
    def test_is_file_referenced_negative(self):
        """Test file is not referenced"""
        content = 'See file report.docx for details'
        result = docs2md.is_file_referenced_in_readme('test.docx', content)
        self.assertFalse(result)


class TestGetFileReferenceLine(unittest.TestCase):
    """Test file reference line extraction"""
    
    def test_get_file_reference_line_positive(self):
        """Test successful line extraction"""
        content = 'Line 1\nSee test.docx here\nLine 3'
        line = docs2md.get_file_reference_line('test.docx', content)
        self.assertIsNotNone(line)
        self.assertIn('test.docx', line)
    
    def test_get_file_reference_line_not_found(self):
        """Test line extraction when file not referenced"""
        content = 'Line 1\nNo file here\nLine 3'
        line = docs2md.get_file_reference_line('test.docx', content)
        self.assertIsNone(line)


class TestHasSkipfileTag(unittest.TestCase):
    """Test skipfile tag checking"""
    
    def test_has_skipfile_tag_positive(self):
        """Test skipfile tag is found"""
        line = 'test.docx doc2md#skipfile should be skipped'
        result = docs2md.has_skipfile_tag(line)
        self.assertTrue(result)
    
    def test_has_skipfile_tag_negative(self):
        """Test skipfile tag is not found"""
        line = 'test.docx should be processed'
        result = docs2md.has_skipfile_tag(line)
        self.assertFalse(result)


class TestFilterFilesByReadme(unittest.TestCase):
    """Test file filtering based on README"""
    
    def test_filter_files_positive(self):
        """Test successful file filtering"""
        files = ['test.docx', 'report.docx']
        content = 'Process test.docx'
        result = docs2md.filter_files_by_readme(files, content, True)
        self.assertIn('test.docx', result)
    
    def test_filter_files_with_skipfile(self):
        """Test filtering with skipfile tag"""
        files = ['test.docx']
        content = 'test.docx doc2md#skipfile'
        result = docs2md.filter_files_by_readme(files, content, True)
        self.assertEqual(len(result), 0)


class TestGetTargetMdPath(unittest.TestCase):
    """Test MD target path determination"""
    
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_get_target_md_path_no_md_dir(self, mock_listdir, mock_exists):
        """Test target path without md directory"""
        mock_exists.return_value = False
        mock_listdir.return_value = []
        result = docs2md.get_target_md_path('test.docx', '/dir')
        self.assertTrue(result.endswith('test.md'))
    
    @patch('os.path.isfile')
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_get_target_md_path_with_conflict(self, mock_listdir, mock_exists, mock_isfile):
        """Test target path with name conflict"""
        mock_exists.return_value = False
        mock_listdir.return_value = ['test.xlsx', 'test.docx']
        mock_isfile.return_value = True
        result = docs2md.get_target_md_path('test.docx', '/dir')
        self.assertTrue(result.endswith('test_docx.md'))


class TestIsSourceNewer(unittest.TestCase):
    """Test source file timestamp comparison"""
    
    @patch('os.path.getmtime')
    def test_is_source_newer_positive(self, mock_getmtime):
        """Test source is newer than target"""
        mock_getmtime.side_effect = [2000, 1000]
        result = docs2md.is_source_newer('/source', '/target')
        self.assertTrue(result)
    
    @patch('os.path.getmtime')
    def test_is_source_newer_negative(self, mock_getmtime):
        """Test source is not newer than target"""
        mock_getmtime.side_effect = [1000, 2000]
        result = docs2md.is_source_newer('/source', '/target')
        self.assertFalse(result)


class TestConvertToMarkdown(unittest.TestCase):
    """Test markdown conversion"""
    
    @patch('subprocess.run')
    @patch('os.makedirs')
    def test_convert_to_markdown_positive(self, mock_makedirs, mock_run):
        """Test successful conversion"""
        mock_run.return_value = Mock(returncode=0)
        logger = Mock()
        success, message = docs2md.convert_to_markdown('/src.docx', '/dst.md', logger)
        self.assertTrue(success)
        self.assertIn('generated', message)
    
    @patch('subprocess.run')
    @patch('os.makedirs')
    def test_convert_to_markdown_failure(self, mock_makedirs, mock_run):
        """Test conversion failure"""
        mock_run.return_value = Mock(returncode=1, stderr='Error occurred')
        logger = Mock()
        success, message = docs2md.convert_to_markdown('/src.docx', '/dst.md', logger)
        self.assertFalse(success)
        self.assertIn('Error', message)


class TestProcessFile(unittest.TestCase):
    """Test file processing"""
    
    @patch('docs2md.convert_to_markdown')
    @patch('docs2md.get_target_md_path')
    @patch('os.path.exists')
    def test_process_file_new_file(self, mock_exists, mock_get_path, mock_convert):
        """Test processing new file"""
        mock_exists.return_value = False
        mock_get_path.return_value = '/dir/test.md'
        mock_convert.return_value = (True, 'MD generated')
        logger = Mock()
        success, message = docs2md.process_file('test.docx', '/dir', False, logger)
        self.assertTrue(success)
    
    @patch('docs2md.is_source_newer')
    @patch('docs2md.get_target_md_path')
    @patch('os.path.exists')
    def test_process_file_up_to_date(self, mock_exists, mock_get_path, mock_newer):
        """Test processing up-to-date file"""
        mock_exists.return_value = True
        mock_get_path.return_value = '/dir/test.md'
        mock_newer.return_value = False
        logger = Mock()
        success, message = docs2md.process_file('test.docx', '/dir', False, logger)
        self.assertIsNone(success)
        self.assertIn('Skipped', message)


if __name__ == '__main__':
    unittest.main()
