#!/usr/bin/python3

from construct import *
from construct.lib import hexdump

HEADER = Struct(
  "magic" / Const(b"RIFF"),
  "file_size" / Int32ul,
  "file_type" / Const(b"WAVE"),
)

FORMAT = Struct(
  "magic" / Const(b"fmt "),
  "size" / Int32ul,
  "format" / Enum(Int16ul, PCM=1),
  "num_channels" / Int16ul,
  "sample_rate" / Int32ul,
  "byte_rate" / Int32ul,
  "block_align" / Int16ul,
  "bits_per_sample" / Int16ul,
)

DATA = Struct(
  "magic" / Hex(Int32ul),
  "size" / Int32ul,
)


WAV = Struct(
  "header" / HEADER,
  "fmt" / FORMAT,
  "data" / DATA,
  "datas" / Bytes(this.header.file_size - HEADER.sizeof() - FORMAT.sizeof()),
)

if __name__ == '__main__':
  with open("test.wav", "rb") as f:
    data = f.read()
    header = WAV.parse(data)
    print(header)
    # print("data len: " + hexdump(header.datas, 32))