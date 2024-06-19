from ..git.repository import Repository
from .base import AsyncTestBed


class JavascriptTestBed(AsyncTestBed):
    """
    Testbed for JavaScript repositories
    """

    def __init__(
        self,
        test_id: str,
        environment: str,
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
