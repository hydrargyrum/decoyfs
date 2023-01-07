#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL

import sqlite3
from pathlib import Path
import sys


def getrow(path):
    try:
        stat = path.lstat()
    except FileNotFoundError:
        return None

    relpath = path.relative_to(root)
    parent = str(relpath.parent)
    if parent == ".":
        parent = ""

    tup = (
        parent,
        relpath.name,
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

    return tuple(map(str, tup))


def insert(path):
    row = getrow(path)
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

    for sub in sorted(path.iterdir(), key=sortkey):
        insert(sub)

        if not sub.is_symlink() and sub.is_dir():
            recurse(sub)


if len(sys.argv) > 2:
    root = Path(sys.argv[2])
else:
    root = Path.cwd()

db = sqlite3.connect(sys.argv[1])

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


insert(root)
recurse(root)
db.commit()
