import unittest
from unittest.mock import patch, Mock, MagicMock
import os
import sys
import json
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from git_sync import GitManager


class TestGitManager(unittest.TestCase):
    """Test GitManager class"""

    @patch("os.getenv")
    def test_init_with_token(self, mock_getenv):
        """Test initialization with token"""
        mock_getenv.return_value = "test_token"
        git_manager = GitManager()
        self.assertEqual(git_manager.token, "test_token")

    @patch("os.getenv")
    def test_init_without_token(self, mock_getenv):
        """Test initialization without token"""
        mock_getenv.return_value = None
        with self.assertRaises(ValueError):
            git_manager = GitManager()

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_commit_push_file_new_file(self, mock_get, mock_post, mock_put, mock_init):
        """Test committing a new file"""
        mock_init.return_value = None

        # Set up mock response for file check (file doesn't exist)
        mock_get_response = Mock()
        mock_get_response.status_code = 404  # File not found
        mock_get.return_value = mock_get_response

        # Set up mock response for create file
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"file_path": "test_file.md"}
        mock_post_response.text = '{"file_path": "test_file.md"}'
        mock_post.return_value = mock_post_response

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        # Mock open to read file content
        file_content = "Test content"
        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                "https://gitbud.epam.com/project/repo/-/tree/main/path",
                "Test commit",
                git_child_path=None,
            )

        # Verify GET request was made to check if file exists
        self.assertTrue(mock_get.called)

        # Verify POST request was made to create the file (not PUT)
        self.assertTrue(mock_post.called)
        self.assertFalse(mock_put.called)

        # Check payload for file creation
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["commit_message"], "Test commit")
        self.assertEqual(payload["content"], "Test content")

        # Check success
        self.assertTrue(success)
        self.assertIn("message", details)

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_commit_push_file_update_file(
        self, mock_get, mock_post, mock_put, mock_init
    ):
        """Test updating an existing file"""
        mock_init.return_value = None
        import base64

        # Set up mock responses for file check (file exists with different content)
        mock_get_response = Mock()
        mock_get_response.status_code = 200  # File exists
        mock_get_response.json.return_value = {
            "content": base64.b64encode(b"Old content").decode("utf-8")
        }
        mock_get.return_value = mock_get_response

        # Set up mock response for update file
        mock_put_response = Mock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"file_path": "test_file.md"}
        mock_put_response.text = '{"file_path": "test_file.md"}'
        mock_put.return_value = mock_put_response

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        # Mock open to read file content (different from remote)
        file_content = "Test content"
        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                "https://gitbud.epam.com/project/repo/-/tree/main/path",
                "Test commit",
                git_child_path=None,
            )

        # Verify GET request was made to check if file exists
        self.assertTrue(mock_get.called)

        # Verify PUT request was made to update the file (not POST)
        self.assertTrue(mock_put.called)
        self.assertFalse(mock_post.called)

        # Check payload for file update
        args, kwargs = mock_put.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["commit_message"], "Test commit")
        self.assertEqual(payload["content"], "Test content")

        # Check success
        self.assertTrue(success)
        self.assertIn("message", details)

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_commit_push_file_with_child_path(
        self, mock_get, mock_post, mock_put, mock_init
    ):
        """Test committing a file with git_child_path"""
        mock_init.return_value = None

        # Set up mock response for file check (file doesn't exist)
        mock_get_response = Mock()
        mock_get_response.status_code = 404  # File not found
        mock_get.return_value = mock_get_response

        # Set up mock response for create file
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"file_path": "child/dir/test_file.md"}
        mock_post_response.text = '{"file_path": "child/dir/test_file.md"}'
        mock_post.return_value = mock_post_response

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        # Mock open to read file content
        file_content = "Test content"
        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                "https://gitbud.epam.com/project/repo/-/tree/main/path",
                "Test commit",
                git_child_path="child/dir",
            )

        # Verify request was called
        self.assertTrue(mock_post.called)

        # Get the URL from the POST request
        args, kwargs = mock_post.call_args
        url = args[0]

        # Verify child path is properly encoded in the URL
        self.assertIn("child", url)

        # Check success
        self.assertTrue(success)
        self.assertIn("message", details)
        # Verify child path appears in the file_path of the result
        self.assertTrue("child" in details["file_path"])

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_commit_push_file_api_error(self, mock_get, mock_post, mock_put, mock_init):
        """Test handling API error when committing"""
        mock_init.return_value = None

        # Set up mock response for file check (file doesn't exist)
        mock_get_response = Mock()
        mock_get_response.status_code = 404  # File not found
        mock_get.return_value = mock_get_response

        # Set up mock response for create file error
        mock_post_response = Mock()
        mock_post_response.status_code = 400
        mock_post_response.text = "Bad request"
        mock_post.return_value = mock_post_response

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        # Mock open to read file content
        file_content = "Test content"
        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                "https://gitbud.epam.com/project/repo/-/tree/main/path",
                "Test commit",
            )

        # Check failure
        self.assertFalse(success)
        self.assertIn("error", details)

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_commit_push_file_file_exists_retry(
        self, mock_get, mock_post, mock_put, mock_init
    ):
        """Test handling the 'file already exists' error by retrying as update"""
        mock_init.return_value = None

        # Set up mock response for file check (file doesn't exist)
        mock_get_response = Mock()
        mock_get_response.status_code = 404  # File not found
        mock_get.return_value = mock_get_response

        # Set up mock response for POST (file already exists error)
        mock_post_response = Mock()
        mock_post_response.status_code = 400
        mock_post_response.text = '{"message":"A file with this name already exists"}'
        mock_post.return_value = mock_post_response

        # Set up mock response for PUT retry (success)
        mock_put_response = Mock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"file_path": "test_file.md"}
        mock_put_response.text = '{"file_path": "test_file.md"}'
        mock_put.return_value = mock_put_response

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        # Mock open to read file content
        file_content = "Test content"
        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                "https://gitbud.epam.com/project/repo/-/tree/main/path",
                "Test commit",
            )

        # Verify both POST and PUT were called
        self.assertTrue(mock_post.called)
        self.assertTrue(mock_put.called)

        # Check success
        self.assertTrue(success)
        self.assertIn("message", details)
        self.assertIn("updated", details["message"])

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_push_commit_file_root_url_dot_child_path(
        self, mock_get, mock_post, mock_put, mock_init
    ):
        """Test that git_child_path='.' with a root URL (no subdir) produces a clean
        target path 'filename.md' instead of the broken './filename.md'."""
        mock_init.return_value = None

        # File does not exist yet → GET returns 404
        mock_get_response = Mock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response

        # POST succeeds
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {"file_path": "test_file.md"}
        mock_post_response.text = '{"file_path": "test_file.md"}'
        mock_post.return_value = mock_post_response

        git_manager = GitManager()
        git_manager.token = "test_token"

        file_content = "Test content"
        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                # Root URL — no subdir after branch
                "https://gitbud.epam.com/project/repo/-/tree/main",
                "Test commit",
                git_child_path=".",  # what sync_to_git passes for files in root_folder
            )

        self.assertTrue(success)

        # The file path must NOT contain './' — GitLab API rejects that path format
        self.assertEqual(details["file_path"], "test_file.md")
        self.assertNotIn("./", details["file_path"])

        # Verify the URL used in POST also has no './' segment
        args, kwargs = mock_post.call_args
        api_url = args[0]
        self.assertNotIn(".%2F", api_url)  # URL-encoded './'
        self.assertNotIn("./", api_url)

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.post")
    @patch("requests.get")
    def test_commit_push_file_gitlab_no_change(
        self, mock_get, mock_post, mock_put, mock_init
    ):
        """GitLab: returns no_change=True when remote content is identical to local"""
        import base64

        mock_init.return_value = None

        file_content = "Identical content"

        # GET returns the same content that is already on remote
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "content": base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
        }
        mock_get.return_value = mock_get_response

        git_manager = GitManager()
        git_manager.token = "test_token"

        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = git_manager.push_commit_file(
                "test_file.md",
                "https://gitbud.epam.com/project/repo/-/tree/main/path",
                "Test commit",
            )

        # Should succeed but report no change
        self.assertTrue(success)
        self.assertTrue(details.get("no_change"))
        self.assertEqual(details["message"], "File is identical to remote file in git")

        # No actual write calls should have been made
        self.assertFalse(mock_put.called)
        self.assertFalse(mock_post.called)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_valid(self, mock_get, mock_init):
        """Test verify_path with valid path"""
        mock_init.return_value = None

        # Set up mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"name": "file1.txt"}, {"name": "file2.md"}]
        mock_get.return_value = mock_response

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        success, details = git_manager.verify_path(
            "https://gitbud.epam.com/project/repo/-/tree/main/path"
        )

        self.assertTrue(success)
        self.assertEqual(details["contents_count"], 2)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_invalid(self, mock_get, mock_init):
        """Test verify_path with invalid path"""
        mock_init.return_value = None

        # Set up mock response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Set up second response for repo check
        mock_response2 = Mock()
        mock_response2.status_code = 200
        # We need to provide a side_effect to replace the first call with mock_response
        # and the second call with mock_response2
        mock_get.side_effect = [mock_response, mock_response2]

        # Create GitManager instance and set token
        git_manager = GitManager()
        git_manager.token = "test_token"

        success, details = git_manager.verify_path(
            "https://gitbud.epam.com/project/repo/-/tree/main/path"
        )

        self.assertFalse(success)
        self.assertIn("error", details)
        self.assertIn("Path not found", details["error"])


