#!/usr/bin python3

from ast import parse
from construct import *
import sys
import time

# code uses linux epoch in microsoft format?
class UTCTimeStampAdapter(Adapter):
    def _decode(self, obj, context, path):
        return time.ctime(obj)
    def _encode(self, obj, context, path):
        return int(time.mktime(time.strptime(obj)))

class UUIDAdapter(Adapter):
    def _decode(self, obj, context, path):
        s = ''.join([format(x, '02X') for x in obj])
        return '{}-{}-{}-{}-{}'.format(s[0:8], s[8:12], s[12:16], s[16:20], s[20:32])
    
    def _encode(self, obj, context, path):
        return obj

# use core Timestamp
UTCTimeStamp = UTCTimeStampAdapter(Int32ul)
UUID = UUIDAdapter(Bytes(16))
EXT2_LABEL_LEN = 16

super = Struct(
    Padding(1024),
    "s_inodes_count" / Int32ub,
    "s_blocks_count" / Int32ub,
    "s_r_blocks_count" / Int32ub,
    "s_free_blocks_count" / Int32ub,
    "s_free_inodes_count" / Int32ub,
    "s_first_data_block" / Int32ub,
    "s_log_block_size" / Int32ub,
    "s_log_cluster_size" / Int32ub,
    "s_blocks_per_group" / Int32ub,
    "s_clusters_per_group" / Int32ub,
    "s_inodes_per_group" / Int32ub,
    "s_mtime" / UTCTimeStamp,
    "s_wtime" / UTCTimeStamp,
    "s_mnt_count" / Int16ub,
    "s_max_mnt_count" / Int16ub,
    "s_magic"  / Hex(Const(0xEF53, Int16ul)),
    "s_state" / FlagsEnum(
        Int16ub,
        EXT2_VALID_FS = 0x0001,
        EXT2_ERROR_FS = 0x0002,
        EXT3_ORPHAN_FS = 0x0004,
    ),
    "s_errors" / Int16ub,
    "s_minor_rev_level" / Int16ub,
    "s_lastcheck" / UTCTimeStamp,
    "s_checkinterval" / Int32ub,
    "s_creator_os" / Int32ub,
    "s_rev_level" / Enum(
        Int32ub,
        EXT2_GOOD_OLD_REV = 0,
        EXT2_DYNAMIC_REV = 1,
    ),
    "s_def_resuid" / Int16ub,
    "s_def_resgid" / Int16ub,
    "s_first_ino" / Int32ub,
    "s_inode_size" / Int16ub,
    "s_block_group_nr" / Int16ub,
    "s_feature_compat" / FlagsEnum(
        Int32ul,
        EXT2_FEATURE_COMPAT_DIR_PREALLOC = 0x0001,
        EXT2_FEATURE_COMPAT_IMAGIC_INODES = 0x0002,
        EXT3_FEATURE_COMPAT_HAS_JOURNAL = 0x0004,
        EXT2_FEATURE_COMPAT_EXT_ATTR = 0x0008,
        EXT2_FEATURE_COMPAT_RESIZE_INO = 0x0010,
        EXT2_FEATURE_COMPAT_DIR_INDEX = 0x0020,
    ),
    "s_feature_incompat" / FlagsEnum(
        Int32ul,
        EXT2_FEATURE_INCOMPAT_COMPRESSION = 0x0001,
        EXT2_FEATURE_INCOMPAT_FILETYPE = 0x0002,
        EXT3_FEATURE_INCOMPAT_RECOVER = 0x0004,
        EXT3_FEATURE_INCOMPAT_JOURNAL_DEV = 0x0008,
        EXT2_FEATURE_INCOMPAT_META_BG = 0x0010,
        EXT3_FEATURE_INCOMPAT_EXTENTS = 0x0040,
        EXT4_FEATURE_INCOMPAT_64BIT = 0x0080,
        EXT4_FEATURE_INCOMPAT_MMP = 0x0100,
        EXT4_FEATURE_INCOMPAT_FLEX_BG = 0x0200,
        EXT4_FEATURE_INCOMPAT_EA_INODE = 0x0400,
        EXT4_FEATURE_INCOMPAT_DIRDATA = 0x10000,
        EXT4_FEATURE_INCOMPAT_CSUM_SEED = 0x2000,
        EXT4_FEATURE_INCOMPAT_LARGEDIR = 0x4000,
        EXT4_FEATURE_INCOMPAT_INLINE_DATA = 0x8000,
        EXT4_FEATURE_INCOMPAT_ENCRYPT = 0x10000,
        EXT4_FEATURE_INCOMPAT_CASEFOLD = 0x20000,
    ),
    "s_feature_ro_compat" / FlagsEnum(
        Int32ul,
        EXT2_FEATURE_RO_COMPAT_SPARSE_SUPER = 0x0001,
        EXT2_FEATURE_RO_COMPAT_LARGE_FILE = 0x0002,
        EXT2_FEATURE_RO_COMPAT_BTREE_DIR = 0x0004,
        EXT4_FEATURE_RO_COMPAT_HUGE_FILE = 0x0008,
        EXT4_FEATURE_RO_COMPAT_GDT_CSUM	 = 0x0010,
        EXT4_FEATURE_RO_COMPAT_DIR_NLINK = 0x0020,
        EXT4_FEATURE_RO_COMPAT_EXTRA_ISIZE = 0x0040,
        EXT4_FEATURE_RO_COMPAT_HAS_SNAPSHOT = 0x0080,
        EXT4_FEATURE_RO_COMPAT_QUOTA = 0x0100,
        EXT4_FEATURE_RO_COMPAT_BIGALLOC = 0x0200,
        EXT4_FEATURE_RO_COMPAT_METADATA_CSUM = 0x0400,
        EXT4_FEATURE_RO_COMPAT_REPLICA = 0x0800,
        EXT4_FEATURE_RO_COMPAT_READONLY = 0x1000,
        EXT4_FEATURE_RO_COMPAT_PROJECT = 0x2000,
        EXT4_FEATURE_RO_COMPAT_SHARED_BLOCKS = 0x4000,
        EXT4_FEATURE_RO_COMPAT_VERITY = 0x8000,
    ),
    "s_uuid" / UUID,
    "s_volume_name" / PaddedString(EXT2_LABEL_LEN, "ascii"),
    "s_last_mounted" / PaddedString(64, "ascii"),
    "s_algorithm_usage_bitmap" / Hex(Int32ul),
    "s_prealloc_blocks" / Byte,
    "s_prealloc_dir_blocks" / Byte,
    "s_reserved_gdt_blocks" / Int16ub,
    "s_journal_uuid" / UUID,
    "s_journal_inum" / Int32ub,
    "s_journal_dev" / Int32ub,
    "s_last_orphan" / Int32ub,
    "s_hash_seed" / Bytes(16),
    "s_def_hash_version" / Byte,
    "s_jnl_backup_type" / Byte,
    "s_desc_size" / Int16ub,
    "s_default_mount_opts" / FlagsEnum(
        Int32ul,
        EXT2_MOUNT_CHECK = 0x0001,
        EXT2_MOUNT_GRPID = 0x0004,
        EXT2_MOUNT_DEBUG = 0x0008,
        EXT2_MOUNT_ERRORS_CONT = 0x0010,
        EXT2_MOUNT_ERRORS_RO = 0x0020,
        EXT2_MOUNT_ERRORS_PANIC = 0x0040,
        EXT2_MOUNT_MINIX_DF = 0x0080,
        EXT2_MOUNT_NO_UID32 = 0x0200,
    ),
    "s_first_meta_bg" / Int32ub,
    "s_mkfs_time" / UTCTimeStamp,
    "s_jnl_blocks" / Bytes(4 * 17),
    "s_blocks_count_hi" / Int32ub,
    "s_r_blocks_count_hi" / Int32ub,
    "s_free_blocks_hi" / Int32ub,
    "s_min_extra_isize" / Int16ub,
    "s_want_extra_isize" / Int16ub,
    "s_flags" / FlagsEnum(
        Int32ub,
        EXT2_FLAGS_SIGNED_HASH = 0x0001,
        EXT2_FLAGS_UNSIGNED_HASH = 0x0002,
        EXT2_FLAGS_TEST_FILESYS = 0x0004,
        EXT2_FLAGS_IS_SNAPSHOT = 0x0010,
        EXT2_FLAGS_FIX_SNAPSHOT	= 0x0020,
        EXT2_FLAGS_FIX_EXCLUDE = 0x0040,
    ),
    "s_raid_stride" / Int16ub,
    "s_mmp_update_interval" / Int16ub,
    "s_mmp_block" / Int64ub,
    "s_raid_stripe_width" / Int32ub,
    "s_log_groups_per_flex" / Byte,
    "s_checksum_type" / Byte,
    "s_encryption_level"  / Byte,
    "s_reserved_pad" / Byte,
    "s_kbytes_written" / Int64ub,
    "s_snapshot_inum" / Int32ub,
    "s_snapshot_id" / Int32ub,
    "s_snapshot_r_blocks_count" / Int64ub,
    "s_snapshot_list" / Int32ub,
    "s_error_count" / Int32ub,
    "s_first_error_time" / UTCTimeStamp,
    "s_first_error_ino" / Int32ub,
    "s_first_error_block" / Int64ub,
    "s_first_error_func" / Bytes(32), 
    "s_first_error_line" / Int32ub,
    "s_last_error_time" / UTCTimeStamp,
    "s_last_error_ino" / Int32ub,
    "s_last_error_line" / Int32ub,
    "s_last_error_block" / Int64ub,
    "s_last_error_func" / Bytes(32), 
    "s_mount_opts" / Bytes(64),
    "s_usr_quota_inum" / Int32ub,
    "s_grp_quota_inum" / Int32ub,
    "s_overhead_blocks" / Int32ub,
    "s_backup_bgs" / Int32ub[2],
    "s_encrypt_algos" / Bytes(4),
    "s_encrypt_pw_salt" / Bytes(16),
    "s_lpf_ino" / Int32ul,
    "s_prj_quota_inum" / Int32ul,
    "s_checksum_seed" / Int32ul,
    "s_wtime_hi" / Byte,
    "s_mtime_hi" / Byte,
    "s_mkfs_time_hi" / Byte,
    "s_lastcheck_hi" / Byte,
    "s_first_error_time_hi" / Byte,
    "s_last_error_time_hi" / Byte,
    "s_pad" / Bytes(2),
    "s_encoding" / Int16ul,
    "s_encoding_flags"  / Int16ul,
    "s_reserved" / Bytes(4 * 95),
    "s_checksum" / Hex(Int32ub),
)

def parse_metadata(filename):
    with open(filename, 'rb') as f:
        data = f.read(4096)
        meta = super.parse(data)
        print(meta)


if __name__ == "__main__":
    # parse_metadata(sys.argv[1])
    parse_metadata("/home/nickli/work/aosp/out/target/product/crosshatch/system_raw.img")
