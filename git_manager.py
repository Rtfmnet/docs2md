import os
import re
import requests
import subprocess
from dotenv import load_dotenv
from urllib.parse import urlparse


class GitManager:
    """
    Class to manage GitLab connections and operations.
    """
    def __init__(self):
        """
        Initialize GitManager with GitLab access token from .env file.
        """
        # Load environment variables from .env file
        load_dotenv()

        # Get GitLab access token
        self.token = os.getenv('GIT_ACCESS_TOKEN')
        if not self.token:
            raise ValueError("GitLab access token not found in .env file")
    
    def push_commit_file(self, file_path, git_path, commit_message, git_child_path=None):
        """
        Commits and pushes a file to a Git repository.
    
        Args:
            file_path (str): Path to local text file
            git_path (str): Path to git repository
            commit_message (str): Commit message
            git_child_path (str, optional): Additional child path to append to the git_path. Defaults to None.
    
        Returns:
            tuple: (success, details) where success is a boolean and details is a dict with results
        """
        try:
            # Extract repository components from URL
            parsed_url = urlparse(git_path)
            hostname = parsed_url.netloc
            path_parts = parsed_url.path.strip('/').split('/-/')
    
            if len(path_parts) != 2:
                return False, {'error': f"Invalid GitLab URL format: {git_path}"}
    
            # Extract project path (e.g., slbn-awop/aws-ai)
            project_path = path_parts[0]
    
            # Extract branch and subdir (e.g., tree/main/sandbox)
            branch_path = path_parts[1]
            match = re.match(r'tree/([^/]+)(.*)', branch_path)
    
            if not match:
                return False, {'error': f"Invalid branch format in URL: {git_path}"}
    
            branch = match.group(1)
            subdir_path = match.group(2).lstrip('/')
    
            # URL encode components for API
            import urllib.parse
            encoded_project_path = urllib.parse.quote(project_path, safe='')
    
            # Create headers with token
            headers = {'PRIVATE-TOKEN': self.token, 'Content-Type': 'application/json'}
    
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
    
            # Get file name from path
            file_name = os.path.basename(file_path)
    
            # Process git_child_path if provided
            if git_child_path:
                # Normalize the child path format (handle different slash formats)
                normalized_child_path = git_child_path.replace('\\', '/')
                # Remove leading and trailing slashes if present
                normalized_child_path = normalized_child_path.strip('/')
    
                # Combine with the existing subdir_path
                if subdir_path:
                    subdir_path = f"{subdir_path}/{normalized_child_path}"
                else:
                    subdir_path = normalized_child_path
    
            # Path in the repository where the file should be committed
            target_path = f"{subdir_path}/{file_name}" if subdir_path else file_name
            target_path = target_path.replace('//', '/')
    
            # Use the Repository Files API instead of Commits API
            # This allows better handling of create vs update operations
            files_api_url = f"https://{hostname}/api/v4/projects/{encoded_project_path}/repository/files/{urllib.parse.quote(target_path, safe='')}"
    
            # Common payload for both create and update operations
            file_payload = {
                'branch': branch,
                'content': file_content,
                'commit_message': commit_message
            }
    
            # First check if the file exists by doing a HEAD request
            try:
                file_check_response = requests.head(files_api_url, headers=headers, params={'ref': branch})
                file_exists = file_check_response.status_code == 200
            except Exception:
                file_exists = False
    
            # Use PUT for existing files, POST for new files
            if file_exists:
                response = requests.put(files_api_url, headers=headers, json=file_payload)
                action_type = "updated"
            else:
                response = requests.post(files_api_url, headers=headers, json=file_payload)
                action_type = "created"
    
            if response.status_code in [200, 201]:
                return True, {
                    'message': f"File {action_type} successfully",
                    'file_path': target_path,
                    'project_path': project_path,
                    'branch': branch
                }
            else:
                # If we get a 400 with "file already exists" when trying to create,
                # retry as an update operation
                if not file_exists and response.status_code == 400 and "file with this name already exists" in response.text.lower():
                    # Retry as update
                    retry_response = requests.put(files_api_url, headers=headers, json=file_payload)
                    if retry_response.status_code in [200, 201]:
                        return True, {
                            'message': f"File updated successfully",
                            'file_path': target_path,
                            'project_path': project_path,
                            'branch': branch
                        }
                    else:
                        return False, {'error': f"File update retry failed: {retry_response.status_code} - {retry_response.text}"}
                else:
                    return False, {'error': f"API request failed: {response.status_code} - {response.text}"}
    
        except Exception as e:
            return False, {'error': f"File commit failed: {str(e)}"}
    
    def verify_path(self, git_url):
        """
        Verify that the given GitLab path is valid and accessible in one simple call.
    
        This method makes a single API call to verify:
        1. The URL format is valid
        2. The repository exists and is accessible
        3. The specific path exists (if specified)
        4. The Git token has sufficient permissions
    
        Args:
            git_url (str): GitLab URL like https://gitbud.epam.com/slbn-awop/aws-ai/-/tree/main/sandbox
    
        Returns:
            tuple: (success, details) where success is a boolean and details is a dict with verification results
        """
        # Parse the URL to extract components
        try:
            # Extract repository components from URL
            parsed_url = urlparse(git_url)
            hostname = parsed_url.netloc
            path_parts = parsed_url.path.strip('/').split('/-/')
    
            if len(path_parts) != 2:
                return False, {'error': f"Invalid GitLab URL format: {git_url}"}
    
            # Extract project path (e.g., slbn-awop/aws-ai)
            project_path = path_parts[0]
    
            # Extract branch and subdir (e.g., tree/main/sandbox)
            branch_path = path_parts[1]
            match = re.match(r'tree/([^/]+)(.*)', branch_path)
    
            if not match:
                return False, {'error': f"Invalid branch format in URL: {git_url}"}
    
            branch = match.group(1)
            subdir_path = match.group(2).lstrip('/')
    
            # URL encode components for API
            import urllib.parse
            encoded_project_path = urllib.parse.quote(project_path, safe='')
            encoded_ref = urllib.parse.quote(branch, safe='')
    
            # Create headers with token
            headers = {'PRIVATE-TOKEN': self.token}
    
            # Make API call to check repository and path
            contents_url = f"https://{hostname}/api/v4/projects/{encoded_project_path}/repository/tree"
            params = {'ref': encoded_ref}
    
            if subdir_path:
                params['path'] = subdir_path
    
            # Make the request - this checks repository exists and path is valid
            response = requests.get(contents_url, headers=headers, params=params)
    
            if response.status_code == 200:
                # Success - both repo and path are valid
                return True, {
                    'message': "Repository and path verified successfully",
                    'project_path': project_path,
                    'branch': branch,
                    'subdirectory_path': subdir_path,
                    'contents_count': len(response.json())
                }
            elif response.status_code == 404:
                # Check if it's the repository or the path that's invalid
                # Try to access just the repository
                repo_url = f"https://{hostname}/api/v4/projects/{encoded_project_path}"
                repo_response = requests.get(repo_url, headers=headers)
    
                if repo_response.status_code == 200:
                    # Repository exists, so it must be the path that's invalid
                    return False, {'error': f"Path not found: {subdir_path}"}
                else:
                    # Repository doesn't exist or is inaccessible
                    return False, {'error': f"Repository not found or inaccessible: {project_path}"}
            elif response.status_code == 401:
                return False, {'error': "Authentication failed. Check your Git access token."}
            else:
                return False, {'error': f"API request failed: {response.status_code} - {response.text}"}
    
        except Exception as e:
            return False, {'error': f"Verification failed: {str(e)}"}


