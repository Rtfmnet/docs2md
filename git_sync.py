import base64
import os
import re
import requests
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlparse


class GitManager:
    """
    Manages Git connections and file push operations for GitLab, GitHub, and Azure DevOps.
    """

    # Supported providers
    PROVIDER_GITLAB = "gitlab"
    PROVIDER_GITHUB = "github"
    PROVIDER_AZURE = "azure_devops"

    def __init__(self):
        """
        Initialize GitManager with a Git access token from .env file.
        The same token variable (GIT_ACCESS_TOKEN) is used for all providers.
        """
        load_dotenv()
        self.token = os.getenv("GIT_ACCESS_TOKEN")
        if not self.token:
            raise ValueError("'GIT_ACCESS_TOKEN' access token not found in .env file")

    # ------------------------------------------------------------------
    # Provider detection
    # ------------------------------------------------------------------

    def _detect_provider(self, url: str) -> str:
        """
        Detect the Git provider from a URL.

        Supported URL formats:
          GitLab  : https://<host>/<project>/-/tree/<branch>[/<path>]
          GitHub  : https://github.com/<owner>/<repo>/tree/<branch>[/<path>]
          Azure   : https://dev.azure.com/<org>/<project>/_git/<repo>[?path=...&version=GB<branch>]
                    https://<org>.visualstudio.com/<project>/_git/<repo>

        Returns:
            str: One of PROVIDER_GITLAB, PROVIDER_GITHUB, PROVIDER_AZURE
        Raises:
            ValueError: If provider cannot be determined from URL.
        """
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()

        if hostname == "github.com":
            return self.PROVIDER_GITHUB

        if hostname == "dev.azure.com" or hostname.endswith(".visualstudio.com"):
            return self.PROVIDER_AZURE

        # GitLab: any other host that uses the /-/ URL pattern
        if "/-/" in parsed.path:
            return self.PROVIDER_GITLAB

        raise ValueError(
            f"Cannot detect Git provider from URL: {url}. "
            "Supported: GitLab (contains '/-/'), GitHub (github.com), "
            "Azure DevOps (dev.azure.com or *.visualstudio.com)"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push_commit_file(
        self, file_path, git_path, commit_message, git_child_path=None
    ):
        """
        Commits and pushes a file to a Git repository (GitLab, GitHub, or Azure DevOps).

        Args:
            file_path (str): Path to local text file.
            git_path (str): URL to git repository tree
                (e.g. https://github.com/owner/repo/tree/main/subdir).
            commit_message (str): Commit message.
            git_child_path (str, optional): Additional child path to append to git_path subdir.

        Returns:
            tuple: (success, details) where success is bool and details is a dict.
        """
        try:
            provider = self._detect_provider(git_path)
        except ValueError as e:
            return False, {"error": str(e)}

        if provider == self.PROVIDER_GITHUB:
            return self._push_commit_file_github(
                file_path, git_path, commit_message, git_child_path
            )
        if provider == self.PROVIDER_AZURE:
            return self._push_commit_file_azure(
                file_path, git_path, commit_message, git_child_path
            )
        return self._push_commit_file_gitlab(
            file_path, git_path, commit_message, git_child_path
        )

    def get_last_commit_time(self, file_path, git_path, git_child_path=None):
        """
        Returns the last commit timestamp for a file in the remote Git repository.

        Args:
            file_path (str): Path to local file (basename is used to locate the remote file).
            git_path (str): URL to git repository tree.
            git_child_path (str, optional): Additional child path to append to git_path subdir.

        Returns:
            tuple: (success, details) where success is bool and details is a dict.
                On success: {"committed_epoch": <UTC float>, "file_path": ..., "project_path": ..., "branch": ...}
                On failure: {"error": ...}
        """
        try:
            provider = self._detect_provider(git_path)
        except ValueError as e:
            return False, {"error": str(e)}

        if provider == self.PROVIDER_GITHUB:
            return self._get_last_commit_time_github(
                file_path, git_path, git_child_path
            )
        if provider == self.PROVIDER_AZURE:
            return self._get_last_commit_time_azure(file_path, git_path, git_child_path)
        return self._get_last_commit_time_gitlab(file_path, git_path, git_child_path)

    def verify_path(self, git_url):
        """
        Verify that a given Git path is valid and accessible.

        Args:
            git_url (str): URL to git repository tree.

        Returns:
            tuple: (success, details) where success is bool and details is a dict.
        """
        try:
            provider = self._detect_provider(git_url)
        except ValueError as e:
            return False, {"error": str(e)}

        if provider == self.PROVIDER_GITHUB:
            return self._verify_path_github(git_url)
        if provider == self.PROVIDER_AZURE:
            return self._verify_path_azure(git_url)
        return self._verify_path_gitlab(git_url)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_child_path(subdir_path: str, git_child_path: str) -> str:
        """Merge subdir_path with git_child_path, stripping '.' segments."""
        normalized = git_child_path.replace("\\", "/").strip("/")
        normalized = "/".join(p for p in normalized.split("/") if p and p != ".")
        if normalized:
            return f"{subdir_path}/{normalized}" if subdir_path else normalized
        return subdir_path

    # ------------------------------------------------------------------
    # GitLab implementation
    # ------------------------------------------------------------------

    def _parse_gitlab_url(self, git_url):
        """
        Parse a GitLab tree URL into its components.

        Returns:
            dict with keys: hostname, project_path, branch, subdir_path
        Raises:
            ValueError on invalid format.
        """
        parsed_url = urlparse(git_url)
        hostname = parsed_url.netloc
        path_parts = parsed_url.path.strip("/").split("/-/")

        if len(path_parts) != 2:
            raise ValueError(f"Invalid GitLab URL format: {git_url}")

        project_path = path_parts[0]
        branch_path = path_parts[1]
        match = re.match(r"tree/([^/]+)(.*)", branch_path)
        if not match:
            raise ValueError(f"Invalid branch format in GitLab URL: {git_url}")

        branch = match.group(1)
        subdir_path = match.group(2).lstrip("/")
        return {
            "hostname": hostname,
            "project_path": project_path,
            "branch": branch,
            "subdir_path": subdir_path,
        }

    def _push_commit_file_gitlab(
        self, file_path, git_path, commit_message, git_child_path=None
    ):
        """Push a file to GitLab using the Repository Files API."""
        try:
            parts = self._parse_gitlab_url(git_path)
            hostname = parts["hostname"]
            project_path = parts["project_path"]
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]

            if git_child_path:
                subdir_path = self._normalize_child_path(subdir_path, git_child_path)

            encoded_project_path = urllib.parse.quote(project_path, safe="")
            headers = {"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"}

            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            file_name = os.path.basename(file_path)
            target_path = f"{subdir_path}/{file_name}" if subdir_path else file_name
            target_path = target_path.replace("//", "/")

            files_api_url = (
                f"https://{hostname}/api/v4/projects/{encoded_project_path}"
                f"/repository/files/{urllib.parse.quote(target_path, safe='')}"
            )

            file_payload = {
                "branch": branch,
                "content": file_content,
                "commit_message": commit_message,
            }

            try:
                file_check_response = requests.head(
                    files_api_url, headers=headers, params={"ref": branch}
                )
                file_exists = file_check_response.status_code == 200
            except Exception:
                file_exists = False

            if file_exists:
                response = requests.put(
                    files_api_url, headers=headers, json=file_payload
                )
                action_type = "updated"
            else:
                response = requests.post(
                    files_api_url, headers=headers, json=file_payload
                )
                action_type = "created"

            if response.status_code in [200, 201]:
                return True, {
                    "message": f"File {action_type} successfully",
                    "file_path": target_path,
                    "project_path": project_path,
                    "branch": branch,
                }
            else:
                # Race condition: file appeared between HEAD and POST → retry as PUT
                if (
                    not file_exists
                    and response.status_code == 400
                    and "file with this name already exists" in response.text.lower()
                ):
                    retry_response = requests.put(
                        files_api_url, headers=headers, json=file_payload
                    )
                    if retry_response.status_code in [200, 201]:
                        return True, {
                            "message": "File updated successfully",
                            "file_path": target_path,
                            "project_path": project_path,
                            "branch": branch,
                        }
                    else:
                        return False, {
                            "error": f"File update retry failed: {retry_response.status_code} - {retry_response.text}"
                        }
                else:
                    return False, {
                        "error": f"API request failed: {response.status_code} - {response.text}"
                    }

        except Exception as e:
            return False, {"error": f"File commit failed: {str(e)}"}

    def _get_last_commit_time_gitlab(self, file_path, git_path, git_child_path=None):
        """Fetch the last commit timestamp for a file from GitLab."""
        try:
            parts = self._parse_gitlab_url(git_path)
            hostname = parts["hostname"]
            project_path = parts["project_path"]
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]

            if git_child_path:
                subdir_path = self._normalize_child_path(subdir_path, git_child_path)

            file_name = os.path.basename(file_path)
            target_path = f"{subdir_path}/{file_name}" if subdir_path else file_name
            target_path = target_path.replace("//", "/")

            encoded_project_path = urllib.parse.quote(project_path, safe="")
            headers = {"PRIVATE-TOKEN": self.token}
            url = f"https://{hostname}/api/v4/projects/{encoded_project_path}/repository/commits"
            params = {"ref_name": branch, "path": target_path, "per_page": 1}

            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200 and response.json():
                committed_date = response.json()[0]["committed_date"]
                committed_epoch = datetime.fromisoformat(
                    committed_date.replace("Z", "+00:00")
                ).timestamp()
                return True, {
                    "committed_epoch": committed_epoch,
                    "file_path": target_path,
                    "project_path": project_path,
                    "branch": branch,
                }
            else:
                return False, {
                    "error": f"API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"Last commit time retrieval failed: {str(e)}"}

    def _verify_path_gitlab(self, git_url):
        """Verify a GitLab repository path using the Repository Tree API."""
        try:
            parts = self._parse_gitlab_url(git_url)
            hostname = parts["hostname"]
            project_path = parts["project_path"]
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]

            encoded_project_path = urllib.parse.quote(project_path, safe="")
            encoded_ref = urllib.parse.quote(branch, safe="")
            headers = {"PRIVATE-TOKEN": self.token}

            contents_url = f"https://{hostname}/api/v4/projects/{encoded_project_path}/repository/tree"
            params = {"ref": encoded_ref}
            if subdir_path:
                params["path"] = subdir_path

            response = requests.get(contents_url, headers=headers, params=params)

            if response.status_code == 200:
                return True, {
                    "message": "Repository and path verified successfully",
                    "project_path": project_path,
                    "branch": branch,
                    "subdirectory_path": subdir_path,
                    "contents_count": len(response.json()),
                }
            elif response.status_code == 404:
                repo_url = f"https://{hostname}/api/v4/projects/{encoded_project_path}"
                repo_response = requests.get(repo_url, headers=headers)
                if repo_response.status_code == 200:
                    return False, {"error": f"Path not found: {subdir_path}"}
                else:
                    return False, {
                        "error": f"Repository not found or inaccessible: {project_path}"
                    }
            elif response.status_code == 401:
                return False, {
                    "error": "Authentication failed. Check your Git access token."
                }
            else:
                return False, {
                    "error": f"API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"Verification failed: {str(e)}"}

    # ------------------------------------------------------------------
    # GitHub implementation
    # ------------------------------------------------------------------

    def _parse_github_url(self, git_url):
        """
        Parse a GitHub tree URL into its components.

        Supported format:
          https://github.com/<owner>/<repo>/tree/<branch>[/<path>]

        Returns:
            dict with keys: owner, repo, branch, subdir_path
        Raises:
            ValueError on invalid format.
        """
        parsed = urlparse(git_url)
        # path: /<owner>/<repo>/tree/<branch>[/<subdir>]
        path = parsed.path.strip("/")
        # Split off owner/repo then tree/branch/...
        match = re.match(r"([^/]+)/([^/]+)/tree/([^/]+)(.*)", path)
        if not match:
            raise ValueError(
                f"Invalid GitHub URL format: {git_url}. "
                "Expected: https://github.com/<owner>/<repo>/tree/<branch>[/<path>]"
            )
        owner = match.group(1)
        repo = match.group(2)
        branch = match.group(3)
        subdir_path = match.group(4).lstrip("/")
        return {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "subdir_path": subdir_path,
        }

    def _github_headers(self):
        """Build GitHub API request headers."""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get_last_commit_time_github(self, file_path, git_path, git_child_path=None):
        """Fetch the last commit timestamp for a file from GitHub."""
        try:
            parts = self._parse_github_url(git_path)
            owner = parts["owner"]
            repo = parts["repo"]
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]

            if git_child_path:
                subdir_path = self._normalize_child_path(subdir_path, git_child_path)

            file_name = os.path.basename(file_path)
            target_path = f"{subdir_path}/{file_name}" if subdir_path else file_name
            target_path = target_path.replace("//", "/")

            headers = self._github_headers()
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {"sha": branch, "path": target_path, "per_page": 1}

            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200 and response.json():
                committed_date = response.json()[0]["commit"]["committer"]["date"]
                committed_epoch = datetime.fromisoformat(
                    committed_date.replace("Z", "+00:00")
                ).timestamp()
                return True, {
                    "committed_epoch": committed_epoch,
                    "file_path": target_path,
                    "project_path": f"{owner}/{repo}",
                    "branch": branch,
                }
            else:
                return False, {
                    "error": f"GitHub API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"Last commit time retrieval failed: {str(e)}"}

    def _push_commit_file_github(
        self, file_path, git_path, commit_message, git_child_path=None
    ):
        """
        Push a file to GitHub using the Contents API.

        PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}
        Requires SHA of existing file for updates.
        """
        try:
            parts = self._parse_github_url(git_path)
            owner = parts["owner"]
            repo = parts["repo"]
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]

            if git_child_path:
                subdir_path = self._normalize_child_path(subdir_path, git_child_path)

            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            file_name = os.path.basename(file_path)
            target_path = f"{subdir_path}/{file_name}" if subdir_path else file_name
            target_path = target_path.replace("//", "/")

            headers = self._github_headers()
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{urllib.parse.quote(target_path, safe='/')}"

            # Check if the file already exists to get its SHA (required for updates)
            sha = None
            try:
                check_response = requests.get(
                    api_url, headers=headers, params={"ref": branch}
                )
                if check_response.status_code == 200:
                    sha = check_response.json().get("sha")
            except Exception:
                pass

            # Encode content as base64 (GitHub API requirement)
            encoded_content = base64.b64encode(file_content.encode("utf-8")).decode(
                "utf-8"
            )

            payload = {
                "message": commit_message,
                "content": encoded_content,
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha

            response = requests.put(api_url, headers=headers, json=payload)

            if response.status_code in [200, 201]:
                action_type = "updated" if sha else "created"
                return True, {
                    "message": f"File {action_type} successfully",
                    "file_path": target_path,
                    "project_path": f"{owner}/{repo}",
                    "branch": branch,
                }
            else:
                return False, {
                    "error": f"GitHub API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"File commit failed: {str(e)}"}

    def _verify_path_github(self, git_url):
        """
        Verify a GitHub repository path using the Contents API.

        GET https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}
        """
        try:
            parts = self._parse_github_url(git_url)
            owner = parts["owner"]
            repo = parts["repo"]
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]

            headers = self._github_headers()
            contents_path = (
                urllib.parse.quote(subdir_path, safe="/") if subdir_path else ""
            )
            api_url = (
                f"https://api.github.com/repos/{owner}/{repo}/contents/{contents_path}"
            )

            response = requests.get(api_url, headers=headers, params={"ref": branch})

            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else 1
                return True, {
                    "message": "Repository and path verified successfully",
                    "project_path": f"{owner}/{repo}",
                    "branch": branch,
                    "subdirectory_path": subdir_path,
                    "contents_count": count,
                }
            elif response.status_code == 404:
                # Check if it's the repo or path that doesn't exist
                repo_url = f"https://api.github.com/repos/{owner}/{repo}"
                repo_response = requests.get(repo_url, headers=headers)
                if repo_response.status_code == 200:
                    return False, {"error": f"Path not found: {subdir_path}"}
                else:
                    return False, {
                        "error": f"Repository not found or inaccessible: {owner}/{repo}"
                    }
            elif response.status_code == 401:
                return False, {
                    "error": "Authentication failed. Check your Git access token."
                }
            else:
                return False, {
                    "error": f"GitHub API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"Verification failed: {str(e)}"}

    # ------------------------------------------------------------------
    # Azure DevOps implementation
    # ------------------------------------------------------------------

    def _parse_azure_url(self, git_url):
        """
        Parse an Azure DevOps repository URL into components.

        Supported formats:
          https://dev.azure.com/{org}/{project}/_git/{repo}
          https://dev.azure.com/{org}/{project}/_git/{repo}?path=/{subdir}&version=GB{branch}
          https://{org}.visualstudio.com/{project}/_git/{repo}

        Returns:
            dict with keys: org, project, repo, branch, subdir_path, base_url
        Raises:
            ValueError on invalid format.
        """
        parsed = urlparse(git_url)
        hostname = parsed.netloc.lower()
        path = parsed.path.strip("/")
        query = dict(urllib.parse.parse_qsl(parsed.query))

        if hostname == "dev.azure.com":
            # path: {org}/{project}/_git/{repo}
            match = re.match(r"([^/]+)/([^/]+)/_git/([^/]+)", path)
            if not match:
                raise ValueError(f"Invalid Azure DevOps URL format: {git_url}")
            org = match.group(1)
            project = match.group(2)
            repo = match.group(3)
            base_url = (
                f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}"
            )
        elif hostname.endswith(".visualstudio.com"):
            # path: {project}/_git/{repo}
            org = hostname.split(".")[0]
            match = re.match(r"([^/]+)/_git/([^/]+)", path)
            if not match:
                raise ValueError(
                    f"Invalid Azure DevOps visualstudio.com URL format: {git_url}"
                )
            project = match.group(1)
            repo = match.group(2)
            base_url = (
                f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}"
            )
        else:
            raise ValueError(f"Unrecognised Azure DevOps hostname: {hostname}")

        # Branch from query param: version=GB<branch>
        branch = "main"
        version_param = query.get("version", "")
        if version_param.startswith("GB"):
            branch = version_param[2:]

        # Subdirectory from path query param
        subdir_path = query.get("path", "").strip("/")

        return {
            "org": org,
            "project": project,
            "repo": repo,
            "branch": branch,
            "subdir_path": subdir_path,
            "base_url": base_url,
        }

    def _azure_headers(self):
        """Build Azure DevOps API request headers using Basic auth with PAT."""
        # Azure DevOps uses Basic auth: base64(":"  + token)
        credentials = base64.b64encode(f":{self.token}".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    def _get_last_commit_time_azure(self, file_path, git_path, git_child_path=None):
        """Fetch the last commit timestamp for a file from Azure DevOps."""
        try:
            parts = self._parse_azure_url(git_path)
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]
            base_url = parts["base_url"]
            api_version = "7.0"

            if git_child_path:
                subdir_path = self._normalize_child_path(subdir_path, git_child_path)

            file_name = os.path.basename(file_path)
            target_path = (
                f"/{subdir_path}/{file_name}" if subdir_path else f"/{file_name}"
            )
            target_path = target_path.replace("//", "/")

            headers = self._azure_headers()
            url = (
                f"{base_url}/commits"
                f"?searchCriteria.itemPath={urllib.parse.quote(target_path)}"
                f"&searchCriteria.itemVersion.version={urllib.parse.quote(branch)}"
                f"&searchCriteria.itemVersion.versionType=branch"
                f"&$top=1&api-version={api_version}"
            )

            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                commits = response.json().get("value", [])
                if commits:
                    committed_date = commits[0]["committer"]["date"]
                    committed_epoch = datetime.fromisoformat(
                        committed_date.replace("Z", "+00:00")
                    ).timestamp()
                    return True, {
                        "committed_epoch": committed_epoch,
                        "file_path": target_path,
                        "project_path": f"{parts['org']}/{parts['project']}/{parts['repo']}",
                        "branch": branch,
                    }
            return False, {
                "error": f"Azure DevOps API request failed: {response.status_code} - {response.text}"
            }

        except Exception as e:
            return False, {"error": f"Last commit time retrieval failed: {str(e)}"}

    def _push_commit_file_azure(
        self, file_path, git_path, commit_message, git_child_path=None
    ):
        """
        Push a file to Azure DevOps using the Git Push API.

        POST https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pushes
        """
        try:
            parts = self._parse_azure_url(git_path)
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]
            base_url = parts["base_url"]

            if git_child_path:
                subdir_path = self._normalize_child_path(subdir_path, git_child_path)

            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            file_name = os.path.basename(file_path)
            target_path = (
                f"/{subdir_path}/{file_name}" if subdir_path else f"/{file_name}"
            )
            target_path = target_path.replace("//", "/")

            headers = self._azure_headers()
            api_version = "7.0"

            # Check if the file already exists
            items_url = (
                f"{base_url}/items"
                f"?path={urllib.parse.quote(target_path)}"
                f"&versionDescriptor.versionType=branch"
                f"&versionDescriptor.version={urllib.parse.quote(branch)}"
                f"&api-version={api_version}"
            )
            check_response = requests.get(items_url, headers=headers)
            file_exists = check_response.status_code == 200

            # Get the latest commit SHA on the branch (required for push)
            refs_url = f"{base_url}/refs?filter=heads/{urllib.parse.quote(branch)}&api-version={api_version}"
            refs_response = requests.get(refs_url, headers=headers)
            if refs_response.status_code != 200:
                return False, {
                    "error": f"Failed to get branch ref: {refs_response.status_code} - {refs_response.text}"
                }
            refs_data = refs_response.json()
            if not refs_data.get("value"):
                return False, {"error": f"Branch '{branch}' not found"}
            old_object_id = refs_data["value"][0]["objectId"]

            change_type = "edit" if file_exists else "add"
            push_payload = {
                "refUpdates": [
                    {
                        "name": f"refs/heads/{branch}",
                        "oldObjectId": old_object_id,
                    }
                ],
                "commits": [
                    {
                        "comment": commit_message,
                        "changes": [
                            {
                                "changeType": change_type,
                                "item": {"path": target_path},
                                "newContent": {
                                    "content": file_content,
                                    "contentType": "rawtext",
                                },
                            }
                        ],
                    }
                ],
            }

            push_url = f"{base_url}/pushes?api-version={api_version}"
            response = requests.post(push_url, headers=headers, json=push_payload)

            if response.status_code in [200, 201]:
                action_type = "updated" if file_exists else "created"
                return True, {
                    "message": f"File {action_type} successfully",
                    "file_path": target_path,
                    "project_path": f"{parts['org']}/{parts['project']}/{parts['repo']}",
                    "branch": branch,
                }
            else:
                return False, {
                    "error": f"Azure DevOps API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"File commit failed: {str(e)}"}

    def _verify_path_azure(self, git_url):
        """
        Verify an Azure DevOps repository path using the Items API.

        GET https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items
        """
        try:
            parts = self._parse_azure_url(git_url)
            branch = parts["branch"]
            subdir_path = parts["subdir_path"]
            base_url = parts["base_url"]
            api_version = "7.0"

            headers = self._azure_headers()
            path_param = f"/{subdir_path}" if subdir_path else "/"

            items_url = (
                f"{base_url}/items"
                f"?path={urllib.parse.quote(path_param)}"
                f"&recursionLevel=OneLevel"
                f"&versionDescriptor.versionType=branch"
                f"&versionDescriptor.version={urllib.parse.quote(branch)}"
                f"&api-version={api_version}"
            )
            response = requests.get(items_url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                count = len(data.get("value", []))
                return True, {
                    "message": "Repository and path verified successfully",
                    "project_path": f"{parts['org']}/{parts['project']}/{parts['repo']}",
                    "branch": branch,
                    "subdirectory_path": subdir_path,
                    "contents_count": count,
                }
            elif response.status_code == 404:
                repo_url = f"{base_url}?api-version={api_version}"
                repo_response = requests.get(repo_url, headers=headers)
                if repo_response.status_code == 200:
                    return False, {"error": f"Path not found: {subdir_path}"}
                else:
                    return False, {
                        "error": f"Repository not found or inaccessible: {parts['repo']}"
                    }
            elif response.status_code == 401:
                return False, {
                    "error": "Authentication failed. Check your Git access token."
                }
            else:
                return False, {
                    "error": f"Azure DevOps API request failed: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return False, {"error": f"Verification failed: {str(e)}"}


if __name__ == "__main__":
    # Manual test runner for GitLab and GitHub
    git_manager = GitManager()

    print("===== TESTING GIT MANAGER VERIFY_PATH (GitLab) =====\n")
    test_path = "https://gitbud.epam.com/slbn-awop/aws-ai-sandbox/-/tree/main"
    print(f"Testing URL: {test_path}")
    success, result = git_manager.verify_path(test_path)
    if success:
        print(f"[OK] {result['message']} | contents: {result['contents_count']}")
    else:
        print(f"[FAIL] {result.get('error')}")

    print("\n===== TESTING GIT MANAGER VERIFY_PATH (GitHub) =====\n")
    test_path_gh = "https://github.com/Rtfmnet/test-data/tree/main/doc2md"
    print(f"Testing URL: {test_path_gh}")
    success, result = git_manager.verify_path(test_path_gh)
    if success:
        print(f"[OK] {result['message']} | contents: {result['contents_count']}")
    else:
        print(f"[FAIL] {result.get('error')}")

    print("\n===== TESTING COMMIT_PUSH_FILE (GitLab) =====\n")
    success, result = git_manager.push_commit_file(
        "tests/manual_tests/git/TestFile.md",
        "https://gitbud.epam.com/slbn-awop/aws-ai-sandbox/-/tree/main",
        "doc2md#sync",
    )
    if success:
        print(f"[OK] {result['message']} → {result['file_path']}")
    else:
        print(f"[FAIL] {result.get('error')}")

    print("\n===== TESTING COMMIT_PUSH_FILE (GitHub) =====\n")
    success, result = git_manager.push_commit_file(
        "tests/manual_tests/git/TestFile.md",
        "https://github.com/Rtfmnet/test-data/tree/main/doc2md",
        "doc2md#sync",
    )
    if success:
        print(f"[OK] {result['message']} → {result['file_path']}")
    else:
        print(f"[FAIL] {result.get('error')}")
