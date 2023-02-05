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


def to_bytes_if_broken(s):
    try:
        s.encode("utf8")
    except UnicodeError:
        return s.encode("utf8", "surrogateescape")
    else:
        return s


def insert(parent, match):
    if match["iso"]:
        mtime = datetime.datetime.fromisoformat(match["iso"])
    elif match["recent"]:
        # this format is used if mtime is in the last 6 months
        # the year is missing, and so by default strptime will use 1900.
        # we could accept that and compute the year afterwards, except it might
        # fail for february 29th which did not exist in 1900.
        # so we force a leap year at first in order to accept 02-09.
        mtime = datetime.datetime.strptime(f'1904 {match["recent"]}', "%Y %b %d %H:%M")
        # then we determine the appropriate year
        today = datetime.date.today()
        if today.month >= mtime.month >= today.month - 6:
            # example: today=december[12] mtime=october[10]
            mtime = mtime.replace(year=today.year)
        elif mtime.month >= today.month + 6:
            # example: today=january[1] mtime=november[11]
            mtime = mtime.replace(year=today.year - 1)
        else:
            # example: today=october[10] mtime=december[12]
            # this violates the POSIX requirements, assume anything
            mtime = mtime.replace(year=today.year)

    elif match["old"]:
        mtime = datetime.datetime.strptime(match["old"], "%b %d %Y")

    if match["dev"]:
        size = 0
    else:
        size = int(match["size"])

    mtime = calendar.timegm(mtime.timetuple())

    row = (
        to_bytes_if_broken(str(parent)),
        to_bytes_if_broken(match["filename"]),
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
for line in sys.stdin.buffer:
    line = line.decode("utf8", "surrogateescape")
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
