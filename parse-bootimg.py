#!/usr/bin/python2

from tkinter.tix import Select
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

PAGE_SIZE = 2048

def padding(size, padding):
  return (padding- (size & (padding - 1))) & (padding - 1)

# boot_img_hdr_v3 = Struct (
#   "magic" / Const(b"ANDROID!", Bytes(8)),
#   "kernel_size" / Int32ul,
#   "ramdisk_size" / Int32ul,
#   "os_version" / Hex(Int32ul),
#   "header_size" / Int32ul,
#   Padding(4 * 4),
#   "header_version" / Int32ul,
#   "cmdline" / PaddedString(BOOT_EXTRA_ARGS_SIZE + BOOT_ARGS_SIZE, "ascii"),
# )

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
  "mem_rsvmap" / Pointer(this._start + this.off_mem_rsvmap, mem_rsvmap),
  "dt_struct" / Pointer(this._start + this.off_dt_struct, HexDump(Bytes(64))), 
  "dt_strings" / Pointer(this._start + this.off_dt_strings, HexDump(Bytes(64))),
  Padding(this.totalsize - 40),
)

dt_table_entry = Struct (
  "dt_size" / Int32ub,
  "dt_offset" / Int32ub,
  "id" / Int32ub,
  "rev" / Int32ub,
  "custom" / Array(4, Int32ub),
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

BOOTIMG = Struct(
  "header" / boot_img_hdr_v2,
  Padding(padding(boot_img_hdr_v2.sizeof(), 
                            this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size)),
  "kernel" / Padding(this.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size + 
                            padding(this.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size, 
                            this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size)),
  "ramdisk" / Padding(this.header.boot_img_hdr_v1.boot_img_hdr_v0.ramdisk_size + 
                            padding(this.header.boot_img_hdr_v1.boot_img_hdr_v0.ramdisk_size, 
                            this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size)),
  "second" / Padding(this.header.boot_img_hdr_v1.boot_img_hdr_v0.second_size + 
                            padding(this.header.boot_img_hdr_v1.boot_img_hdr_v0.second_size, 
                            this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size)),
  "recovery_dtbo" / If(this.header.boot_img_hdr_v1.recovery_dtbo_size > 0, dtbimg),
  Padding(padding(this.header.boot_img_hdr_v1.recovery_dtbo_size, 
                            this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size)),
  "dtbimg" / IfThenElse(this.header.dtb_size > 0, Select(dtbimg, fdt_header), 
                            Padding(this.header.dtb_size +
                            padding(this.header.dtb_size, this.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size))),
)

if __name__ == '__main__':
    with open(sys.argv[1], "rb") as f:
        data = f.read()
        bootimg = BOOTIMG.parse(data)
        
        # uncommit underlines to unpack root.cpio.gz
        # offset = 0
        # page_size = bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.page_size
        # offset += page_size
        # print("parge_size: ", page_size)
        # offset += (bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size + 
        #            padding(bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.kernel_size, page_size))

        # with open("root.cpio.gz", "wb") as out:
        #   out.write(data[offset:offset + bootimg.header.boot_img_hdr_v1.boot_img_hdr_v0.ramdisk_size])
        print(bootimg)