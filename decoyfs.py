#!/usr/bin/env python3

import os
import errno
from threading import Lock, local
from pathlib import Path
import sqlite3

import fuse
from fuse import Fuse


if not hasattr(fuse, "__version__"):
    raise RuntimeError(
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."
    )

fuse.fuse_python_api = (0, 2)

fuse.feature_assert("stateful_files", "has_init")


def flag2mode(flags):
    md = {os.O_RDONLY: "rb", os.O_WRONLY: "wb", os.O_RDWR: "wb+"}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]

    if flags | os.O_APPEND:
        m = m.replace("w", "a", 1)

    return m


class Decoy(Fuse):
    def __init__(self, *args, **kw):
        Fuse.__init__(self, *args, **kw)
        self.dbpath = None
        self.tls = local()

    @property
    def db(self):
        try:
            return self.tls.db
        except AttributeError:
            pass

        self.tls.db = sqlite3.connect(self.dbpath)
        self.tls.db.row_factory = sqlite3.Row
        return self.tls.db

    def getattr(self, path):
        ppath = Path(path)

        for row in self.db.execute(
            "select * from files where basename = ? and dirname = ?",
            (ppath.name, str(ppath.parent)[1:]),
        ):
            stat_kwargs = {
                f"st_{field}": row[field] or 0
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
            stat_kwargs["st_dev"] = 0

            return fuse.Stat(**stat_kwargs)

        return -errno.ENOENT

    def xreadlink(self, path):
        return os.readlink("." + path)

    def readdir(self, path, offset):
        ppath = Path(path)

        for row in self.db.execute(
            "select rowid, basename, ino, mode from files where dirname = ?",
            (str(ppath)[1:],),
        ):
            if not row["basename"]:
                continue

            yield fuse.Direntry(
                row["basename"],
                ino=row["ino"],
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

    class XmpFile(object):
        def __init__(self, path, flags, *mode):
            self.file = os.fdopen(os.open("." + path, flags, *mode), flag2mode(flags))
            self.fd = self.file.fileno()
            if hasattr(os, "pread"):
                self.iolock = None
            else:
                self.iolock = Lock()

        def read(self, length, offset):
            if self.iolock:
                self.iolock.acquire()
                try:
                    self.file.seek(offset)
                    return self.file.read(length)
                finally:
                    self.iolock.release()
            else:
                return os.pread(self.fd, length, offset)

        def release(self, flags):
            self.file.close()

        def fgetattr(self):
            return os.fstat(self.fd)

    def main(self, *a, **kw):
        # self.file_class = self.XmpFile
        return super().main(*a, **kw)


def main():
    server = Decoy(dash_s_do="setsingle")

    server.parser.add_option(mountopt="dbpath")
    server.parse(values=server, errex=1)

    server.main()


if __name__ == "__main__":
    main()
