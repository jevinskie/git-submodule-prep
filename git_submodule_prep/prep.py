#!/usr/bin/env python3

import argparse
import configparser
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from typing import Callable, Iterator

import git
from path import Path as BasePath
from typing_extensions import Self


class Path(BasePath):
    def __new__(cls: type[Self], other: str = ".") -> Self:
        return BasePath.__new__(cls, other)

    def __init__(self, other: str = ".") -> None:
        super().__init__(other)

    @contextmanager
    def chdir_ctx(self) -> Iterator[None]:
        orig_dir = Path().abspath()
        try:
            self.chdir()
            yield
        finally:
            orig_dir.chdir()

    @property
    def parent(self) -> Self:
        return (self / "..").normpath()


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


def parse_prep(gitmodules_prep_path: Path) -> dict[Path, dict[str, str]]:
    config = configparser.ConfigParser()
    config.read(gitmodules_prep_path)
    return {Path(submod): dict(config[submod]) for submod in config.sections()}


def find_dir_containing(dir_path: Path, filename: Path) -> Path:
    assert dir_path.isdir()
    orig_path = dir_path
    cur_dir = dir_path
    while True:
        if (cur_dir / filename).exists():
            return cur_dir
        if cur_dir.abspath() == Path("/"):
            break
        cur_dir = cur_dir.parent
    raise ValueError(f'Couldn\'t find "{filename}" under "{orig_path}"')


def find_git_root(dir_path: Path) -> Path:
    return find_dir_containing(dir_path, Path(".git"))


def find_prep_root(dir_path: Path) -> Path:
    prep_root = find_dir_containing(dir_path, Path(".gitmodules-prep"))
    if not (prep_root / ".git").exists():
        raise ValueError(f'Found .gitmodules-prep but not in a repo root at "{prep_root}"')
    return prep_root


def get_submodule_dirs(repo_path: Path, recurse: bool = False) -> list[Path]:
    with repo_path.chdir_ctx():
        repo = git.Repo()
        submod_dirs = []
        for submod in repo.submodules:
            submod_dir = Path(submod.path)
            submod_dirs.append((repo_path / submod_dir).normpath())
            if recurse:
                submod_dirs += get_submodule_dirs(submod_dir, recurse=True)
    return submod_dirs


def get_subprep_dirs(repo_path: Path, recurse: bool = False) -> list[Path]:
    submod_dirs = get_submodule_dirs(repo_path, recurse=True) if recurse else []
    subprep_dirs = []
    for submod_dir in (repo_path, *submod_dirs):
        if (submod_dir / ".gitmodules-prep").exists():
            subprep_dirs.append(submod_dir.normpath())
    return subprep_dirs


def get_unique_subprep_dirs(child_paths: list[Path], recurse: bool = False) -> list[Path]:
    subprep_dirs = set()
    for child in child_paths:
        subprep_dirs |= set(get_subprep_dirs(find_git_root(child), recurse=recurse))
    return list(subprep_dirs)


def config_module(mod_path, upstream_url, upstream_branch):
    with mod_path.chdir_ctx():
        # if any([l.startswith("upstream\t") for l in GIT("remote", "-v").out.splitlines()]):
        #     return
        # GIT("remote", "add", "upstream", upstream_url)
        # GIT("fetch", "--all")
        pass


def fetch_module(mod_path):
    with mod_path.chdir_ctx():
        # GIT("fetch", "--all")
        pass


def real_main(args):
    if not len(args.path):
        args.path = [Path()]

    if args.list_preps:
        print("Git repos with submodule preps:")
        for prep_root in get_unique_subprep_dirs(args.path, recurse=args.recursive):
            print(f"\t{prep_root}")
            prep_cfg = parse_prep(prep_root / ".gitmodules-prep")
            for submod_path, submod in prep_cfg.items():
                url, branch = submod["upstream_url"], submod["upstream_branch"]
                print(f"\t\t{submod_path.normpath()}")
                print(f"\t\t\tupstream_url:    {url}")
                print(f"\t\t\tupstream_branch: {branch}")
    # for path in args.path:
    #     if args.list_preps:
    #         print("Git repos with submodule preps:")
    #         for prep_root in get_prep_roots(path)
    #     elif args.unchanged:
    #         print("unchanged")
    #     elif args.merge:
    #         print("merge")
    return


def main():
    parser = argparse.ArgumentParser(description="git-submodule-prep")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "-m", "--merge-upstream", action="store_true", help="merge upstream changes with your own"
    )
    actions.add_argument(
        "-u", "--unchanged", action="store_true", help="check if repos are unchanged"
    )
    actions.add_argument("-l", "--list-preps", action="store_true", help="list submodule preps")
    parser.add_argument("-r", "--recursive", action="store_true", help="recurse into sub-preps")
    parser.add_argument("path", type=Path, nargs="*", help="repo path(s) (default: CWD)")
    args = parser.parse_args()
    real_main(args)


if __name__ == "__main__":
    main()
