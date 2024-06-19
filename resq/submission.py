import asyncio
import os
from typing import List, Optional, Union

from tqdm.asyncio import tqdm

from .dataset import RESQDataset
from .models import Submission, SubmissionResult
from .task import TaskInstance


class SubmissionEnv:
    """
    Environment for evaluating RES-Q submissions
    """

    def __init__(
        self,
        dataset: RESQDataset,
        temp_dir: str,
        timeout: Optional[int] = None,
        persist: bool = False,
    ):
        self.dataset = dataset
        temp_dir = os.path.join(temp_dir, "workspace")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        self.temp_dir = temp_dir
        self.timeout = timeout
        self.persist = persist

    def step(self, submission: Submission) -> SubmissionResult:
        """
        Checks that the diff correctly edits the repository
        """
        return asyncio.run(self.astep(submission))

    async def astep(self, submission: Submission) -> SubmissionResult:
        """
        Checks that the diff correctly edits the repository
        """
        task_entry = self.dataset[submission.id]
        task = TaskInstance(
            task=task_entry,
            submission=submission,
            parent_temp_dir=self.temp_dir,
            persist=self.persist,
        )
        result = await task.execute(timeout=self.timeout)
        return result

    def step_batch(
        self, submissions: List[Submission], n_workers: int = 1, pbar: bool = False
    ) -> List[SubmissionResult]:
        """
        Processes a batch of submissions asynchronously
        """
        return asyncio.run(
            self.astep_batch(submissions=submissions, n_workers=n_workers, pbar=pbar)
        )

    async def astep_batch(
        self,
        submissions: List[Submission],
        n_workers: int = 1,
        pbar: Union[tqdm, bool] = False,
    ) -> List[SubmissionResult]:
        """
        Processes a batch of submissions asynchronously
        """

        results: List[SubmissionResult] = []
        queue: asyncio.Queue[Optional[Submission]] = asyncio.Queue()
        pbar = (
            tqdm(total=len(submissions), desc="Processing Submissions")
            if pbar
            else None
        )

        workers = [
            asyncio.create_task(self.worker(queue, results, pbar))
            for _ in range(n_workers)
        ]

        for submission in submissions:
            await queue.put(submission)

        await queue.join()

        for _ in range(n_workers):
            await queue.put(None)

        await asyncio.gather(*workers)
        if pbar:
            pbar.close()

        return results

    async def worker(
        self,
        queue: asyncio.Queue[Optional[Submission]],
        results: List[SubmissionResult],
        pbar: tqdm,
    ) -> None:
        """
        Worker that gets submissions from the queue, submits them, and records the result
        """
        while True:
            submission = await queue.get()
            if submission is None:
                queue.task_done()
                break
            result = await self.astep(submission)
            results.append(result)
            queue.task_done()
            if pbar:
                pbar.update(1)
