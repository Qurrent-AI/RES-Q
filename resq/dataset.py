import json
import tempfile
from typing import Dict, List, Optional, Any

from datasets import load_dataset

from .git.repository import Repository
from .models import RESQDataPoint


class RESQDataset:
    HF_NAME = "RES-Q"
    HF_SPLIT = "test"
    """
    Represents the RES-Q dataset
    """

    def __init__(self, dataset_obj: str, temp_dir: Optional[str] = None):
        self.dataset: List[RESQDataPoint] = [
            RESQDataPoint.model_validate(o) for o in dataset_obj
        ]
        if temp_dir is None:
            self.temp_dir = tempfile.mkdtemp()
        else:
            self.temp_dir = temp_dir
        self._index = 0

    @classmethod
    def from_json(
        cls, dataset_dir: str, temp_dir: Optional[str] = None
    ) -> "RESQDataset":
        """
        Load a RES-Q dataset from a JSON file
        """
        with open(dataset_dir, "r", encoding="utf-8") as f:
            raw_dataset = json.load(f)
        return cls(dataset_obj=raw_dataset, temp_dir=temp_dir)

    @classmethod
    def from_huggingface(
        cls, temp_dir: Optional[str] = None, **kwargs: Any
    ) -> "RESQDataset":
        """
        Load a RES-Q dataset from a Hugging Face dataset
        """
        dataset = load_dataset(name=cls.HF_NAME, split=cls.HF_SPLIT, **kwargs)
        return cls(dataset_obj=dataset, temp_dir=temp_dir)

    def get_context(self, eval_id: str) -> List[Dict[str, str]]:
        """
        Return a list of all the files in the Repository for the given eval_id
        """
        entry = self[eval_id]
        with Repository(entry.repo_url, temp_dir=self.temp_dir) as repo:
            repo.reset(commit_hash=entry.base_commit)
            return [file for file in repo.files]

    def get_oracle_context(self, eval_id: str) -> Dict[str, str]:
        """
        Return a dict of {filepath: content} representing all files that were edited by the ground truth solution patch
        """
        entry = self[eval_id]
        return entry.modified_files

    def __getitem__(self, param: str) -> RESQDataPoint:
        eval_entry = next(filter(lambda e: e.id == param, self.dataset), None)
        if eval_entry is None:
            raise ValueError(f"Eval with id={param} does not exist")
        return eval_entry

    def __iter__(self) -> "RESQDataset":
        self._index = 0
        return self

    def __next__(self) -> RESQDataPoint:
        if self._index < len(self.dataset):
            result = self.dataset[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration
