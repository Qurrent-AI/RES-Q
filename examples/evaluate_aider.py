import json
import traceback
import os

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model

from datasets import load_dataset
from resq.dataset import RESQDataset, RESQDataPoint
from resq.models import Submission
from resq.submission import SubmissionEnv
from resq.git.repository import Repository


# Adapted from https://github.com/paul-gauthier/aider-swe-bench/blob/main/harness.py
def get_coder(model: str, git_dname: str, chat_history_file: str, temperature: float) -> Coder:
    """
    Get an instance of aider to work with the given LLM `model` at `temperature`
    on the code in `git_dname`. Will store the markdown chat logs in
    the `chat_history_file`. Tells aider it can use the `test_cmd` to
    run tests after the LLM edits files.
    """
    model = Model(model)
    io = InputOutput(
        yes=True,  
        chat_history_file=chat_history_file,  
        input_history_file="/dev/null",  
    )

    coder = Coder.create(
        main_model=model,
        io=io,
        git_dname=git_dname,
        map_tokens=2048,  
        stream=False,
        auto_commits=False,  
    )
    print(coder.repo)
    coder.temperature = temperature

    coder.max_reflections = 4

    coder.show_announcements()
    return coder

def process_entry(entry: RESQDataPoint, model: str, temp_dir: str) -> str:
    entry_temp_dir = os.path.join(temp_dir, entry.id)
    chat_history_file = os.path.join(entry_temp_dir, "chat.md")

    with Repository(repo_url=entry.repo_url, temp_dir=entry_temp_dir, persist=True) as repo:
        repo.reset(entry.base_commit)
        coder = get_coder(model=model, git_dname=repo.path, chat_history_file=chat_history_file, temperature=0.0)
        try:
            coder.run(with_message=entry.instruction)
        except Exception as e:
            traceback.print_exc()
        
        repo.run(["add", "."])
        patch = repo.get_repo_diff(commit=entry.base_commit)
    return patch

if __name__ == "__main__":
    repo_temp_dir = "temp"
    env_temp_dir = "env_temp"
    model = "gpt-4o"
    submissions_dir = "submissions.json"
    results_dir = "results.json"

    hf_dataset = load_dataset("Qurrent/RES-Q", split="test")
    dataset = RESQDataset(hf_dataset)

    env = SubmissionEnv(dataset=dataset, temp_dir=env_temp_dir, persist=True)

    submissions = []
    for entry in dataset:  
        patch = process_entry(entry=entry, model=model, temp_dir=repo_temp_dir)
        sub = Submission(id=entry.id, patch=patch)
        submissions.append(sub)

    results = env.step_batch(submissions, n_workers=4, pbar=True)

    with open(results_dir, "w") as f:
        json.dump([o.model_dump() for o in results], f)