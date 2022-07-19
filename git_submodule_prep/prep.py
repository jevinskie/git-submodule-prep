#!/usr/bin/env python3

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from typing import Callable

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


def run_cmd(*args, log: bool = True):
    args = (*args,)
    if log:
        print(f"+ {' '.join(map(str, args))}", file=sys.stderr)
    r = subprocess.run(list(map(str, args)), capture_output=True)
    if r.returncode != 0:
        sys.stderr.buffer.write(r.stdout)
        sys.stderr.buffer.write(r.stderr)
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    try:
        r.out = r.stdout.decode()
    except UnicodeDecodeError:
        pass
    return r


def gen_cmd(bin_name: str) -> Callable[[str], subprocess.CompletedProcess]:
    bin_path = shutil.which(bin_name)
    assert bin_path is not None
    return lambda *args, **kwargs: run_cmd(bin_path, *args, **kwargs)


GIT = gen_cmd("git")

SUBMOD_CONFIG_PAT = re.compile('\[submodule\s+"(.*?)"\]')
SUBMOD_PATH_PAT = re.compile("\s+path\s+=\s(.*)")
SUBMOD_URL_PAT = re.compile("\s+url\s+=\s(.*)")
SUBMOD_BRANCH_PAT = re.compile("\s+branch\s+=\s(.*)")


def parse_submodules():
    with open(".gitmodules") as f:
        submods = {}
        current_mod = None
        for line in f:
            line = line.rstrip("\n")
            cfg_match = SUBMOD_CONFIG_PAT.match(line)
            if cfg_match:
                current_mod = cfg_match.group(1)
                submods[current_mod] = {}
            path_match = SUBMOD_PATH_PAT.match(line)
            if path_match:
                submods[current_mod]["path"] = Path(path_match.group(1))
            url_match = SUBMOD_URL_PAT.match(line)
            if url_match:
                submods[current_mod]["url"] = url_match.group(1)
            branch_match = SUBMOD_BRANCH_PAT.match(line)
            if branch_match:
                submods[current_mod]["branch"] = branch_match.group(1)
        return submods


def config_module(mod_path, upstream_url, upstream_branch):
    with mod_path.chdir():
        if any([l.startswith("upstream\t") for l in GIT("remote", "-v").out.splitlines()]):
            return
        GIT("remote", "add", "upstream", upstream_url)
        GIT("fetch", "--all")


def fetch_module(mod_path):
    with mod_path.chdir():
        GIT("fetch", "--all")


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
