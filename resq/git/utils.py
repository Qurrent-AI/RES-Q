import logging
import os
import re
import subprocess
from typing import List, Literal, Optional, Union, Tuple, Callable

import aiofiles

from ..utils import log_run_subprocess, log_run_subprocess_sync


def format_patch(patch: str) -> str:
    """
    Format the patch
    """
    formatters: List[Callable[[str], str]] = [filter_binary_patch]
    for formatter in formatters:
        try:
            patch = formatter(patch)
        except Exception:
            logging.exception("Error formatting patch with %s", formatter)
            continue
    return patch


def filter_binary_patch(patch: str) -> str:
    """
    Filter out binary patches from the patch
    """
    lines = patch.splitlines(keepends=True)

    filtered_lines = []

    in_binary_section = False

    # Regular expressions to match the binary patch indicators
    binary_patch_start = re.compile(r"^GIT binary patch$")
    binary_patch_header = re.compile(r"^index ")
    binary_files_differ = re.compile(r"^Binary files .* and .* differ$")
    git_diff_line = re.compile(r"^diff --git ")

    i = 0
    while i < len(lines):
        line = lines[i]
        if binary_patch_start.match(line):
            in_binary_section = True
            i += 1
            continue
        elif binary_patch_header.match(line):
            i += 1
            continue
        elif binary_files_differ.match(line):
            in_binary_section = False
            i += 1
            continue

        if git_diff_line.match(line):
            # Check if this is a binary files diff
            if i + 2 < len(lines) and binary_files_differ.match(lines[i + 2]):
                # Skip the diff line, index line, and the binary files differ line
                i += 3
                continue

        if not in_binary_section:
            filtered_lines.append(line)

        i += 1

    filtered_patch = "".join(filtered_lines)
    return filtered_patch


def extract_modified_files(patch: str) -> List[str]:
    """
    Return a list of files in the diff where more than spaces/newlines are changed
    """
    # Regular expression to find file paths and change lines
    file_path_regex = re.compile(r"^diff --git a\/(.*?) b\/(.*?)$", re.MULTILINE)
    change_line_regex = re.compile(r"^[\+\-](?!\+\+|\-\-)(.*)$", re.MULTILINE)

    modified_files = []
    current_file = None
    found_significant_change = False

    for line in patch.splitlines():
        file_path_match = file_path_regex.match(line)
        change_line_match = change_line_regex.match(line)

        if file_path_match:
            if current_file and found_significant_change:
                modified_files.append(current_file)

            current_file = file_path_match.group(1)
            found_significant_change = False
        elif change_line_match:
            if change_line_match.group(1).strip():
                found_significant_change = True

    if current_file and found_significant_change:
        modified_files.append(current_file)

    return modified_files


async def aapply_patch(patch: str, repo_dir: str) -> Tuple[bool, str]:
    """
    Apply the patch to the repo with the given directory
    """
    patch_file = "temp.patch"
    patch_path = os.path.join(repo_dir, "..", patch_file)

    async with aiofiles.open(patch_path, "w", encoding="utf-8") as f:
        await f.write(patch)

    # Apply patch to testbed directory
    apply_cmd = [
        "git",
        "-C",
        repo_dir,
        "apply",
        "--reject",
        "--whitespace=fix",
        # "--allow-empty",
        "-v",
        os.path.join("..", patch_file),
    ]

    success, _, stderr = await log_run_subprocess(apply_cmd)

    os.remove(patch_path)
    return success, stderr


