import os
import json
import time
import argparse

from typing import Any
from pydantic import ValidationError
from resq.dataset import RESQDataset
from resq.submission import SubmissionEnv, Submission


def main(args: Any) -> None:
    # Load the submissions
    with open(args.submissions_file, "r", encoding="utf-8") as f:
        submissions = json.load(f)

    # Parse the submissions
    try:
        submissions = [
            Submission(
                **{"id": entry.get("id", None), "patch": entry.get("patch", None)}
            )
            for entry in submissions
        ]
    except ValidationError as e:
        print(f"Error validating submissions: {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return

    # Load the dataset and create the SubmissionEnv instance
    if args.dataset_file is None:
        dataset = RESQDataset.from_huggingface()
    else:
        dataset = RESQDataset.from_json(dataset_dir=args.dataset_file)

    SUB_TIMEOUT = 60
    if not os.path.exists(args.env_temp_dir):
        print(f"Creating temporary environment directory: {args.env_temp_dir}")
        os.makedirs(args.env_temp_dir)
    else:
        print(f"Reusing existing temporary environment directory: {args.env_temp_dir}")
    submission_env = SubmissionEnv(
        dataset=dataset,
        temp_dir=args.env_temp_dir,
        timeout=SUB_TIMEOUT,
        persist=args.persist_env,
    )

    now = time.time()

    results = submission_env.step_batch(
        submissions=submissions, n_workers=args.n_workers, pbar=args.enable_pbar
    )

    with open(args.results_file, "w", encoding="utf-8") as f:
        json.dump([o.model_dump() for o in results], f, indent=4)

    elapsed_time = time.time() - now
    print(f"Processed {len(submissions)} submissions in {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Make submissions to the RES-Q Submission Environment"
    )
    parser.add_argument(
        "--submissions_file",
        type=str,
        required=True,
        help="Path to JSON file containing submissions.",
    )
    parser.add_argument(
        "--env_temp_dir",
        type=str,
        required=True,
        help="Where to build the submission environment's temporary files.",
    )
    parser.add_argument(
        "--dataset_file",
        type=str,
        default=None,
        help="Path to RES-Q dataset JSON file.",
    )
    parser.add_argument(
        "--results_file",
        type=str,
        default="results.json",
        help="JSON file to write the results to.",
    )
    parser.add_argument(
        "--persist_env",
        type=bool,
        default=True,
        help="Persist generated environment files for future use.",
    )
    parser.add_argument(
        "--enable_pbar", type=bool, default=True, help="Enable progress bar."
    )
    parser.add_argument("--n_workers", type=int, default=1, help="Number of workers.")

    args = parser.parse_args()
    main(args)
