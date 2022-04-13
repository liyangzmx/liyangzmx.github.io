#!/usr/bin/python2

from construct import *
import os
import sys

BOOT_MAGIC = b"ANDROID!"
BOOT_MAGIC_SIZE = 8
BOOT_NAME_SIZE = 16
BOOT_ARGS_SIZE = 512
BOOT_EXTRA_ARGS_SIZE = 1024
BOOT_IMAGE_HEADER_V1_SIZE = 1648
BOOT_IMAGE_HEADER_V2_SIZE = 1660
BOOT_IMAGE_HEADER_V3_SIZE = 1580
BOOT_IMAGE_HEADER_V3_PAGESIZE = 4096
BOOT_IMAGE_HEADER_V4_SIZE = 1584
BOOT_IMAGE_V4_SIGNATURE_SIZE = 4096
FDT_HEADER_SIZE = 40

def padding(size, padding):
  return (padding- (size & (padding - 1))) & (padding - 1)

boot_img_hdr_v0 = Struct (
  "magic" / Const(BOOT_MAGIC, Bytes(BOOT_MAGIC_SIZE)),
  "kernel_size" / Int32ul,
  "kernel_addr" / Hex(Int32ul),
  "ramdisk_size" / Int32ul,
  "ramdisk_addr" / Hex(Int32ul),
  "second_size" / Int32ul,
  "second_addr" / Hex(Int32ul),
  "tags_addr" / Hex(Int32ul),
  "page_size" / Int32ul,
  "header_version" / Int32ul,
  "os_version" / Hex(Int32ul),
  "name" / PaddedString(BOOT_NAME_SIZE, "ascii"),
  "cmdline" / PaddedString(BOOT_ARGS_SIZE, "ascii"),
  "id(hash)" / HexDump(Bytes(4 * 8)),
  Padding(BOOT_EXTRA_ARGS_SIZE)
)

boot_img_hdr_v1 = Struct (
  "boot_img_hdr_v0" / boot_img_hdr_v0,
  "recovery_dtbo_size" / Int32ul,
  "recovery_dtbo_offset" / Hex(Int64ul), 
  "header_size" / Int32ul, 
)

boot_img_hdr_v2 = Struct (
  "boot_img_hdr_v1" / boot_img_hdr_v1,
  "dtb_size" / Int32ul,
  "dtb_addr" / Hex(Int32ul),
)

fdt_reserve_entry = Struct (
  "address" / Hex(Int64ub),
  "size" / Int64ub
)

mem_rsvmap = Struct(
  "address" / Hex(Int64ub),
  "size" / Int64ub,
)

fdt_header  = Struct (
  "_start" / Tell,
  "magic" / Hex(Const(0xd00dfeed , Int32ub)),
  "totalsize" / Int32ub,
  "off_dt_struct" / Int32ub,
  "off_dt_strings" / Int32ub,
  "off_mem_rsvmap" / Int32ub,
  "version" / Int32ub,
  "last_comp_version" / Int32ub,
  "boot_cpuid_phys" / Int32ub,
  "size_dt_strings" / Int32ub,
  "size_dt_struct" / Int32ub,
  Padding(this.off_mem_rsvmap - 40),
  "mem_rsvmap" / mem_rsvmap,
  "dt_struct" / HexDump(Bytes(64)),
  Padding(this.size_dt_struct - 64), 
  "_dt_struct_data" / Bytes(this.size_dt_strings),
  "dt_strings" / RestreamData(this._dt_struct_data, GreedyString("ascii")),
)

dt_table_entry = Struct (
  "dt_size" / Int32ub,
  "dt_offset" / Int32ub,
  "id" / Int32ub,
  "rev" / Int32ub,
  "custom" / Bytes(16),
)

dt_table_header  = Struct (
  # This field shall contain the value 0xd7b7ab1e (big-endian).
  "magic" / Hex(Const(0xd7b7ab1e, Int32ub)),
  "total_size" / Int32ub,
  "header_size" / Int32ub,
  "dt_entry_size" / Int32ub,
  "dt_entry_count" / Int32ub,
  "dt_entries_offset" / Int32ub,
  "page_size" / Int32ub,
  "version" / Int32ub
)

dtbimg = Struct (
  "dt_table_header" / dt_table_header,
  "entries" / Array(this.dt_table_header.dt_entry_count, dt_table_entry),
  "fdt_headers" / Array(this.dt_table_header.dt_entry_count, fdt_header),
)

CPIO_IMG = Struct(
  "magic" / Const(b'070701', Bytes(6)),
  "dev" / PaddedString(6, 'ascii'),
  "ino" / PaddedString(6, 'ascii'),
  "mode" / PaddedString(6, 'ascii'),
  "uid" / PaddedString(6, 'ascii'),
  "gid" / PaddedString(6, 'ascii'),
  "nlink" / PaddedString(6, 'ascii'),
  "rdev" / PaddedString(6, 'ascii'),
  "mtime" / PaddedString(11, 'ascii'), # Timestamp(Int32ub, "msdos", "msdos"),
  "namesize" / PaddedString(6, 'ascii'),
  "filesize" / PaddedString(11, 'ascii'),
)

BOOTIMG = Struct(
  "header" / boot_img_hdr_v2,

  # sizes
  "_page_size" / Computed(this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size),
  "_ramdisk_size" / Computed(this.header.boot_img_hdr_v1.boot_img_hdr_v0.ramdisk_size),
  "_kernel_size" / Computed(this.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size),
  "_second_size" / Computed(this.header.boot_img_hdr_v1.boot_img_hdr_v0.second_size),
  "_recovery_dtbo_size" / Computed(this.header.boot_img_hdr_v1.recovery_dtbo_size),
  "_dtb_size" / Computed(this.header.dtb_size),

  # Pared
  Padding(padding(boot_img_hdr_v2.sizeof(), 
                            this._page_size)),
  # "_kernel_data" / Bytes(this._kernel_size),
  # "kernel" / RestreamData(this._kernel_data, Select(CompressedLZ4(GreedyBytes), Bytes(this._kernel_size))),
  # Padding(padding(this._kernel_size, this._page_size)),
  "kernel" / Padding(this._kernel_size + padding(this._kernel_size, this._page_size)),

  # Must here
  "ramdisk" / Bytes(this._ramdisk_size),
  "cpio_data" / RestreamData(this.ramdisk, Compressed(GreedyBytes, "gzip")),
  "cpio(ramdisk)" / RestreamData(this.cpio_data, CPIO_IMG),
  Padding(padding(this._ramdisk_size, this._page_size)),
  "second" / Padding(this._second_size + padding(this._second_size, this._page_size)),
  "recovery_dtbo" / If(this._recovery_dtbo_size > 0, dtbimg),
  Padding(padding(this._recovery_dtbo_size,  this._page_size)),
  "dtbimg" / IfThenElse(this._dtb_size > 0, Select(dtbimg, fdt_header),  Padding(this._dtb_size + padding(this._dtb_size, this._page_size))),
)

if __name__ == '__main__':
  setGlobalPrintFullStrings(False)
  with open(sys.argv[1], "rb") as f:
    data = f.read()
    bootimg = BOOTIMG.parse(data)
    print(bootimg)
    
    # uncommit underlines to unpack root.cpio.gz
    # offset = 0
    # page_size = bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size
    # offset += page_size
    # print("parge_size: ", page_size)
    # offset += (bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size + 
    #            padding(bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size, page_size))

    # with open("root.cpio.gz", "wb") as out:
    #   out.write(data[offset:offset + bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.ramdisk_size])