def apply_patch(patch: str, repo_dir: str) -> Tuple[bool, str]:
    """
    Apply the patch to the repo with the given directory
    """
    patch_file = "temp.patch"
    patch_path = os.path.join(repo_dir, "..", patch_file)

    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(patch)

    # Apply patch to testbed directory
    apply_cmd = [
        "git",
        "-C",
        repo_dir,
        "apply",
        # "--allow-empty",
        "-v",
        os.path.join("..", patch_file),
    ]
    apply_process = subprocess.run(
        apply_cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout = apply_process.stdout.decode("utf-8")
    stderr = apply_process.stderr.decode("utf-8")
    logging.debug("====== Patch stdout: ======\n%s", stdout)
    logging.debug("====== Patch stderr: ======\n%s", stderr)
    os.remove(patch_path)
    return apply_process.returncode == 0, stderr


async def aclone(repo_url: str, repo_dir: str) -> None:
    """
    Clone the repo with the given url into the dir
    """
    if not os.path.exists(repo_dir):
        clone_cmd = ["git", "clone", repo_url, repo_dir]
        await log_run_subprocess(clone_cmd)


def clone(repo_url: str, repo_dir: str) -> None:
    """
    Clone the repo with the given url into the dir
    """
    if not os.path.exists(repo_dir):
        clone_cmd = ["git", "clone", repo_url, repo_dir]
        subprocess.run(clone_cmd, check=True)


async def aforce_checkout(repo_dir: str, commit_hash: str) -> None:
    """
    Checkout the commit hash and remove local changes
    """
    reset_cmd = ["git", "-C", repo_dir, "reset", "--hard", commit_hash]
    await log_run_subprocess(reset_cmd)

    clean_cmd = ["git", "-C", repo_dir, "clean", "-fdx"]
    await log_run_subprocess(clean_cmd)


def force_checkout(repo_dir: str, commit_hash: str) -> None:
    """
    Checkout the commit hash and remove local changes
    """
    reset_cmd = ["git", "-C", repo_dir, "reset", "--hard", commit_hash]
    subprocess.run(reset_cmd, check=True)

    clean_cmd = ["git", "-C", repo_dir, "clean", "-fdx"]
    subprocess.run(clean_cmd, check=True)


async def aget_diff(repo_dir: str, parent_commit: str, child_commit: str) -> str:
    """
    Return the patch file for the two commits for the given repo
    """
    diff_cmd = [
        "git",
        "-C",
        repo_dir,
        "diff",
        parent_commit,
        child_commit,
        "--",
        ".",
        ":(exclude)__pycache__/*",
        ":(exclude)*/__pycache__/*",
    ]
    # diff_cmd = ["git", "-C", repo_dir, "diff", parent_commit, child_commit]
    _, stdout, _ = await log_run_subprocess(diff_cmd)
    patch = stdout
    patch = "\n".join(
        line for line in patch.split("\n") if not line.startswith("index ")
    )
    return patch


def get_diff(repo_dir: str, parent_commit: str, child_commit: str) -> str:
    """
    Return the patch file for the two commits for the given repo
    """
    diff_cmd = [
        "git",
        "-C",
        repo_dir,
        "diff",
        parent_commit,
        child_commit,
        "--",
        ".",
        ":(exclude)__pycache__/*",
        ":(exclude)*/__pycache__/*",
    ]
    # diff_cmd = ["git", "-C", repo_dir, "diff", parent_commit, child_commit]
    patch = subprocess.run(diff_cmd, check=True, capture_output=True, text=True).stdout
    patch = "\n".join(
        line for line in patch.split("\n") if not line.startswith("index ")
    )

    return patch


async def aget_repo_diff(repo_dir: str, commit_hash: str) -> str:
    """
    Return the patch file for the diff between the current repo and the commit hash
    """
    diff_cmd = [
        "git",
        "-C",
        repo_dir,
        "diff",
        commit_hash,
        "--",
        ".",
        ":(exclude)__pycache__/*",
        ":(exclude)*/__pycache__/*",
    ]
    _, stdout, _ = await log_run_subprocess(diff_cmd)
    patch = stdout
    patch = "\n".join(
        line for line in patch.split("\n") if not line.startswith("index ")
    )
    return patch


def get_repo_diff(repo_dir: str, commit_hash: str) -> str:
    """
    Return the patch file for the diff between the current repo and the commit hash
    """
    diff_cmd = [
        "git",
        "-C",
        repo_dir,
        "diff",
        commit_hash,
        "--",
        ".",
        ":(exclude)__pycache__/*",
        ":(exclude)*/__pycache__/*",
    ]
    success, stdout, _ = log_run_subprocess_sync(diff_cmd)
    if not success:
        raise ValueError(f"Error getting diff for {repo_dir}: {stdout}")
    patch = stdout
    patch = "\n".join(
        line for line in patch.split("\n") if not line.startswith("index ")
    )
    return patch


async def aget_default_branch_name(repo_dir: str) -> Optional[str]:
    """
    Determines the default branch name (main or master) of a Git repository
    """
    fetch_cmd = ["git", "fetch"]
    await log_run_subprocess(fetch_cmd)

    show_cmd = ["git", "-C", repo_dir, "remote", "show", "origin"]

    _, stdout, _ = await log_run_subprocess(show_cmd)

    for line in stdout.split("\n"):
        if "HEAD branch" in line:
            return line.split(": ")[1].strip()
    return None


def get_default_branch_name(repo_dir: str) -> Optional[str]:
    """
    Determines the default branch name (main or master) of a Git repository
    """
    subprocess.run(
        ["git", "fetch"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    result = subprocess.run(
        ["git", "-C", repo_dir, "remote", "show", "origin"],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.split("\n"):
        if "HEAD branch" in line:
            return line.split(": ")[1].strip()
    return None


async def aget_branch_name(repo_dir: str, commit_hash: str) -> Optional[str]:
    """
    Get branch name on which the commit with the given hash was made
    """
    cmd = ["git", "-C", repo_dir, "branch", "--contains", commit_hash]
    _, stdout, _ = await log_run_subprocess(cmd)

    branches = [
        branch.replace("*", "").strip()
        for branch in stdout.split("\n")
        if branch.strip() != f"(HEAD detached at {commit_hash})"
    ]
    return next(iter(branches), None)


def get_branch_name(repo_dir: str, commit_hash: str) -> Optional[str]:
    """
    Get branch name on which the commit with the given hash was made
    """
    # Get branches containing the commit
    branches = (
        subprocess.check_output(
            ["git", "-C", repo_dir, "branch", "--contains", commit_hash],
            stderr=subprocess.STDOUT,
        )
        .decode("utf-8")
        .strip()
        .split("\n")
    )

    # Filter out any extra characters and whitespace, and handle detached HEADs
    branches = [
        branch.replace("*", "").strip()
        for branch in branches
        if branch.strip() != "(HEAD detached at {})".format(commit_hash)
    ]
    return next(iter(branches), None)


async def aget_next_commit(repo_dir: str, parent_commit_hash: str) -> Optional[str]:
    """
    Get the next commit in the repo after the commit with the given hash
    """
    branch = await aget_branch_name(repo_dir=repo_dir, commit_hash=parent_commit_hash)
    if not branch:
        raise ValueError(f"Branch for commit {parent_commit_hash} not found")

    cmd = f"git -C {repo_dir} log --reverse --ancestry-path {parent_commit_hash}^..{branch} --oneline"
    _, stdout, stderr = await log_run_subprocess(cmd.split(" "))
    if stderr:
        raise ValueError(f"Error getting next commit for {repo_dir}: {stderr}")

    log_str = stdout
    commit_hashes = [l.split(" ")[0] for l in log_str.split("\n") if l]
    for i, commit_hash in enumerate(commit_hashes):
        if parent_commit_hash in commit_hash:
            next_commit = commit_hashes[i + 1] if i + 1 < len(commit_hashes) else None
            return next_commit
    return commit_hashes[1] if len(commit_hashes) > 1 else None


def get_next_commit(repo_dir: str, parent_commit_hash: str) -> Optional[str]:
    """
    Get the next commit in the repo after the commit with the given hash
    """

    branch = get_branch_name(repo_dir=repo_dir, commit_hash=parent_commit_hash)

    command = f"git -C {repo_dir} log --reverse --ancestry-path {parent_commit_hash}^..{branch} --oneline"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    log, error = process.communicate()
    if error:
        raise ValueError(f"Error getting next commit for {repo_dir}: {error.decode()}")
    log_str = log.decode("utf-8")
    commit_hashes = [l.split(" ")[0] for l in log_str.split("\n")]
    for i, commit_hash in enumerate(commit_hashes):
        if parent_commit_hash in commit_hash:
            next_commit = commit_hashes[i + 1]
            return next_commit
    return commit_hashes[1] if len(commit_hashes) > 1 else None


def get_status(repo_dir: str) -> Union[str, Literal[False]]:
    """
    Get the status of the repo. If the process fails, return False.
    """
    status_cmd = ["git", "-C", repo_dir, "status"]
    success, stdout, stderr = log_run_subprocess_sync(command=status_cmd)
    if not success:
        return False
    return stdout
