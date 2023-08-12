#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL

import os
import errno
from pathlib import Path
import sqlite3
import stat
import sys

import fuse
from fuse import Fuse


if not hasattr(fuse, "__version__"):
    raise RuntimeError(
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."
    )

fuse.fuse_python_api = (0, 2)

fuse.feature_assert("stateful_files", "has_init")


def decode_name_if_needed(s):
    if isinstance(s, bytes):
        return os.fsdecode(s)
    return s


def to_bytes_if_broken(s):
    try:
        s.encode("utf8")
    except UnicodeError:
        return s.encode("utf8", "surrogateescape")
    else:
        return s


class Decoy(Fuse):
    dbpath = None

    @property
    def db(self):
        return DB

    def getattr(self, path):
        ppath = Path(path)

        for row in self.db.execute(
            "select *, rowid from files where basename = ? and dirname = ?",
            (to_bytes_if_broken(ppath.name), to_bytes_if_broken(str(ppath.parent)[1:])),
        ):
            stat_kwargs = {
                f"st_{field}": max(0, row[field] or 0)
                for field in (
                    "ino",
                    "size",
                    "atime",
                    "mtime",
                    "ctime",
                    "mode",
                    "nlink",
                    "uid",
                    "gid",
                )
            }

            if not stat_kwargs["st_ino"]:
                stat_kwargs["st_ino"] = row["rowid"]

            stat_kwargs["st_dev"] = 0

            return fuse.Stat(**stat_kwargs)

        if path == "/":
            # return a dummy entry if there was none in database
            # else, the mountpoint will be hidden and harder to unmount
            return fuse.Stat(
                st_ino=1,
                st_dev=0,
                st_size=0,
                st_mtime=0,
                st_ctime=0,
                st_atime=0,
                st_nlink=1,
                st_uid=os.getuid(),
                st_gid=os.getgid(),
                st_mode=stat.S_IFDIR | 0o500,
            )

        return -errno.ENOENT

    def xreadlink(self, path):
        return os.readlink("." + path)

    def readdir(self, path, offset):
        ppath = Path(path)

        for row in self.db.execute(
            "select rowid, basename, ino, mode from files where dirname = ?",
            (to_bytes_if_broken(str(ppath)[1:]),),
        ):
            if not row["basename"]:
                continue

            yield fuse.Direntry(
                decode_name_if_needed(row["basename"]),
                ino=row["ino"] or row["rowid"],
                type=row["mode"],
            )

    #    The following utimens method would do the same as the above utime method.
    #    We can't make it better though as the Python stdlib doesn't know of
    #    subsecond preciseness in acces/modify times.
    #
    #    def utimens(self, path, ts_acc, ts_mod):
    #      os.utime("." + path, (ts_acc.tv_sec, ts_mod.tv_sec))

    def access(self, path, mode):
        # if not os.access("." + path, mode):
        #    return -EACCES
        return 0

    def xstatfs(self):
        """
        Should return an object with statvfs attributes (f_bsize, f_frsize...).
        Eg., the return value of os.statvfs() is such a thing (since py 2.2).
        If you are not reusing an existing statvfs object, start with
        fuse.StatVFS(), and define the attributes.

        To provide usable information (ie., you want sensible df(1)
        output, you are suggested to specify the following attributes:

            - f_bsize - preferred size of file blocks, in bytes
            - f_frsize - fundamental size of file blcoks, in bytes
                [if you have no idea, use the same as blocksize]
            - f_blocks - total number of blocks in the filesystem
            - f_bfree - number of free blocks
            - f_files - total number of file inodes
            - f_ffree - nunber of free file inodes
        """

        return os.statvfs(".")

    def fsinit(self):
        pass

    def main(self, *a, **kw):
        return super().main(*a, **kw)


def main():
    global DB

    if sqlite3.threadsafety < 3:
        # force single-threaded if sqlite doesn't serialize access
        sys.argv.insert(1, "-s")

    server = Decoy(dash_s_do="setsingle")
    server.parser.add_option(mountopt="dbpath")

    server.parse(values=server, errex=1)
    if not server.dbpath:
        server.parser.error("missing -o dbath=...")

    server.dbpath = Path(server.dbpath).resolve()
    DB = sqlite3.connect(server.dbpath, check_same_thread=False)
    DB.row_factory = sqlite3.Row

    server.main()


if __name__ == "__main__":
    main()
