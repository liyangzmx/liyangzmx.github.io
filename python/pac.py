#!/usr/bin/python2

from construct import *
import os
import sys

QSB_HEADER_MAGIC = b"01030006"
INFOSIZE = 256

qsb_header = Struct (
  "magic" / Const(QSB_HEADER_MAGIC, Bytes(8)),
  "checksum" / Hex(Int32ul),
  "filesize" / Int32ul,
  "author" / PaddedString(32, "ascii"),
  "version" / PaddedString(32, "ascii"),
  "timestamp" / Int32ul,
  "imagecount" / Int32ul,
)

qsb_images = Struct (
  "filename" / PaddedString(64, "ascii"),
  "partname" / PaddedString(32, "ascii"),
  "checksum" / Int32ul,
  "timestamp" / Int32ul,
  "imageoffset" / Int32ul,
  "eraseflag" / Hex(Int32ul),
  "writeflag" / Hex(Int32ul),
  "imagesectors" / Int32ul,
  "imagestartsectors" / Int32ul,
)

qsb_img = Struct (
  "qsb_header" / Padded(INFOSIZE, qsb_header),
  "qsb_images" / Array(this.qsb_header.imagecount, Padded(INFOSIZE, qsb_images)),
)

SIZEOF_PAC_HEADER = 2124
SIZEOF_FILE_T = 2580

PacHeaderInfo = Struct (
  "szVersion" / PaddedString(44, "utf16"),
  "dwHiSize" / Int32ul,
  "dwLoSize" / Int32ul,
  "szPrdName" / PaddedString(512, "utf16"),
  "szPrdVersion" / PaddedString(512, "utf16"),
  "nFileCount" / Int32ul,
  "dwFileOffset" / Int32ul,
  "dwMode" / Hex(Int32ul),
  "dwFlashType" / Int32ul,
  "dwNandStrategy" / Int32ul,
  "dwIsNvBackup" / Int32ul,
  "dwNandPageType" / Int32ul,
  "szPrdAlias" / PaddedString(200, "utf16"),
  "dwOmaDmProductFlag" / Int32ul,
  "dwIsOmaDM" / Int32ul,
  "dwIsPreload" / Int32ul,
  "wCRC1" / Int16ul,
  "wCRC2" / Int16ul,
)

FileInfo = Struct(
  "dwSize" / Int32ul,
  "szFileID" / PaddedString(512, "utf16"),
  "fileName" / PaddedString(512, "utf16"),
  "szFileVersion" / PaddedString(504, "utf16"),
  "_dwHiFileSize" / Int32ul,
  "_dwHiDataOffset" / Int32ul,
  "_dwLoFileSize" / Int32ul,
  "dwFileSize" / Computed(this._dwHiFileSize * 65536 + this._dwLoFileSize),
  "nFileFlag" / Hex(Int32ul),
  "nCheckFlag" / Hex(Int32ul),
  "_dwLoDataOffset" / Int32ul,
  "dwDataOffset" / Hex(Computed(this._dwHiDataOffset * 65536 + this._dwLoDataOffset)),
  "swCanOmitFlag" / Hex(Int32ul),
  "dwAddrNum" / Int32ul,
)

PacImage = Struct (
  "pac_header" / Padded(SIZEOF_PAC_HEADER, PacHeaderInfo),
  "files" / Array(this.pac_header.nFileCount, Padded(SIZEOF_FILE_T, FileInfo)),
)

if __name__ == '__main__':
  setGlobalPrintFullStrings(False)
  with open(sys.argv[1], "rb") as f:
    data = f.read(1024 * 1024)
    bootimg = PacImage.parse(data)
    print(bootimg)