class TestGitManagerProviderDetection(unittest.TestCase):
    """Test _detect_provider method"""

    @patch.object(GitManager, "__init__")
    def test_detect_gitlab(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        self.assertEqual(
            gm._detect_provider(
                "https://gitbud.epam.com/project/repo/-/tree/main/path"
            ),
            GitManager.PROVIDER_GITLAB,
        )

    @patch.object(GitManager, "__init__")
    def test_detect_github(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        self.assertEqual(
            gm._detect_provider("https://github.com/owner/repo/tree/main/path"),
            GitManager.PROVIDER_GITHUB,
        )

    @patch.object(GitManager, "__init__")
    def test_detect_azure_dev(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        self.assertEqual(
            gm._detect_provider("https://dev.azure.com/org/project/_git/repo"),
            GitManager.PROVIDER_AZURE,
        )

    @patch.object(GitManager, "__init__")
    def test_detect_azure_visualstudio(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        self.assertEqual(
            gm._detect_provider("https://myorg.visualstudio.com/project/_git/repo"),
            GitManager.PROVIDER_AZURE,
        )

    @patch.object(GitManager, "__init__")
    def test_detect_unknown_raises(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        with self.assertRaises(ValueError):
            gm._detect_provider("https://unknown.example.com/some/path")


class TestGitManagerGitHub(unittest.TestCase):
    """Test GitHub-specific methods"""

    @patch.object(GitManager, "__init__")
    def test_parse_github_url(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        parts = gm._parse_github_url(
            "https://github.com/Rtfmnet/test-data/tree/main/doc2md"
        )
        self.assertEqual(parts["owner"], "Rtfmnet")
        self.assertEqual(parts["repo"], "test-data")
        self.assertEqual(parts["branch"], "main")
        self.assertEqual(parts["subdir_path"], "doc2md")

    @patch.object(GitManager, "__init__")
    def test_parse_github_url_no_subdir(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        parts = gm._parse_github_url("https://github.com/owner/repo/tree/main")
        self.assertEqual(parts["subdir_path"], "")

    @patch.object(GitManager, "__init__")
    def test_parse_github_url_invalid(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        with self.assertRaises(ValueError):
            gm._parse_github_url("https://github.com/owner/repo")

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.get")
    def test_push_commit_file_github_new_file(self, mock_get, mock_put, mock_init):
        """Test creating a new file on GitHub (no existing SHA)"""
        mock_init.return_value = None

        # GET check: file does not exist
        mock_get_response = Mock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response

        # PUT response: success
        mock_put_response = Mock()
        mock_put_response.status_code = 201
        mock_put_response.json.return_value = {
            "content": {"path": "doc2md/TestFile.md"}
        }
        mock_put_response.text = "{}"
        mock_put.return_value = mock_put_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="# Test")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://github.com/owner/repo/tree/main/doc2md",
                "doc2md#sync",
            )

        self.assertTrue(success)
        self.assertIn("created", details["message"])
        self.assertEqual(details["file_path"], "doc2md/TestFile.md")
        self.assertEqual(details["branch"], "main")

        # Verify PUT was called (not POST)
        self.assertTrue(mock_put.called)
        # Verify no SHA in payload (new file)
        _, kwargs = mock_put.call_args
        self.assertNotIn("sha", kwargs["json"])

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.get")
    def test_push_commit_file_github_update_file(self, mock_get, mock_put, mock_init):
        """Test updating an existing file on GitHub (includes SHA)"""
        mock_init.return_value = None
        import base64

        # GET check: file exists with SHA and different content
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "sha": "abc123",
            "type": "file",
            "content": base64.b64encode(b"Old content").decode("utf-8"),
        }
        mock_get.return_value = mock_get_response

        # PUT response: success
        mock_put_response = Mock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {}
        mock_put_response.text = "{}"
        mock_put.return_value = mock_put_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="# Updated content")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://github.com/owner/repo/tree/main/doc2md",
                "doc2md#sync",
            )

        self.assertTrue(success)
        self.assertIn("updated", details["message"])

        # Verify SHA was passed in PUT payload
        _, kwargs = mock_put.call_args
        self.assertEqual(kwargs["json"]["sha"], "abc123")

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.get")
    def test_push_commit_file_github_api_error(self, mock_get, mock_put, mock_init):
        """Test GitHub API error handling"""
        mock_init.return_value = None

        mock_get_response = Mock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response

        mock_put_response = Mock()
        mock_put_response.status_code = 422
        mock_put_response.text = "Unprocessable Entity"
        mock_put.return_value = mock_put_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="content")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://github.com/owner/repo/tree/main",
                "commit msg",
            )

        self.assertFalse(success)
        self.assertIn("error", details)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_github_valid(self, mock_get, mock_init):
        """Test GitHub verify_path with valid path"""
        mock_init.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "file1.md", "type": "file"},
            {"name": "file2.md", "type": "file"},
        ]
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"

        success, details = gm.verify_path(
            "https://github.com/owner/repo/tree/main/doc2md"
        )

        self.assertTrue(success)
        self.assertEqual(details["contents_count"], 2)
        self.assertEqual(details["branch"], "main")

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_github_path_not_found(self, mock_get, mock_init):
        """Test GitHub verify_path when path doesn't exist"""
        mock_init.return_value = None

        mock_404 = Mock()
        mock_404.status_code = 404

        mock_repo_ok = Mock()
        mock_repo_ok.status_code = 200
        mock_repo_ok.json.return_value = {"full_name": "owner/repo"}

        mock_get.side_effect = [mock_404, mock_repo_ok]

        gm = GitManager()
        gm.token = "test_token"

        success, details = gm.verify_path(
            "https://github.com/owner/repo/tree/main/nonexistent"
        )

        self.assertFalse(success)
        self.assertIn("Path not found", details["error"])

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_github_repo_not_found(self, mock_get, mock_init):
        """Test GitHub verify_path when repo doesn't exist"""
        mock_init.return_value = None

        mock_404 = Mock()
        mock_404.status_code = 404

        mock_get.side_effect = [mock_404, mock_404]

        gm = GitManager()
        gm.token = "test_token"

        success, details = gm.verify_path(
            "https://github.com/owner/nonexistent-repo/tree/main"
        )

        self.assertFalse(success)
        self.assertIn("not found", details["error"].lower())

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.get")
    def test_push_commit_file_github_with_child_path(
        self, mock_get, mock_put, mock_init
    ):
        """Test GitHub push with git_child_path"""
        mock_init.return_value = None

        mock_get_response = Mock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response

        mock_put_response = Mock()
        mock_put_response.status_code = 201
        mock_put_response.json.return_value = {}
        mock_put_response.text = "{}"
        mock_put.return_value = mock_put_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="content")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://github.com/owner/repo/tree/main/base",
                "commit msg",
                git_child_path="child/dir",
            )

        self.assertTrue(success)
        self.assertIn("child", details["file_path"])
        self.assertIn("dir", details["file_path"])

    @patch.object(GitManager, "__init__")
    @patch("requests.put")
    @patch("requests.get")
    def test_push_commit_file_github_no_change(self, mock_get, mock_put, mock_init):
        """GitHub: returns no_change=True when remote content is identical to local"""
        import base64

        mock_init.return_value = None

        file_content = "Identical content"

        # GET returns the same content already on remote
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "sha": "abc123",
            "type": "file",
            "content": base64.b64encode(file_content.encode("utf-8")).decode("utf-8"),
        }
        mock_get.return_value = mock_get_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://github.com/owner/repo/tree/main/doc2md",
                "doc2md#sync",
            )

        self.assertTrue(success)
        self.assertTrue(details.get("no_change"))
        self.assertEqual(details["message"], "File is identical to remote file in git")
        self.assertFalse(mock_put.called)


