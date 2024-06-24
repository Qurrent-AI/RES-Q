from typing import List
from pydantic import BaseModel


class Submission(BaseModel):
    """
    Model for a submission to the environment
    """

    id: str
    patch: str


class SubmissionResult(BaseModel):
    """
    Model for the result of a submission to the environment
    """

    id: str
    success: bool
    message: str
    test_suite_feedback: str



class RESQDataPoint(BaseModel):
    """
    Model for one entry in the RESQDataset
    """

    class ModifiedFile(BaseModel):
        path: str
        content: str

    id: str
    repo_url: str
    instruction: str
    base_commit: str
    test_script: str
    testbed_environment: str
    requirements_txt: str
    solution_commit: str
    solution_patch: str
    modified_files: List[ModifiedFile]
    language: str
