#!/usr/bin/python2

from construct import *
import os
import sys

QSB_HEADER_MAGIC = "01030006"

qsb_header = Struct (
  "magic" / Const(bQSB_HEADER_MAGIC, Bytes(8)),
)

if __name__ == '__main__':
  setGlobalPrintFullStrings(False)
  with open(sys.argv[1], "rb") as f:
    data = f.read()
    bootimg = magic.parse(data)
    print(bootimg)