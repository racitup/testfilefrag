# testfilefrag
A python script that validates the output of filefrag -e for various filesystems on Linux.

##Usage:
1. download
2. chmod u+x
3. check to ensure you have approximately 1GB free hard disk space in the cwd
4. run in a terminal with sudo and no arguments

##Required Linux packages:
* python3
* e2fsprogs
* mount
* util-linux
* coreutils
* parted
* dosfstools
* ntfs-3g
* xfsprogs
* btrfs-tools
* hfsprogs

##Results:
See the [wiki](https://github.com/racitup/testfilefrag/wiki)

##Known issues:
 btrfs mkfs causes exception with:
    `Error: error checking /dev/loop3p1 mount status` and returncode=1

##License:
Original work Copyright 2016 Richard Case

Everyone is permitted to copy, distribute and modify this script,
subject to this statement and the copyright notice above being included.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM.