class TestGitManagerAzureDevOps(unittest.TestCase):
    """Test Azure DevOps-specific methods"""

    @patch.object(GitManager, "__init__")
    def test_parse_azure_url_dev(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        parts = gm._parse_azure_url(
            "https://dev.azure.com/myorg/myproject/_git/myrepo?path=/docs&version=GBmain"
        )
        self.assertEqual(parts["org"], "myorg")
        self.assertEqual(parts["project"], "myproject")
        self.assertEqual(parts["repo"], "myrepo")
        self.assertEqual(parts["branch"], "main")
        self.assertEqual(parts["subdir_path"], "docs")

    @patch.object(GitManager, "__init__")
    def test_parse_azure_url_visualstudio(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        parts = gm._parse_azure_url(
            "https://myorg.visualstudio.com/myproject/_git/myrepo"
        )
        self.assertEqual(parts["org"], "myorg")
        self.assertEqual(parts["project"], "myproject")
        self.assertEqual(parts["repo"], "myrepo")
        self.assertEqual(parts["branch"], "main")  # default branch

    @patch.object(GitManager, "__init__")
    def test_parse_azure_url_invalid(self, mock_init):
        mock_init.return_value = None
        gm = GitManager()
        gm.token = "test_token"
        with self.assertRaises(ValueError):
            gm._parse_azure_url("https://dev.azure.com/incomplete")

    @patch.object(GitManager, "__init__")
    @patch("requests.post")
    @patch("requests.get")
    def test_push_commit_file_azure_new_file(self, mock_get, mock_post, mock_init):
        """Test creating a new file on Azure DevOps"""
        mock_init.return_value = None

        # items check: file does not exist
        mock_items_response = Mock()
        mock_items_response.status_code = 404

        # refs response: branch found
        mock_refs_response = Mock()
        mock_refs_response.status_code = 200
        mock_refs_response.json.return_value = {
            "value": [{"objectId": "deadbeef0001", "name": "refs/heads/main"}]
        }

        mock_get.side_effect = [mock_items_response, mock_refs_response]

        # POST push: success
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {
            "refUpdates": [{"newObjectId": "newsha"}]
        }
        mock_post_response.text = "{}"
        mock_post.return_value = mock_post_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="# Test")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://dev.azure.com/myorg/myproject/_git/myrepo?path=/docs&version=GBmain",
                "doc2md#sync",
            )

        self.assertTrue(success)
        self.assertIn("created", details["message"])

        # Verify push payload has changeType "add"
        _, kwargs = mock_post.call_args
        change_type = kwargs["json"]["commits"][0]["changes"][0]["changeType"]
        self.assertEqual(change_type, "add")

    @patch.object(GitManager, "__init__")
    @patch("requests.post")
    @patch("requests.get")
    def test_push_commit_file_azure_update_file(self, mock_get, mock_post, mock_init):
        """Test updating an existing file on Azure DevOps"""
        mock_init.return_value = None

        # items check: file exists with different content
        mock_items_response = Mock()
        mock_items_response.status_code = 200
        mock_items_response.json.return_value = {
            "objectId": "existingsha",
            "content": "Old content",
        }

        # refs response
        mock_refs_response = Mock()
        mock_refs_response.status_code = 200
        mock_refs_response.json.return_value = {
            "value": [{"objectId": "deadbeef0002", "name": "refs/heads/main"}]
        }

        mock_get.side_effect = [mock_items_response, mock_refs_response]

        # POST push: success
        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {}
        mock_post_response.text = "{}"
        mock_post.return_value = mock_post_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="# Updated")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://dev.azure.com/myorg/myproject/_git/myrepo?version=GBmain",
                "doc2md#sync",
            )

        self.assertTrue(success)
        self.assertIn("updated", details["message"])

        # Verify push payload has changeType "edit"
        _, kwargs = mock_post.call_args
        change_type = kwargs["json"]["commits"][0]["changes"][0]["changeType"]
        self.assertEqual(change_type, "edit")

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_azure_valid(self, mock_get, mock_init):
        """Test Azure DevOps verify_path with valid path"""
        mock_init.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"path": "/docs/file1.md"},
                {"path": "/docs/file2.md"},
            ]
        }
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"

        success, details = gm.verify_path(
            "https://dev.azure.com/myorg/myproject/_git/myrepo?path=/docs&version=GBmain"
        )

        self.assertTrue(success)
        self.assertEqual(details["contents_count"], 2)
        self.assertEqual(details["branch"], "main")

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_verify_path_azure_path_not_found(self, mock_get, mock_init):
        """Test Azure DevOps verify_path when path doesn't exist"""
        mock_init.return_value = None

        mock_404 = Mock()
        mock_404.status_code = 404

        mock_repo_ok = Mock()
        mock_repo_ok.status_code = 200
        mock_repo_ok.json.return_value = {"id": "repo-guid"}

        mock_get.side_effect = [mock_404, mock_repo_ok]

        gm = GitManager()
        gm.token = "test_token"

        success, details = gm.verify_path(
            "https://dev.azure.com/myorg/myproject/_git/myrepo?path=/nonexistent&version=GBmain"
        )

        self.assertFalse(success)
        self.assertIn("Path not found", details["error"])

    @patch.object(GitManager, "__init__")
    @patch("requests.post")
    @patch("requests.get")
    def test_push_commit_file_azure_no_change(self, mock_get, mock_post, mock_init):
        """Azure DevOps: returns no_change=True when remote content is identical to local"""
        mock_init.return_value = None

        file_content = "Identical content"

        # items check: file exists with identical content
        mock_items_response = Mock()
        mock_items_response.status_code = 200
        mock_items_response.json.return_value = {
            "objectId": "existingsha",
            "content": file_content,
        }
        mock_get.return_value = mock_items_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data=file_content)
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://dev.azure.com/myorg/myproject/_git/myrepo?version=GBmain",
                "doc2md#sync",
            )

        self.assertTrue(success)
        self.assertTrue(details.get("no_change"))
        self.assertEqual(details["message"], "File is identical to remote file in git")
        self.assertFalse(mock_post.called)

    @patch.object(GitManager, "__init__")
    @patch("requests.post")
    @patch("requests.get")
    def test_push_commit_file_azure_check_exception_still_writes(
        self, mock_get, mock_post, mock_init
    ):
        """Azure: when items GET raises an exception, file_exists=False and write proceeds."""
        mock_init.return_value = None

        # items check raises an exception (e.g. network error)
        mock_refs_response = Mock()
        mock_refs_response.status_code = 200
        mock_refs_response.json.return_value = {
            "value": [{"objectId": "deadbeef0003", "name": "refs/heads/main"}]
        }
        mock_get.side_effect = [Exception("network error"), mock_refs_response]

        mock_post_response = Mock()
        mock_post_response.status_code = 201
        mock_post_response.json.return_value = {}
        mock_post_response.text = "{}"
        mock_post.return_value = mock_post_response

        gm = GitManager()
        gm.token = "test_token"

        m = unittest.mock.mock_open(read_data="content")
        with patch("builtins.open", m):
            success, details = gm.push_commit_file(
                "TestFile.md",
                "https://dev.azure.com/myorg/myproject/_git/myrepo?version=GBmain",
                "doc2md#sync",
            )

        # Write should still proceed with changeType "add" (file_exists=False)
        self.assertTrue(success)
        _, kwargs = mock_post.call_args
        change_type = kwargs["json"]["commits"][0]["changes"][0]["changeType"]
        self.assertEqual(change_type, "add")


