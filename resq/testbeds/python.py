import os

import aiofiles

from ..git.repository import Repository
from ..utils import log_run_subprocess
from .base import AsyncTestBed


class PythonTestBed(AsyncTestBed):
    """
    Testbed for Python Repositories
    """

    def __init__(
        self,
        test_id: str,
        environment: str,
        requirements_script: str,
        repo: Repository,
        temp_dir: str,
        persist: bool = False,
    ):
        super().__init__(
            test_id=test_id,
            environment=environment,
            repo=repo,
            temp_dir=temp_dir,
            persist=persist,
        )
        self.requirements_script = requirements_script

    async def _setup(self) -> None:
        existing_env = await self.env_store.get_entry(self.test_id)
        if existing_env is not None:
            self.conda_env_name = existing_env
        else:
            self.conda_env_name = await self._create_conda_env()

            if self.requirements_script.strip():
                async with aiofiles.tempfile.NamedTemporaryFile(
                    mode="w+", delete=False
                ) as temp_file:
                    await temp_file.write(self.requirements_script)
                    await temp_file.flush()
                    temp_file_path = str(temp_file.name)

                install_cmd = [
                    "conda",
                    "run",
                    "--name",
                    self.conda_env_name,
                    "pip",
                    "install",
                    "-r",
                    temp_file_path,
                ]
                await log_run_subprocess(install_cmd, cwd=self.repo.path)

                # Cleanup temporary file after installation
                os.remove(temp_file_path)

        if self.persist:
            await self.env_store.add_entry(self.test_id, self.conda_env_name)
