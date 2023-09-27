#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL

from argparse import ArgumentParser
import sqlite3
import stat
import os
from pathlib import Path
import sys
import time


try:
    from termcolor import colored as _colored

    def colored(s, *args, **kwargs):
        if os.environ.get("NO_COLOR"):
            return s
        return _colored(s, *args, **kwargs)

except ImportError:
    def colored(s, *args, **kwargs):
        return s


def to_bytes_if_broken(s):
    try:
        s.encode("utf8")
    except UnicodeError:
        return s.encode("utf8", "surrogateescape")
    else:
        return s


def getrow(path, stat):
    relpath = path.relative_to(options.root)
    parent = str(relpath.parent)
    if parent == ".":
        parent = ""

    tup = (
        to_bytes_if_broken(parent),
        to_bytes_if_broken(relpath.name),
        stat.st_mode,
        stat.st_ino,
        stat.st_nlink,
        stat.st_uid,
        stat.st_gid,
        stat.st_size,
        stat.st_mtime,
        stat.st_atime,
        stat.st_ctime,
    )

    return tup


def insert(path, stat):
    row = getrow(path, stat)
    if not row:
        return None

    db.execute(
        """
        insert into files(
            dirname,
            basename,
            mode,
            ino,
            nlink,
            uid,
            gid,
            size,
            mtime,
            atime,
            ctime
        ) values (?,?,?,?,?,?,?,?,?,?,?)
        """,
        row,
    )

    progress.files += 1

    return True


class Progress:
    def __init__(self):
        self.files = 0
        self.dirs = 0
        self.full_start = self.cycle_start = time.time()

    def duration(self):
        return int(time.time() - progress.full_start)

    def try_print(self):
        now = time.time()
        if now - self.cycle_start > 2:
            self.cycle_start = now
            print(
                f"Processed {self.dirs} dirs and {self.files} files in {self.duration()}s...",
                file=sys.stderr, end="\r",
            )
            return True

        return False

    def print_end(self):
        print(
            colored(f"Finished in {self.duration()}s. Processed {self.dirs} dirs and {self.files} files.", "green"),
            file=sys.stderr,
        )


progress = Progress()


def recurse(path):
    def sortkey(p):
        # not the best sort key but we don't need the perfect one
        return str(p.name).lower()

    try:
        listed = list(path.iterdir())
    except OSError as exc:
        # there are many reasons: permissions could be strict, item could
        # have vanished, etc.
        # those will always happen, we shouldn't exit for that
        print(colored(f"error listdir({path}): {exc}", "red"), file=sys.stderr)
        return

    for sub in sorted(listed, key=sortkey):
        try:
            statobj = sub.lstat()
        except OSError as exc:
            print(f"error lstat({sub}): {exc}", file=sys.stderr)
            continue

        insert(sub, statobj)
        progress.try_print()

        if stat.S_ISDIR(statobj.st_mode):
            if not options.xdev or options.dev == statobj.st_dev:
                recurse(sub)

    progress.dirs += 1
    progress.try_print()


def main():
    global db, options, progress

    parser = ArgumentParser(
        description="Scan a directory and snapshot its tree into a decoyfs database",
    )
    parser.add_argument("dbpath", help="output database file")
    parser.add_argument("root", nargs="?", help="directory to scan recursively")

    parser.add_argument(
        "-x", "--xdev", action="store_true",
        help="if set, don't scan subdirectories if they are not on the same filesystem."
        + " Similar to `find -xdev` or `du -x`.",
    )

    options = parser.parse_args()

    if options.root:
        options.root = Path(options.root)
    else:
        options.root = Path.cwd()

    options.root = options.root.resolve(strict=True)

    db = sqlite3.connect(options.dbpath)

    db.execute(
        """
        CREATE TABLE "files" (
            "dirname"       TEXT,
            "basename"      TEXT,
            "mode"  INTEGER,
            "ino"   INTEGER,
            "nlink" INTEGER,
            "uid"   INTEGER,
            "gid"   INTEGER,
            "size"  INTEGER,
            "mtime" INTEGER,
            "atime" INTEGER,
            "ctime" INTEGER,
            PRIMARY KEY("dirname", "basename")
        );
        """
    )

    progress = Progress()
    rootstat = options.root.lstat()
    if options.xdev:
        options.dev = rootstat.st_dev

    insert(options.root, rootstat)
    recurse(options.root)
    db.commit()

    progress.print_end()


db = None
options = None


if __name__ == "__main__":
    main()