class TestGetLastCommitTime(unittest.TestCase):
    """Test get_last_commit_time for all three providers"""

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_gitlab_success(self, mock_get, mock_init):
        """GitLab: +00:00 offset is correctly converted to UTC epoch float"""
        mock_init.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"committed_date": "2026-04-04T22:42:00.000+00:00", "id": "abc123"}
        ]
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"
        success, details = gm.get_last_commit_time(
            "test.md", "https://gitbud.epam.com/project/repo/-/tree/main/subdir"
        )

        self.assertTrue(success)
        self.assertIsInstance(details["committed_epoch"], float)
        self.assertAlmostEqual(details["committed_epoch"], 1775342520.0, delta=1)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_github_success(self, mock_get, mock_init):
        """GitHub: Z suffix is correctly converted to UTC epoch float"""
        mock_init.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"commit": {"committer": {"date": "2026-04-04T22:42:00Z"}}}
        ]
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"
        success, details = gm.get_last_commit_time(
            "test.md", "https://github.com/owner/repo/tree/main/subdir"
        )

        self.assertTrue(success)
        self.assertIsInstance(details["committed_epoch"], float)
        self.assertAlmostEqual(details["committed_epoch"], 1775342520.0, delta=1)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_azure_success(self, mock_get, mock_init):
        """Azure: Z suffix is correctly converted to UTC epoch float"""
        mock_init.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"committer": {"date": "2026-04-04T22:42:00Z"}, "commitId": "aaa"}
            ]
        }
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"
        success, details = gm.get_last_commit_time(
            "test.md",
            "https://dev.azure.com/myorg/myproject/_git/myrepo?path=/docs&version=GBmain",
        )

        self.assertTrue(success)
        self.assertIsInstance(details["committed_epoch"], float)
        self.assertAlmostEqual(details["committed_epoch"], 1775342520.0, delta=1)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_api_error(self, mock_get, mock_init):
        """Non-200 response returns failure"""
        mock_init.return_value = None
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"
        success, details = gm.get_last_commit_time(
            "test.md", "https://gitbud.epam.com/project/repo/-/tree/main/subdir"
        )

        self.assertFalse(success)
        self.assertIn("error", details)

    @patch.object(GitManager, "__init__")
    @patch("requests.get")
    def test_file_not_in_git(self, mock_get, mock_init):
        """200 with empty result (file not yet committed) returns failure"""
        mock_init.return_value = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        gm = GitManager()
        gm.token = "test_token"
        success, details = gm.get_last_commit_time(
            "test.md", "https://gitbud.epam.com/project/repo/-/tree/main/subdir"
        )

        self.assertFalse(success)
        self.assertIn("error", details)


if __name__ == "__main__":
    unittest.main()
