#!/usr/bin/python2

from construct import *

BMP_HEADER = Struct(
    "type" / Enum(Bytes(2), 
                BMP = b"BM", 
                OS2_BMP = b"BA",
                OS2_COLOR_ICON = b"CI",
                OS2_COLOR_POINTER = b"CP",
                OS2_ICON = "IC",
                OS2_POINTER = "PT"
            ),
    "size" / Int32ul,
    Padding(4),
    "offset" / Int32ul,
)

BITMAPCOREHEADER = Struct(
    "bWidth" / Int16ul,
    "bHeight" / Int16ul,
    "bPlanes" / Const(1, Int16ul),
    "bBitCount" / Int16ul,
)

BITMAPINFOHEADER = Struct(
    "bWidth" / Int32ul,
    "bHeight" / Int32ul,
    "bPlanes" / Const(1, Int16ul),
    "bBitCount" / Int16ul,
    "bCompression" / Enum(Int32ul, 
                BI_RGB = 0, 
                BI_RLE8 = 1,
                BI_RLE4 = 2,
                BI_BITFIELDS = 3, 
                BI_JPEG = 4, 
                BI_PNG = 5, 
                BI_ALPHABITFIELDS = 6, 
                BI_CMYK = 11, 
                BI_CMYKRLE8 = 12, 
                BI_CMYKRLE4 = 13
            ),
    "bSizeImage" / Int32ul,
    "bXPelsPerMeter" / Int32ul, 
    "bYPelsPerMeter" / Int32ul, 
    "bClrUsed" / Int32ul, 
    "bClrImportant" / Int32ul
)

BITMAPINFOHEADER2 = Struct(
    "units" / Const(0, Int16ul), 
    Padding(2), 
    "direction" / Const(0, Int16ul), 
    "halftoning_algorithm" / Int16ul, 
    "halftoning_param0" / Int32ul, 
    "halftoning_param1" / Int32ul, 
    "color_encoding" / Int32ul, 
    "identifier" / Int32ul, 
)

BITMAPV3HEADER = Struct(
    "bWidth" / Int32ul,
    "bHeight" / Int32ul,
    "bPlanes" / Const(1, Int16ul),
    "bBitCount" / Int16ul,
    "bCompression" / Enum(Int32ul, 
                BI_RGB = 0, 
                BI_RLE8 = 1,
                BI_RLE4 = 2,
                BI_BITFIELDS = 3, 
                BI_JPEG = 4, 
                BI_PNG = 5, 
                BI_ALPHABITFIELDS = 6, 
                BI_CMYK = 11, 
                BI_CMYKRLE8 = 12, 
                BI_CMYKRLE4 = 13
            ),
    "bSizeImage" / Int32ul,
    "bXPelsPerMeter" / Int32ul, 
    "bYPelsPerMeter" / Int32ul, 
    "bClrUsed" / Int32ul, 
    "bClrImportant" / Int32ul, 
    "bRedMask" / Hex(Int32ul), 
    "bGreenMask" / Hex(Int32ul), 
    "bBlueMask" / Hex(Int32ul),
    "bAlphaMask" / Hex(Int32ul),
)

BITMAPV4HEADER = Struct(
    "bWidth" / Int32ul,
    "bHeight" / Int32ul,
    "bPlanes" / Const(1, Int16ul),
    "bBitCount" / Int16ul,
    "bCompression" / Enum(Int32ul, 
                BI_RGB = 0, 
                BI_RLE8 = 1,
                BI_RLE4 = 2,
                BI_BITFIELDS = 3, 
                BI_JPEG = 4, 
                BI_PNG = 5, 
                BI_ALPHABITFIELDS = 6, 
                BI_CMYK = 11, 
                BI_CMYKRLE8 = 12, 
                BI_CMYKRLE4 = 13
            ),
    "bSizeImage" / Int32ul,
    "bXPelsPerMeter" / Int32ul, 
    "bYPelsPerMeter" / Int32ul, 
    "bClrUsed" / Int32ul, 
    "bClrImportant" / Int32ul, 
    "bRedMask" / Hex(Int32ul),
    "bGreenMask" / Hex(Int32ul), 
    "bBlueMask" / Hex(Int32ul),
    "bAlphaMask" / Hex(Int32ul),
    "bCSType" / PaddedString(4, "ascii"), 
    "bEndpoints" / HexDump(Bytes(24)), 
    "bGammaRed" / Hex(Int32ul),
    "bGammaGreen" / Hex(Int32ul),
    "bGammaBlue" / Hex(Int32ul),
)

BITMAPV5HEADER = Struct(
    "bWidth" / Int32ul,
    "bHeight" / Int32ul,
    "bPlanes" / Const(1, Int16ul),
    "bBitCount" / Int16ul,
    "bCompression" / Enum(Int32ul, 
                BI_RGB = 0, 
                BI_RLE8 = 1,
                BI_RLE4 = 2,
                BI_BITFIELDS = 3, 
                BI_JPEG = 4, 
                BI_PNG = 5, 
                BI_ALPHABITFIELDS = 6, 
                BI_CMYK = 11, 
                BI_CMYKRLE8 = 12, 
                BI_CMYKRLE4 = 13
            ),
    "bSizeImage" / Int32ul,
    "bXPelsPerMeter" / Int32ul, 
    "bYPelsPerMeter" / Int32ul, 
    "bClrUsed" / Int32ul, 
    "bClrImportant" / Int32ul, 
    "bRedMask" / Hex(Int32ul), 
    "bGreenMask" / Hex(Int32ul), 
    "bBlueMask" / Hex(Int32ul),
    "bAlphaMask" / Hex(Int32ul),
    "bCSType" / PaddedString(4, "ascii"),
    "bEndpoints" / HexDump(Bytes(24)), 
    "bGammaRed" / Hex(Int32ul),
    "bGammaGreen" / Hex(Int32ul),
    "bGammaBlue" / Hex(Int32ul),
    "bIntent" / Hex(Int32ul), 
    "bProfileData" / Hex(Int32ul), 
    "bProfileSize" / Hex(Int32ul), 
    "bReserved" / Hex(Int32ul), 
)

DIP = Struct (
    "size" / Enum(Int32ul, 
                BITMAPCOREHEADER = 12,
                BITMAPINFOHEADER = 40,
                BITMAPV3HEADER = 56, 
                BITMAPV4HEADER = 108, 
                BITMAPV5HEADER = 124, 
            ),
    "etc" / Switch(this.size, {
                    "BITMAPCOREHEADER" : BITMAPCOREHEADER,
                    "BITMAPINFOHEADER" : BITMAPINFOHEADER, 
                    "BITMAPV3HEADER" : BITMAPV3HEADER,
                    "BITMAPV4HEADER" : BITMAPV4HEADER, 
                    "BITMAPV5HEADER" : BITMAPV5HEADER, 
                }
            )
)

BMP = Struct(
    "header" / BMP_HEADER,
    "dip" / DIP, 
    "data" / Switch(this.dip.size, {
                    "BITMAPV4HEADER" : HexDump(Bytes(256))
                } 
            )
)

if __name__ == '__main__':
    with open("baidu.bmp", "rb") as f:
        data = f.read()
        bmp = BMP.parse(data)
        print(bmp)