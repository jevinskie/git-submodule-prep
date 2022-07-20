#!/usr/bin/env python3

import argparse
import configparser
import sys
from contextlib import contextmanager
from typing import Iterator

import git
from path import Path as BasePath
from typing_extensions import Self


class Path(BasePath):
    def __new__(cls: type[Self], other: str = ".") -> Self:
        return BasePath.__new__(cls, other)

    def __init__(self, other: str = "."):
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

    def removesuffix(self, suffix: Self) -> Self:
        return Path(super().removesuffix(suffix)).normpath()

    def removeprefix(self, prefix: Self) -> Self:
        return Path(super().removeprefix(prefix)).normpath()


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
    subprep_dirs_dfs = sorted(subprep_dirs, key=lambda d: len(d.parts()), reverse=True)
    return subprep_dirs_dfs


def is_dirty(repo_path: Path) -> bool:
    with repo_path.chdir_ctx():
        repo = git.Repo()
        untracked = bool(len(repo.untracked_files))
        unstaged = bool(len(repo.index.diff(None, ignore_submodules="all")))
        staged = bool(len(repo.index.diff(repo.head.commit, ignore_submodules="all")))
        return untracked or unstaged or staged


def get_dirty_repos(repo_dirs: list[Path]) -> list[Path]:
    dirty = []
    for repo_dir in repo_dirs:
        if is_dirty(repo_dir):
            dirty.append(repo_dir)
    return dirty


def get_prep_configs(prep_dirs: list[Path]) -> dict[Path, dict[str, str]]:
    cfgs = {}
    for prep_dir in prep_dirs:
        prep_cfg = parse_prep(prep_dir / ".gitmodules-prep")
        for path, cfg in prep_cfg.items():
            cfg["path"] = path
            cfgs[(prep_dir / path).normpath()] = cfg
    return cfgs


def config_module(mod_path: Path, upstream_url: str, upstream_branch: str):
    with mod_path.chdir_ctx():
        repo = git.Repo()
        if "upstream" not in repo.remotes:
            repo.create_remote("upstream", url=upstream_url, t=upstream_branch)
            upstream = repo.remotes["upstream"]
            upstream.fetch()


def fetch_module(mod_path: Path):
    with mod_path.chdir_ctx():
        repo = git.Repo()
        for remote in repo.remotes:
            remote.fetch()


def real_main(args):
    if not len(args.path):
        args.path = [Path()]

    prep_dirs = get_unique_subprep_dirs(args.path, recurse=args.recursive)
    prep_cfgs = get_prep_configs(prep_dirs)

    if args.list_preps:
        print("Git repos with submodule preps:")
        for prep_dir, prep_cfg in prep_cfgs.items():
            prep_git_dir = prep_dir.removesuffix(prep_cfg["path"])
            print(f"\t{prep_git_dir}")
            print(f"\t\t{prep_cfg['path'].normpath()}")
            print(f"\t\t\tupstream_url:    {prep_cfg['upstream_url']}")
            print(f"\t\t\tupstream_branch: {prep_cfg['upstream_branch']}")
    elif args.dirty:
        print("Dirty repos:")
        for dirty_dir in get_dirty_repos(prep_cfgs.keys()):
            print(f"\t{dirty_dir}")

    return


def main():
    parser = argparse.ArgumentParser(description="git-submodule-prep")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "-m", "--merge-upstream", action="store_true", help="merge upstream changes with your own"
    )
    actions.add_argument("-d", "--dirty", action="store_true", help="check if repos are dirty")
    actions.add_argument("-l", "--list-preps", action="store_true", help="list submodule preps")
    parser.add_argument("-r", "--recursive", action="store_true", help="recurse into sub-preps")
    parser.add_argument("path", type=Path, nargs="*", help="repo path(s) (default: CWD)")
    args = parser.parse_args()
    real_main(args)


if __name__ == "__main__":
    main()
