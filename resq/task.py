import os
from typing import Optional

from .git.repository import Repository
from .git.utils import format_patch
from .models import RESQDataPoint, Submission
from .testbeds.python import PythonTestBed
from .utils import locked_temp_dir
from .models import SubmissionResult


class TaskInstance:
    """
    Represents a task instance of RES-Q to be executed
    """

    def __init__(
        self,
        submission: Submission,
        task: RESQDataPoint,
        parent_temp_dir: str,
        persist: bool = False,
    ):
        self.submission = submission
        self.task = task
        self.parent_temp_dir = parent_temp_dir
        self.task_temp_dir = os.path.join(self.parent_temp_dir, self.task.id)
        self.persist = persist

    async def execute(self, timeout: Optional[int] = None) -> SubmissionResult:
        """
        Asynchronously execute the task instance and return the result
        """
        async with locked_temp_dir(
            directory=self.task_temp_dir, persist=self.persist
        ) as task_temp_dir:

            repo_url = self.task.repo_url

            async with Repository(
                repo_url=repo_url, temp_dir=task_temp_dir, persist=self.persist
            ) as repo:

                await repo.areset(commit_hash=self.task.base_commit)

                if self.submission.patch:
                    applied_patch, patch_stderr = await repo.aapply_patch(
                        patch=format_patch(self.submission.patch)
                    )
                else:
                    applied_patch = False
                    patch_stderr = "Empty patch"

                if not applied_patch:
                    return SubmissionResult(
                        id=self.submission.id,
                        success=False,
                        message="PATCH FAILED",
                        test_suite_feedback=patch_stderr,
                    )

                async with PythonTestBed(
                    test_id=self.task.id,
                    environment=self.task.testbed_environment,
                    requirements_script=self.task.requirements_txt,
                    repo=repo,
                    temp_dir=self.parent_temp_dir,
                    persist=self.persist,
                ) as tb:
                    success, stdout, stderr = await tb.check(
                        self.task.test_script, timeout=timeout
                    )

                if success:
                    message = "PASS"
                    test_output = ""
                elif stdout == "TIMED OUT":
                    message = stdout
                    test_output = ""
                else:
                    message = "FAIL"
                    test_output = stdout + stderr

                return SubmissionResult(
                    id=self.submission.id,
                    success=success,
                    message=message,
                    test_suite_feedback=test_output,
                )
