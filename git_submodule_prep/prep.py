#!/usr/bin/env python3

import argparse
from contextlib import contextmanager

import path


class Path(path.Path):
    @contextmanager
    def chdir_ctx(self):
        orig_dir = Path().absolute()
        try:
            self.chdir()
            yield
        finally:
            orig_dir.chdir()


def real_main(args):
    return


def main():
    parser = argparse.ArgumentParser(description="git-submodule-prep")
    parser.add_argument(
        "-m", "--merge-upstream", action="store_true", help="Merge upstream changes with your own"
    )
    parser.add_argument("-l", "--list-preps", action="store_true", help="List submodule preps")
    parser.add_argument("path", default=None, nargs="*", help="Repo path(s) (default: CWD)")
    args = parser.parse_args()
    real_main(args)


if __name__ == "__main__":
    main()
