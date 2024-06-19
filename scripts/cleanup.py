import os
import json
import argparse
import asyncio
import re
import shutil
from tqdm.asyncio import tqdm # type: ignore
from asyncio import Queue
from typing import Optional, List

def validate_env_temp_dir(env_temp_dir: str) -> None:
    valid = True
    message = ""

    # Check that the directory exists
    if not os.path.exists(env_temp_dir):
        valid = False
        message = "The environment temp directory does not exist."

    # Check that the directory has a conda_envs.json file
    env_store = os.path.join(env_temp_dir, "workspace", "conda_envs.json")
    if not os.path.exists(env_store):
        valid = False
        message = "The environment temp directory does not contain a conda_envs.json file."

    # Check that the rest of the files in the directory are folders
    for file in os.listdir(os.path.join(env_temp_dir, "workspace")):
        if file != "conda_envs.json" and not os.path.isdir(os.path.join(env_temp_dir, "workspace", file)):
            print(f"Found file: {file}")
            valid = False
            message = "The environment temp directory contains files that are not folders."
    if not valid:
        raise ValueError(f"The environment temp directory is not valid.: {message}")

async def list_conda_envs(env_temp_dir: Optional[str] = None) -> List[str]:
    if env_temp_dir:
        env_store = os.path.join(env_temp_dir, "workspace", "conda_envs.json")
        with open(env_store, "r") as f:
            env_store_json = json.load(f)
        envs = list(env_store_json.values())
    else:
        process = await asyncio.create_subprocess_shell(
            'conda env list',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if stderr:
            print(f"Error listing environments: {stderr.decode().strip()}")
            return []

        envs_output = stdout.decode().strip()
        pattern = re.compile(r"^test_env_[0-9a-fA-F-]{36}$")
        envs = [line.split()[0] for line in envs_output.splitlines() if pattern.match(line.split()[0])]
    return envs

async def remove_conda_env(env_name: str, pbar: tqdm) -> None:
    process = await asyncio.create_subprocess_shell(
        f'conda env remove -n {env_name}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    pbar.update(1)

async def worker(queue: Queue, pbar: tqdm) -> None:
    while True:
        env_name = await queue.get()
        if env_name is None:  
            break
        await remove_conda_env(env_name, pbar)
        queue.task_done()

async def main(env_temp_dir: Optional[str]) -> None:
    envs_to_remove = await list_conda_envs(env_temp_dir = env_temp_dir)
    queue: Queue[Optional[str]] = Queue()
    num_workers = 5  

    with tqdm(total=len(envs_to_remove), desc="Removing Conda Environments") as pbar:
        workers = [asyncio.create_task(worker(queue, pbar)) for _ in range(num_workers)]
        
        for env in envs_to_remove:
            await queue.put(env)
        
        await queue.join()
        
        for _ in range(num_workers):
            await queue.put(None)  
        await asyncio.gather(*workers)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make submissions to the RES-Q Submission Environment")
    parser.add_argument("--env-temp-dir", type=str, default=None, help="Path of the environment temp directory to clean, if it exists.")
    args = parser.parse_args()
    if args.env_temp_dir:
        validate_env_temp_dir(args.env_temp_dir)
        abs_path = os.path.abspath(args.env_temp_dir)
        confirmation = input(f"Are you sure you want to delete the files in {abs_path} (yes/no): ")
        if confirmation.lower() != "yes":
            print("Operation cancelled by user.")
            exit()
    asyncio.run(main(args.env_temp_dir))
    if args.env_temp_dir:
        shutil.rmtree(args.env_temp_dir)