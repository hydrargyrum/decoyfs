#!/usr/bin/env pytest
# SPDX-License-Identifier: WTFPL

import functools
import subprocess
import os
from pathlib import Path

import pytest


srcpath = Path(__file__).parent.resolve()


@pytest.fixture()
def mount(tmp_path):
    obj = functools.partial(do_mount, target=str(tmp_path))
    obj.path = tmp_path
    yield obj
    subprocess.check_call(["fusermount", "-u", str(tmp_path)])


def do_mount(db_filename, target):
    subprocess.check_call([f"{srcpath.parent}/decoyfs.py", "-o", f"dbpath={srcpath}/{db_filename}", target])


def test_foo(mount):
    mount("sample.sqlite")
    assert list(os.walk(mount.path)) == [
        (f"{mount.path}", ["bar", "foo"], []),
        (f"{mount.path}/bar", ["baz"], ["script.sh"]),
        (f"{mount.path}/bar/baz", [], ["archive.tgz"]),
        (f"{mount.path}/foo", [], ["document.txt", "something.png"]),
    ]
    assert os.path.getsize(mount.path / "bar/baz/archive.tgz") == 11768008
