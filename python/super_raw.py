#!/usr/bin python3

from construct import *
import sys

SPARSE_HEADER = Struct(
    "magic" / Hex(Const(0xed26ff3a, Int32ul)),
    "major_version" / Int16ul,
    "minor_version" / Int16ul,
    "file_header_size" / Int16ul,
    "chunk_header_size" / Int16ul,
    "block_size" / Int32ul,
    "total_blocks" / Int32ul,
    "total_chunks" / Int32ul,
    "image_checksum" / Int32ul
)

CHUNK_HEADER = Struct(
    "chunk_type" / Enum(Int16ul,
        RAW = 0xCAC1,
        FILL = 0xCAC2,
        DONT_CARE = 0xCAC3,
        CRC = 0xCAC4
    ),
    Int16ul,                # reserved1
    "chunk_size" / Int32ul,
    "total_size" / Int32ul
)

CHUNK = Struct(
    "header" / RawCopy(CHUNK_HEADER),
    "data" / Switch(this.header.value.chunk_type,
            {
                "RAW": Bytes(this.header.value.total_size - CHUNK_HEADER.sizeof()),
                "FILL": Int32ul,
                "DONT_CARE": Bytes(0),
                "CRC": Hex(Int32ul)
            }
        )
)

SPARSE = Struct(
    "header" / RawCopy(SPARSE_HEADER),
    "chunks" / GreedyRange(CHUNK)
)

# size
LP_PARTITION_RESERVED_BYTES = 4096
LP_METADATA_GEOMETRY_SIZE = 4096
LP_METADATA_HEADER_SIZE = 256
LP_METADATA_SIZE = 65536

# magic
LP_METADATA_GEOMETRY_MAGIC = 0x616c4467
LP_METADATA_HEADER_MAGIC = 0x414c5030

LpMetadataGeometry = Struct(
    "magic" / Hex(Const(LP_METADATA_GEOMETRY_MAGIC, Int32ul)),
    "struct_size" / Int32ul,
    
    # caclulate checksum must set checksu[32] first, f**k...
    # "struct_size" / RawCopy(Int32ul),
    # "checksum" / Checksum(Bytes(32), lambda data: hashlib.sha256(data).digest(), this.struct_size.data),
    "checksum" / Hex(Bytes(32)),
    "metadata_max_size" / Int32ul,
    "metadata_slot_count" / Int32ul,
    "logical_block_size" / Int32ul,
)

LpMetadataTableDescriptor = Struct(
    "offset" / Int32ul,
    "num_entries" / Int32ul,
    "entry_size" / Int32ul
)

LpMetadataHeader = Struct(
    "magic" / Hex(Const(LP_METADATA_HEADER_MAGIC, Int32ul)),
    "major_version" / Int16ul,
    "minor_version" / Int16ul,
    "header_size" / Int32ul,
    "header_checksum" / Hex(Bytes(32)),
    "tables_size" / Int32ul,
    "table_checksum" / Hex(Bytes(32)),
    "partitions" / LpMetadataTableDescriptor,
    "extents" / LpMetadataTableDescriptor,
    "groups" / LpMetadataTableDescriptor,
    "block_devices" / LpMetadataTableDescriptor,
    "flags" / Int32ul,
    Padding(124)
)

LpMetadataExtent = Struct(
    "num_sectors" / Int64ul,
    "target_type" / Enum(
        Int32ul,
        DM_LINEAR=0,
        DM_ZERO=1
    ),
    "target_data" / Int64ul,
    "target_source" / Int32ul
)

LpMetadataPartitionGroup = Struct(
    "name" / PaddedString(36, "ascii"),
    "flags" / Int32ul,
    "maximum_size" / Int64ul
)

LpMetadataBlockDevice = Struct(
    "first_logic_sector" / Int64ul,
    "alignment" / Int32ul,
    "alignment_offset" / Int32ul,
    "size" / Int64ul,
    "partition_name" / PaddedString(36, "ascii"),
    "flags" / Int32ul
)

LpMetadataPartition = Struct(
    "_start" / Tell,
    "name" / PaddedString(36, "ascii"),
    "attributes" / FlagsEnum(
        Int32ul, 
        LP_PARTITION_ATTR_READONLY = (1 << 0),
        LP_PARTITION_ATTR_SLOT_SUFFIXED = (1 << 1),
        LP_PARTITION_ATTR_UPDATED = (1 << 2),
        LP_PARTITION_ATTR_DISABLED = (1 << 3),
    ),
    "first_extent_index" / Int32ul,
    "num_extents" / Int32ul,
    "group_index" / Int32ul,
    "_end" / Tell,
    "extents" / If(
        this.num_extents > 0, 
        Pointer(
            this._._header_start + this._.header.header_size + 
            this._.header.extents.offset + 
            this.first_extent_index * this._.header.extents.entry_size,
            Array(
                this.num_extents, 
                Padded(
                    this._.header.extents.entry_size, 
                    LpMetadataExtent
                )
            )
        )
    ),
    "group" / Pointer(
        this._._header_end + 
        this._.header.groups.offset + 
        this.group_index * this._.header.groups.entry_size, 
        LpMetadataPartitionGroup
    ),
)

