import asyncio
import os
import uuid
from contextlib import AbstractAsyncContextManager
from typing import Optional, Tuple

import aiofiles

from ..git.repository import Repository
from ..utils import LockedKVStore, log_run_subprocess
from .utils import insert_secret


class AsyncTestBed(AbstractAsyncContextManager["AsyncTestBed"]):
    ENV_STORE = "conda_envs"

    """
    Base class for evaluating repositories in a conda environment
    """

    def __init__(
        self,
        test_id: str,
        environment: str,
        repo: Repository,
        temp_dir: str,
        persist: bool = False,
    ):
        self.repo: Repository = repo
        self.test_id: str = test_id
        self.python_version: str = environment.replace("python", "").strip()
        self.conda_env_name: Optional[str] = None
        self.temp_dir: str = temp_dir
        self.env_store: LockedKVStore = LockedKVStore(self.temp_dir, self.ENV_STORE)
        self.persist: bool = persist

    async def __aenter__(self) -> "AsyncTestBed":
        await self._setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        if not self.persist:
            await self._teardown()

    async def _setup(self) -> None:
        # Create a conda environment with the specified Python version
        existing_env = await self.env_store.get_entry(self.test_id)
        if existing_env is not None:
            self.conda_env_name = existing_env
        else:
            self.conda_env_name = await self._create_conda_env()

        if self.persist:
            await self.env_store.add_entry(self.test_id, self.conda_env_name)

    async def _create_conda_env(self) -> str:
        conda_env_name = f"test_env_{uuid.uuid4()}"
        create_env_cmd = [
            "conda",
            "create",
            "--name",
            conda_env_name,
            f"python={self.python_version}",
            "-y",
        ]
        await log_run_subprocess(create_env_cmd)
        return conda_env_name

    async def _teardown(self) -> None:
        if self.conda_env_name is not None:
            remove_conda_env_command = [
                "conda",
                "env",
                "remove",
                "--name",
                self.conda_env_name,
            ]
            await log_run_subprocess(command=remove_conda_env_command)

    async def check(
        self, test_script: str, timeout: Optional[int] = None
    ) -> Tuple[bool, str, str]:
        """
        Check the given test script against the TestBed's repo
        Returns a tuple of (success, stdout, stderr)
        """
        assert self.conda_env_name is not None, "Conda environment not initialized"
        # Write the test script into the root of the repo
        random_file = f"{str(uuid.uuid4())}.py"
        test_script_dest = os.path.join(self.repo.path, random_file)

        secret = str(uuid.uuid4())
        async with aiofiles.open(test_script_dest, "w", encoding="utf-8") as f:
            await f.write(insert_secret(test_script=test_script, secret=secret))

        try:
            test_cmd = [
                "conda",
                "run",
                "-n",
                self.conda_env_name,
                "python",
                random_file,
            ]
            success, stdout, stderr = await log_run_subprocess(
                test_cmd, timeout=timeout, cwd=self.repo.path
            )
            success &= secret in stdout  # Prevent early exit exploit

        except asyncio.TimeoutError:
            success = False
            stdout = "TIMED OUT"
            stderr = ""
        finally:
            os.remove(test_script_dest)

        return success, stdout, stderr
