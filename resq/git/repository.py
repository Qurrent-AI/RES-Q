import os
import shutil
import tempfile
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Dict, Iterator, Optional, List, Tuple

from .utils import (
    aapply_patch,
    aclone,
    aforce_checkout,
    aget_branch_name,
    aget_diff,
    aget_next_commit,
    aget_repo_diff,
    apply_patch,
    clone,
    force_checkout,
    get_branch_name,
    get_default_branch_name,
    get_diff,
    get_next_commit,
    get_repo_diff,
    get_status,
)
from ..utils import log_run_subprocess, log_run_subprocess_sync


class Repository(
    AbstractContextManager["Repository"], AbstractAsyncContextManager["Repository"]
):
    """
    Represents a GitHub repository
    """

    def __init__(
        self, repo_url: str, temp_dir: str = tempfile.mkdtemp(), persist: bool = False
    ):
        self.repo_url = repo_url
        self.repo_name = self.repo_url.split("/")[-1]
        self.temp_dir = os.path.abspath(os.path.join(temp_dir, self.repo_name))
        self._path: Optional[str] = None
        self._default_branch: Optional[str] = None
        self._persist = persist

    def __enter__(self) -> "Repository":
        self._path = self.temp_dir
        clone(repo_url=self.repo_url, repo_dir=self.temp_dir)
        return self

    async def __aenter__(self) -> "Repository":
        self._path = self.temp_dir
        await aclone(repo_url=self.repo_url, repo_dir=self.temp_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        if not self._persist:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            self._path = None

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        if not self._persist:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            self._path = None

    @classmethod
    def from_path(cls, path: str, persist: bool = True) -> "Repository":
        """
        Creates a Repository object from an existing directory
        """
        if not os.path.exists(path):
            raise ValueError("The directory does not exist")
        elif not get_status(repo_dir=path):
            raise ValueError("The directory is not a valid git repository")
        else:
            repo = cls(repo_url="", temp_dir=path, persist=persist)
            repo._path = path
            return repo

    @property
    def default_branch(self) -> str:
        """
        Return's the name of the remote's default branch
        """
        if self._default_branch is None:
            self._default_branch = (
                f"origin/{get_default_branch_name(repo_dir=self.path)}"
            )
        return self._default_branch

    @property
    def path(self) -> str:
        """
        Returns the path to the root of the repo
        """
        if self._path is not None:
            return self._path
        else:
            raise ValueError("Tried to get repo path when not opened")

    @property
    def files(self) -> Iterator[Dict[str, str]]:
        """
        Returns an iterator over the files in the repo
        """
        for root, _, files in os.walk(self.path):
            for file in files:
                try:
                    abs_path = os.path.join(root, file)
                    relative_path = os.path.relpath(abs_path, self.path)
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        content = f.read()
                    yield {
                        "filename": file,
                        "filepath": os.path.join(root, file),
                        "rel_filepath": relative_path,
                        "content": content,
                    }
                except UnicodeDecodeError:
                    continue

    def get_file(self, relative_path: str) -> Optional[str]:
        """
        Return the content in the file with given relative path (to the root of the repo)
        Returns None if the content is not utf-8 encoded
        """
        try:
            abs_path = os.path.join(self.path, relative_path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            else:
                return None
        except UnicodeDecodeError:
            return None

    def reset(self, commit_hash: str) -> None:
        """
        Resets the repository to the specified commit hash
        """
        force_checkout(repo_dir=self.path, commit_hash=commit_hash)

    async def areset(self, commit_hash: str) -> None:
        """
        Resets the repository to the specified commit hash
        """
        await aforce_checkout(repo_dir=self.path, commit_hash=commit_hash)

    def get_repo_diff(self, commit: str) -> str:
        """
        Returns the diff between the repository and the specified commit
        """
        return get_repo_diff(repo_dir=self.path, commit_hash=commit)

    async def aget_repo_diff(self, commit: str) -> str:
        """
        Returns the diff between the repository and the specified commit
        """
        return await aget_repo_diff(repo_dir=self.path, commit_hash=commit)

    def get_diff(self, parent_commit: str, child_commit: str) -> str:
        """
        Returns the diff between two specified commits
        """
        return get_diff(
            repo_dir=self.path, parent_commit=parent_commit, child_commit=child_commit
        )

    async def aget_diff(self, parent_commit: str, child_commit: str) -> str:
        """
        Returns the diff between two specified commits
        """
        return await aget_diff(
            repo_dir=self.path, parent_commit=parent_commit, child_commit=child_commit
        )

    def get_branch_name(self, commit_hash: str) -> Optional[str]:
        """
        Retrieves the branch name for the given commit hash
        """
        return get_branch_name(repo_dir=self.path, commit_hash=commit_hash)

    async def aget_branch_name(self, commit_hash: str) -> Optional[str]:
        """
        Retrieves the branch name for the given commit hash
        """
        return await aget_branch_name(repo_dir=self.path, commit_hash=commit_hash)

    def get_next_commit(self, parent_commit_hash: str) -> Optional[str]:
        """
        Finds the next commit hash in the repository after the given parent commit hash
        """
        return get_next_commit(
            repo_dir=self.path, parent_commit_hash=parent_commit_hash
        )

    async def aget_next_commit(self, parent_commit_hash: str) -> Optional[str]:
        """
        Finds the next commit hash in the repository after the given parent commit hash
        """
        return await aget_next_commit(
            repo_dir=self.path, parent_commit_hash=parent_commit_hash
        )

    def apply_patch(self, patch: str) -> Tuple[bool, str]:
        """
        Applies a patch to the repository and returns whether it was successful and the stderr
        """
        return apply_patch(patch=patch, repo_dir=self.path)

    async def aapply_patch(self, patch: str) -> Tuple[bool, str]:
        """
        Applies a patch to the repository and returns whether it was successful and the stderr
        """
        return await aapply_patch(patch=patch, repo_dir=self.path)

    def run(self, command: List[str]) -> Tuple[bool, str, str]:
        """
        Runs a git command in the repository and returns the (success, stdout, stderr)
        """
        command = ["git", "-C", self.path] + command
        return log_run_subprocess_sync(command=command)

    async def arun(self, command: List[str]) -> Tuple[bool, str, str]:
        """
        Runs a git command in the repository and returns the (success, stdout, stderr)
        """
        command = ["git", "-C", self.path] + command
        return await log_run_subprocess(command=command)
