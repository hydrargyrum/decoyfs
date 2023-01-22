#!/usr/bin/env python3
# SPDX-License-Identifier: WTFPL
# see https://github.com/deadc0de6/catcli

import json
import sqlite3
import sys
from stat import S_IFREG, S_IFDIR
from os.path import dirname


def recurse(node, prefix):
    if node["type"] == "top":
        #for child in node["children"][0]:
        #	yield from recurse(child, "")
        yield from recurse(node["children"][0], "")
        return

    ret = {}
    if node["type"] == "file":
        ret["mode"] = S_IFREG | 0o444
        ret["mtime"] = node["maccess"]
    elif node["type"] in ("dir", "storage"):
        ret["mode"] = S_IFDIR | 0o555
        ret["mtime"] = node["maccess"]

    ret["basename"] = node["name"]
    if node["type"] == "storage":
        ret["dirname"] = ""
    else:
        ret["dirname"] = f"{prefix}{dirname(node['relpath']).lstrip('/')}".rstrip("/")

    ret["size"] = node["size"]

    yield ret

    if node["type"] == "storage":
        prefix = f"{node['name']}/"

    if "children" in node:
        for child in node["children"]:
            yield from recurse(child, prefix)


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

with open(sys.argv[2]) as fp:
    catalog = json.load(fp)
    for row in recurse(catalog, ""):
        db.execute(
            "INSERT INTO files(dirname, basename, mode, size, mtime) values(?, ?, ?, ?, ?)",
            (row["dirname"], row["basename"], row["mode"], row["size"], row.get("mtime", 0)),
        )

db.commit()
