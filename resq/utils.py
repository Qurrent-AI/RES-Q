import asyncio
import json
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple, Union, AsyncGenerator, Any

import aiofiles
import aiofiles.os


class LockRegistry:
    """
    Class to manage a registry of asyncio locks
    """

    _locks: Dict[int, Dict[str, asyncio.Lock]] = {}

    @classmethod
    def get_lock(cls, filepath: str) -> asyncio.Lock:
        loop = asyncio.get_event_loop()
        loop_id = id(loop)

        if loop_id not in cls._locks:
            cls._locks[loop_id] = {}

        if filepath not in cls._locks[loop_id]:
            cls._locks[loop_id][filepath] = asyncio.Lock()

        return cls._locks[loop_id][filepath]


class LockedKVStore:
    """
    Async key-value store that locks access to its data file
    """

    def __init__(self, directory: str, name: str):
        self.filepath = os.path.join(directory, f"{name}.json")
        self.lock = LockRegistry.get_lock(self.filepath)

    async def _load_data(self) -> Dict[str, str]:
        try:
            async with aiofiles.open(self.filepath, "r") as f:
                content = await f.read()
                if content:
                    return dict(json.loads(content))
                return {}
        except FileNotFoundError:
            return {}

    async def _save_data(self, data: Dict[str, str]) -> None:
        async with aiofiles.open(self.filepath, "w") as f:
            await f.write(json.dumps(data, indent=4))

    async def add_entry(self, key: str, env_name: str) -> None:
        """
        Add a new key-value entry to the store, or update an existing key with a new value
        """
        async with self.lock:
            data = await self._load_data()
            data[key] = env_name
            await self._save_data(data)

    async def get_entry(self, key: str) -> Union[str, None]:
        """
        Retrieve the value associated with the given key from the store
        """
        async with self.lock:
            data = await self._load_data()
            return data.get(key, None)

    async def remove_entry(self, key: str) -> bool:
        """
        Remove the entry associated with the given key from the store
        Returns False is the key was not found
        """
        async with self.lock:
            data = await self._load_data()
            if key in data:
                del data[key]
                await self._save_data(data)
                return True
            return False


@asynccontextmanager
async def locked_temp_dir(
    directory: str, persist: bool = False
) -> AsyncGenerator[str, None]:
    """
    Context manager for creating a locked temporary directory
    """
    lock = LockRegistry.get_lock(directory)
    await lock.acquire()
    await aiofiles.os.makedirs(directory, exist_ok=True)
    try:
        yield directory
    finally:
        if not persist:
            await aiofiles.os.rmdir(directory)
        lock.release()


async def log_run_subprocess(
    command: List[str], timeout: Optional[int] = None, **run_kwargs: Any
) -> Tuple[bool, str, str]:
    """
    Run a subprocess command asynchronously, capturing its output and logging the results
    """
    logging.debug(
        "====== Running command: %s, Timeout: %s, Run kwargs: %s ======",
        " ".join(command),
        timeout,
        run_kwargs,
    )

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **run_kwargs,
    )

    start_time = time.time()
    stdout = b""
    stderr = b""
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError as e:
        process.kill()
        stdout, stderr = await process.communicate()
        raise e
    finally:
        end_time = time.time()
        duration = end_time - start_time
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()
        logging.debug("====== Command stdout: ======\n%s", stdout_str)
        logging.debug("====== Command stderr: ======\n%s", stderr_str)
        logging.debug("====== Command duration: %.2f seconds ======", duration)

    success = process.returncode == 0

    return success, stdout_str, stderr_str


def log_run_subprocess_sync(
    command: List[str], timeout: Optional[int] = None, **run_kwargs: Any
) -> Tuple[bool, str, str]:
    """
    Run a subprocess command synchronously, capturing its output and logging the results.
    """
    logging.debug(
        "====== Running command: %s, Timeout: %s, Run kwargs: %s ======",
        " ".join(command),
        timeout,
        run_kwargs,
    )

    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
            **run_kwargs,
        )
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if e.stdout else ""
        stderr = e.stderr.decode() if e.stderr else ""
        logging.error("====== Command timed out ======")
        logging.debug("====== Command stdout: ======\n%s", stdout)
        logging.debug("====== Command stderr: ======\n%s", stderr)
        raise e
    finally:
        end_time = time.time()
        duration = end_time - start_time
        logging.debug("====== Command duration: %.2f seconds ======", duration)

    success = result.returncode == 0
    logging.debug("====== Command stdout: ======\n%s", stdout)
    logging.debug("====== Command stderr: ======\n%s", stderr)

    return success, stdout, stderr
