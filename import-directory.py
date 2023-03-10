#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL

from argparse import ArgumentParser
import sqlite3
import stat
from pathlib import Path
import sys


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

    return True


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
        print(f"error listdir({path}): {exc}", file=sys.stderr)
        return

    for sub in sorted(listed, key=sortkey):
        try:
            statobj = sub.lstat()
        except OSError as exc:
            print(f"error lstat({sub}): {exc}", file=sys.stderr)
            continue

        insert(sub, statobj)

        if stat.S_ISDIR(statobj.st_mode):
            if not options.xdev or options.dev == statobj.st_dev:
                recurse(sub)


def main():
    global db, options

    parser = ArgumentParser()
    parser.add_argument("dbpath")
    parser.add_argument("root", nargs="?")

    parser.add_argument("-x", "--xdev", action="store_true")

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

    rootstat = options.root.lstat()
    if options.xdev:
        options.dev = rootstat.st_dev

    insert(options.root, rootstat)
    recurse(options.root)
    db.commit()


db = None
options = None


if __name__ == "__main__":
    main()
