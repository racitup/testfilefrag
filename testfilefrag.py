#!/usr/bin/python3
"""Validates the output of filefrag -e for various filesystems on Linux.

Run with sudo.
Tested with e2fsprogs v1.42.12: vfat FAILED, btrfs ERROR, others: PASSED

Known issues:
 btrfs mkfs causes exception with:
    'Error: error checking /dev/loop3p1 mount status' and returncode=1

###
Original work Copyright 2016 Richard Case

Everyone is permitted to copy, distribute and modify this script,
subject to this statement and the copyright notice above being included.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM.
"""
import subprocess, re, os, sys, signal
from binascii import hexlify

VERSION = 'v1.0.0'

filesystems = [
    ('vfat', 'fat32', ''),
    ('ext4', 'ext4', ''),
    ('hfsplus', 'hfs', ''),
    ('ntfs', 'NTFS', ''),
    ('xfs', 'xfs', '-f'),
    ('btrfs', 'btrfs', '--force')
]

def exe(cmd, info=True):
    "Runs a subprocess and returns stdout."
    proc = subprocess.Popen(cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()

    out = stdout.decode('utf-8').strip()
    err = stderr.decode('utf-8').strip()

    if info:
        lines = out.splitlines()
        if len(lines) > 12:
            topbottom = lines[:8] + ['...'] + lines[-4:]
            debstr = '\n'.join(topbottom)
        else:
            debstr = out
        log = 'exe: cmd={}, out={}, err={}'.format(cmd, debstr, err)
        if proc.returncode != 0:
            log += ', RET={}'.format(proc.returncode)
        print(log)
    if proc.returncode != 0:
        raise Exception('Returncode')
    return out

pat_filefrag = re.compile(r"\s*\d+:\s+\d+\.\.\s+\d+:\s+(\d+)\.\.\s+(\d+):\s+(\d+)")
def parse_filefrag(path):
    "Parse filefrag output & return extent list & the number of sectors."
    text = exe('filefrag -b512 -e -s ' + path)
    genline = (m.group(0) for m in re.finditer(r"^.+$", text, re.MULTILINE))
    total = 0
    extent_list = []
    for line in genline:
        ematch = pat_filefrag.match(line)
        if ematch:
            extent = ematch.groups()
            # filefrag returns physical offsets relative to partition start
            start = int(extent[0])
            size = int(extent[2])
            total += size
            extent_list += [(start, size)]
    if total > 0 and len(extent_list) > 0:
        # merge consecutive extents
        mergetotal = 0
        merged = []
        prev_start, prev_size = None, None
        for estart, esize in extent_list:
            # start
            if prev_start is None:
                prev_start, prev_size = estart, esize
            # consecutive
            elif prev_start + prev_size == estart:
                prev_size += esize
            elif estart + esize == prev_start:
                prev_start = estart
                prev_size += esize
            # overlap!
            elif (prev_start <= estart < prev_start + prev_size or
                  prev_start < estart + esize <= prev_start + prev_size):
                print('Overlap found: {}:{} & {}:{}'
                        .format(prev_start, prev_size, estart, esize))
                prev_start = min(prev_start, estart)
                prev_size = max(prev_start + prev_size, estart + esize) - prev_start
            # gap
            else:
                merged += [(prev_start, prev_size)]
                mergetotal += prev_size
                prev_start, prev_size = estart, esize
        merged += [(prev_start, prev_size)]
        mergetotal += prev_size
        print('Merged extents: before={}:{}, after={}:{}, list={}'
                .format(len(extent_list), total, len(merged), mergetotal, merged))
        extent_list = merged
        total = mergetotal
    return total, extent_list

def test_filefrag(path, fstype, loop, elist):
    "Validates the output of filefrag."
    result = None
    cmpsize = 256
    if os.path.isfile(path) and os.stat(path).st_size > cmpsize:
        with open(path, 'rb') as fdesc:
            file1kA = fdesc.read(cmpsize)
        readin = 0
        i = 0
        file1kB = b''
        with open(loop, 'rb') as fdesc:
            while readin < cmpsize:
                estart, esize = elist[i]
                esizeB = esize * 512
                # Default seek whence is SEEK_SET, i.e. from start or 0
                fdesc.seek(estart * 512)
                remaining = cmpsize - readin
                if esizeB >= (remaining):
                    file1kB += fdesc.read(remaining)
                    readin += remaining
                else:
                    file1kB += fdesc.read(esizeB)
                    readin += esizeB
                i += 1
        if file1kA == file1kB:
            print('RESULT: filefrag validation PASSED for {}.'
                            .format(fstype))
            result = True
        else:
            print('RESULT: filefrag validation FAILED for {}.'
                            .format(fstype))
            print('A: {}'.format(hexlify(file1kA)))
            print('B: {}'.format(hexlify(file1kB)))
            result = False
    if result is None:
        print('RESULT: File not suitable.')
    return result

MOUNTED = False
def cleanup():
    "Cleanup after script."
    if MOUNTED:
        exe('umount /dev/loop3p1')
    exe('losetup --detach /dev/loop3')
    exe('blockdev --rereadpt /dev/loop3')
    exe('rm ./temp.img')
    exe('rm ./random')
    exe('rmdir ./mnt')

# EXCEPTION HANDLER
SYSEXCEPTHOOK = sys.excepthook
def globalexceptions(typ, value, traceback):
    "Override system exception handler to clean up before exit."
    print('Caught Exception!')
    cleanup()
    SYSEXCEPTHOOK(typ, value, traceback)
sys.excepthook = globalexceptions

# CTRL+C HANDLER
def signal_handler(signal, frame):
    print('Caught SIGINT!')
    cleanup()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

# Requires 1G disk space
exe('mkdir ./mnt')
exe('dd if=/dev/urandom of=rand bs=512 count=4')
for _ in range(5250):
    exe('dd if=./rand of=random conv=notrunc oflag=append status=none', False)
exe('rm ./rand')
exe('dd if=/dev/zero of=temp.img bs=512 count=1048576')
exe('losetup /dev/loop3 ./temp.img')
for fstype, pttype, force in filesystems:
    print('### START {} ###'.format(fstype))
    exe('parted -s /dev/loop3 mklabel msdos')
    exe('parted -s /dev/loop3 mkpart primary ' + pttype + ' 2048s 1026047s')
    exe('blockdev --rereadpt /dev/loop3')
    exe('mkfs -t ' + fstype + ' ' + force + ' /dev/loop3p1')
    exe('mount /dev/loop3p1 ./mnt')
    MOUNTED = True
    exe('cp ./random ./mnt/')
    nsectors, elist = parse_filefrag('./mnt/random')
    test_filefrag('./mnt/random', fstype, '/dev/loop3p1', elist)
    exe('df -B 512 ./mnt')
    stat = os.statvfs('./mnt')
    blksects = stat.f_frsize // 512
    # Seems xfs can't completely fill available space
    free = stat.f_bavail * blksects - 100
    exe('dd if=/dev/zero of=./mnt/empty bs=512 count=' + str(free))
    exe('df -B 512 ./mnt')
    nsectors, elist = parse_filefrag('./mnt/empty')
    exe('umount /dev/loop3p1')
    MOUNTED = False
    if fstype not in ('ntfs', 'btrfs', 'xfs'):
        exe('fsck /dev/loop3p1 -- -n')
    exe('cat /sys/class/block/loop3p1/size')
    print('### FINISH {} ###'.format(fstype))

cleanup()