if __name__ == "__main__":
    # Test the simplified verify_path method
    git_manager = GitManager()

    print("===== TESTING GIT MANAGER VERIFY_PATH =====\n")

    # Test with a valid repository URL
    test_path = "https://gitbud.epam.com/slbn-awop/aws-ai/-/tree/main/sandbox"
    print(f"Testing URL: {test_path}")

    success, result = git_manager.verify_path(test_path)

    if success:
        print("\n✅ Verification successful!")
        print(f"Project: {result['project_path']}")
        print(f"Branch: {result['branch']}")
        print(f"Path: {result['subdirectory_path']}")
        print(f"Contents count: {result['contents_count']}")
        print(f"Message: {result['message']}")
    else:
        print("\n❌ Verification failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Test the commit_push_file method
    print("\n===== TESTING GIT MANAGER COMMIT_PUSH_FILE =====\n")

    # Test file path and git path
    test_file_path = "manual_tests/git/TestFile.md"
    test_git_path = "https://gitbud.epam.com/slbn-awop/aws-ai/-/tree/main/sandbox"
    test_commit_message = "Test file path and git path"

    print(f"Testing commit_push_file with:")
    print(f"File: {test_file_path}")
    print(f"Git Path: {test_git_path}")
    print(f"Commit Message: {test_commit_message}")

    success, result = git_manager.push_commit_file(test_file_path, test_git_path, test_commit_message)

    if success:
        print("\n✅ Commit and push successful!")
        print(f"File path: {result['file_path']}")
        print(f"Project: {result['project_path']}")
        print(f"Branch: {result['branch']}")
        print(f"Message: {result['message']}")
    else:
        print("\n❌ Commit and push failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")
        
    # Test the commit_push_file method with git_child_path
    print("\n===== TESTING GIT MANAGER COMMIT_PUSH_FILE WITH CHILD PATH =====\n")

    # Test file path, git path and child path
    test_file_path = "manual_tests/git/TestFile.md"
    test_git_path = "https://gitbud.epam.com/slbn-awop/aws-ai/-/tree/main/sandbox"
    test_child_path = "test-sub-dir"
    test_commit_message = "Test file path and git path with child"

    print(f"Testing commit_push_file with:")
    print(f"File: {test_file_path}")
    print(f"Git Path: {test_git_path}")
    print(f"Child Path: {test_child_path}")
    print(f"Commit Message: {test_commit_message}")

    success, result = git_manager.push_commit_file(test_file_path, test_git_path, test_commit_message, git_child_path=test_child_path)

    if success:
        print("\n✅ Commit and push successful!")
        print(f"File path: {result['file_path']}")
        print(f"Project: {result['project_path']}")
        print(f"Branch: {result['branch']}")
        print(f"Message: {result['message']}")
    else:
        print("\n❌ Commit and push failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")