#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL

# LANG=C ls -laniR <directory> | import-ls.py output.sqlite

import calendar
import datetime
from pathlib import Path
import re
import sqlite3
import stat
import sys


def insert(parent, match):
    if match["iso"]:
        mtime = datetime.datetime.fromisoformat(match["iso"])
    elif match["recent"]:
        mtime = datetime.datetime.strptime(match["recent"], "%b %e %H:%M")
    elif match["old"]:
        mtime = datetime.datetime.strptime(match["old"], "%b %e %Y")

    if match["dev"]:
        size = 0
    else:
        size = int(match["size"])

    mtime = calendar.timegm(mtime.timetuple())

    row = (
        parent,
        match["filename"],
        parse_modeline(match["mode"]),
        int(match["ino"]),
        int(match["nlink"]),
        int(match["uid"]),
        int(match["gid"]),
        size,
        mtime,
        mtime,
        mtime,
    )

    row = tuple(map(str, row))

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


filetypes = {
    "-": stat.S_IFREG,
    "d": stat.S_IFDIR,
    "l": stat.S_IFLNK,
    "s": stat.S_IFSOCK,
    "p": stat.S_IFIFO,
    "b": stat.S_IFBLK,
    "c": stat.S_IFCHR,
}


def parse_modeline(record):
    s_type = record[0]
    s_perms = record[1:10]

    perms = 0
    for n, sbit in enumerate(reversed(s_perms)):
        if sbit != "-":
            perms |= 1 << n

    type_ = filetypes[s_type]
    # raise NotImplementedError(record)

    return type_ | perms


ignore_line = re.compile(r"total \d+|")
path_line = re.compile(r"(.*):")
entry_line = re.compile(r"""
    \s*
    (?P<ino>\d+)\s+
    (?P<mode>[dlbcps-][r-][w-][xSsTt-][r-][w-][xSsTt-][r-][w-][xSsTt-])\s+
    (?P<nlink>\d+)\s+
    (?P<uid>\d+)\s+
    (?P<gid>\d+)\s+
    (?:
        (?P<size>\d+)|
        (?P<dev>\d+,\s+\d+)
    )\s+
    (?P<datetime>
        # this format seems on android
        (?P<iso>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})|
        # the 2 following formats are described by POSIX
        (?P<recent>\w+\s+\d+\s+\d{2}:\d{2})|
        (?P<old>\w+\s+\d+\s+\d{4})
    )\s+
    (?P<filename>[^/]+)(?:\s->\s(?P<symlink>.*))?
""", re.X)


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

lastpath = None
for line in sys.stdin:
    line = line.rstrip()

    if ignore_line.fullmatch(line):
        continue

    match = path_line.fullmatch(line)
    if match:
        lastpath = Path(match[1])
        continue

    match = entry_line.fullmatch(line)
    assert match, f"bad line {line!r}"

    if match["filename"] in (".", ".."):
        continue
    #print(lastpath, match["filename"])

    try:
        insert(lastpath, match)
    except sqlite3.IntegrityError as exc:
        print(f"could not insert({lastpath}/{match['filename']}): {exc}", file=sys.stderr)

db.commit()