LpMetadataHeaderV1_0 = Struct(
    "magic" / Int32ul,
    "major_version" / Int16ul,
    "minor_version" / Int16ul,
    "header_size" / Int32ul,
    "header_checksum" / Hex(Bytes(32)),
    "tables_size" / Int32ul,
    "tables_checksum" / Hex(Bytes(32)),
    "partitions" / LpMetadataTableDescriptor,
    "extents" / LpMetadataTableDescriptor,
    "groups" / LpMetadataTableDescriptor,
    "block_devices" / LpMetadataTableDescriptor
)

LpMetadataHeaderV1_2 = LpMetadataHeader

LpMetaData = Struct(
    "_header_start" / Tell,
    "header" / LpMetadataHeader,
    "_header_end" / Tell,
    "_padded" / Computed(
        this.header.partitions.entry_size * this.header.partitions.num_entries + 
        this.header.extents.entry_size * this.header.extents.num_entries + 
        this.header.groups.entry_size * this.header.groups.num_entries 
    ),
    # parse the "extends" / "group" / "block_device" in "partitions"
    "partitions" / Pointer(
        this._header_start + this.header.header_size + this.header.partitions.offset, 
        Padded(
            this._padded, 
            Array(
                this.header.partitions.num_entries, 
                LpMetadataPartition
            )
        )
    ),
    Seek(
        this._header_end + 
        this.header.partitions.entry_size * this.header.partitions.num_entries
    ),
    
    # change "_extents" -> "extents" for show container
    "_extents" / Array(
        this.header.extents.num_entries, 
        LpMetadataExtent
    ),
    "_groups" / Array(
        this.header.groups.num_entries, 
        LpMetadataPartitionGroup
    ),
    "devices" / Pointer(
        this._header_end + this.header.block_devices.offset, 
        Array(
            this.header.block_devices.num_entries, 
            LpMetadataBlockDevice
        )
    ),
)

LpMetaLayout = Struct(
    # Bytes(LP_PARTITION_RESERVED_BYTES),
    "gemometry" / Padded(LP_METADATA_GEOMETRY_SIZE, LpMetadataGeometry),
    "gemometry_backup" / Padded(LP_METADATA_GEOMETRY_SIZE, LpMetadataGeometry),
    # "metadata" / Padded(this.gemometry.metadata_max_size, LpMetaData),
    # "metadata_backup" / Padded(this.gemometry.metadata_max_size, LpMetaData),
    
    # three metadata data is same??
    "metadata" / Array(this.gemometry.metadata_slot_count, Padded(this.gemometry.metadata_max_size, LpMetaData)),
    "metadata_backup" / Array(this.gemometry_backup.metadata_slot_count, Padded(this.gemometry_backup.metadata_max_size, LpMetaData)),
)

def parse_gemometry(gemometry_data):
    gemometry = LpMetadataGeometry.parse(gemometry_data)
    return gemometry

LP_SECTOR_SIZE = 512

def parse_metadata(filename):
    with open(filename, 'rb') as f:
        f.seek(LP_PARTITION_RESERVED_BYTES)
        gemometry = LpMetadataGeometry.parse(f.read(LP_METADATA_GEOMETRY_SIZE))
        gemometry_backup = LpMetadataGeometry.parse(f.read(LP_METADATA_GEOMETRY_SIZE))
        # for i in range(gemometry.metadata_slot_count):
        # only parse first
        metadata = f.read(gemometry.metadata_max_size)
        meta = LpMetaData.parse(metadata)
        # LpMetadataPartition
        for partition in meta.partitions:
            if(partition.num_extents > 0):
                if (partition.name == 'vendor_a'):
                    # LpMetadataExtent
                    extent = partition.extents[0]
                    print("extent:", extent)
                    f.seek(extent.target_data * LP_SECTOR_SIZE)
                    data = f.read(extent.num_sectors * LP_SECTOR_SIZE)
                    with open("vendor.img", "wb") as output:
                        output.write(data)
                    output.close()

        # meta = LpMetaLayout.parse(meta_layout)
    f.close()

if __name__ == "__main__":
    parse_metadata(sys.argv[1])
