# decoy-fs

decoyfs is a FUSE filesystem that reproduces a tree hierarchy of files and folders stored in SQLite.
The files have no content though (hence *decoy*), this filesystem is only for browsing the hierarchy.

decoy-fs comes with a tool to snapshot an directory tree in such an SQLite database.

## Example

Let's say we snapshotted a directory in `sample.sqlite`. See how it looks:

```shell
% sqlite3 sample.sqlite "select * from files"
┌─────────┬───────────────┬───────┬──────────┬───────┬──────┬──────┬──────────┬──────────────────┬──────────────────┬──────────────────┐
│ dirname │   basename    │ mode  │   ino    │ nlink │ uid  │ gid  │   size   │      mtime       │      atime       │      ctime       │
├─────────┼───────────────┼───────┼──────────┼───────┼──────┼──────┼──────────┼──────────────────┼──────────────────┼──────────────────┤
│         │               │ 16877 │ 24698924 │ 4     │ 1000 │ 1000 │ 4096     │ 1672860821.58673 │ 1672860786.2864  │ 1672860821.58673 │
│         │ bar           │ 16877 │ 24698926 │ 3     │ 1000 │ 1000 │ 4096     │ 1672861017.35253 │ 1672860821.58673 │ 1672861017.35253 │
│         │ foo           │ 16877 │ 24698925 │ 2     │ 1000 │ 1000 │ 4096     │ 1672860903.35948 │ 1672860821.58673 │ 1672860903.35948 │
│ bar     │ baz           │ 16877 │ 24699120 │ 2     │ 1000 │ 1000 │ 4096     │ 1672861045.02878 │ 1672860821.58673 │ 1672861045.02878 │
│ bar/baz │ archive.tgz   │ 33188 │ 24653449 │ 1     │ 1000 │ 1000 │ 11768008 │ 1669434053       │ 1669434053       │ 1672861045.24478 │
│ bar     │ script.sh     │ 33261 │ 24653447 │ 1     │ 1000 │ 1000 │ 5920     │ 1672860424.38708 │ 1672860424.38708 │ 1672861017.35253 │
│ foo     │ document.txt  │ 33188 │ 24653307 │ 1     │ 1000 │ 1000 │ 0        │ 1672860857.03905 │ 1672860857.03905 │ 1672860903.35948 │
│ foo     │ something.png │ 33188 │ 24653446 │ 1     │ 1000 │ 1000 │ 25296    │ 1672391150.51346 │ 1672391150.46946 │ 1672860894.4594  │
└─────────┴───────────────┴───────┴──────────┴───────┴──────┴──────┴──────────┴──────────────────┴──────────────────┴──────────────────┘
```

*Empty `dirname` column is the root directory.*

Now we can run decoyfs to mount that virtual tree to `./mnt/`:

```shell
% decoyfs -o dbpath=sample.sqlite ./mnt/
```

We can now explore the virtual tree:

```shell
% ls mnt
bar  foo
% tree -psDFh mnt/
[drwxr-xr-x 4.0K Jan  4 20:33]  mnt/
├── [drwxr-xr-x 4.0K Jan  4 20:36]  bar/
│   ├── [drwxr-xr-x 4.0K Jan  4 20:37]  baz/
│   │   └── [-rw-r--r--  11M Nov 26 04:40]  archive.tgz
│   └── [-rwxr-xr-x 5.8K Jan  4 20:27]  script.sh*
└── [drwxr-xr-x 4.0K Jan  4 20:35]  foo/
    ├── [-rw-r--r--    0 Jan  4 20:34]  document.txt
    └── [-rw-r--r--  25K Dec 30 10:05]  something.png

4 directories, 4 files
```

## Generate the database

The [ls-to-sqlite.py](ls-to-sqlite.py) tool can generate a SQLite database with the proper schema and fill it with entries from an actual directory:

```
ls-to-sqlite.py sample.sqlite real_folder/
```

The format is pretty simple so it's easy to create another tool to create such a database from another source (tar archive, remote file system, etc.)

The schema is as follows:

```sql
CREATE TABLE "files" (
    "dirname"  TEXT,
    "basename" TEXT,
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
```

### catcli

It's also possible to import [catcli](https://github.com/deadc0de6/catcli) databases:

```
import-catcli.py myfiles.sqlite myfiles.catcli
```
