参考资料:
* [Construct - 官方文档](http://construct.readthedocs.org/)
* [construct - github](https://github.com/construct/construct)

安装`construct`:
```
$ python3 -m pip install construct
```

准备带有色彩空间的`bmp`文件, 使用`GIMP`, 在"`Image`" -> "`Mode`"中选择"`Index`"模式导出为`bmp`即可.

编写解析脚本:
```
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
    with open("test.bmp", "rb") as f:
        data = f.read()
        bmp = BMP.parse(data)
        print(bmp)
```

执行解析脚本分析测试文件:`test.bmp`
```
$ /usr/bin/python3 parse_bmp.py
Container: 
    header = Container: 
        type = (enum) BMP b'BM'
        size = 140058
        offset = 738
    dip = Container: 
        size = (enum) BITMAPV4HEADER 108
        etc = Container: 
            bWidth = 540
            bHeight = 258
            bPlanes = 1
            bBitCount = 8
            bCompression = (enum) BI_RGB 0
            bSizeImage = 139320
            bXPelsPerMeter = 2835
            bYPelsPerMeter = 2835
            bClrUsed = 154
            bClrImportant = 154
            bRedMask = 0x73524742
            bGreenMask = 0x00000000
            bBlueMask = 0x00000000
            bAlphaMask = 0x00000000
            bCSType = u'' (total 0)
            bEndpoints = hexundump("""
            0000   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
            0010   00 00 00 00 00 00 00 00                           ........
            """)
            
            bGammaRed = 0x00000000
            bGammaGreen = 0x00000000
            bGammaBlue = 0x00000002
    data = hexundump("""
    0000   00 00 00 00 00 00 00 00 00 00 00 00 00 00 E4 00   ................
    0010   06 00 E3 00 00 00 E5 00 00 00 E6 00 07 00 E5 00   ................
    0020   08 00 E6 00 00 04 E7 00 11 00 F1 00 09 04 E7 00   ................
    0030   E4 30 29 00 E5 35 19 00 DD 32 27 00 0A 08 E9 00   .0)..5...2'.....
    0040   E5 31 2B 00 E6 36 1C 00 03 0D DF 00 EE 35 20 00   .1+..6.......5 .
    0050   E6 32 2D 00 EE 31 30 00 E7 37 1F 00 0D 0E DF 00   .2-..10..7......
    0060   E0 34 2C 00 E8 33 2F 00 EF 32 32 00 E1 35 2D 00   .4,..3/..22..5-.
    0070   E9 38 22 00 0B 0D EA 00 E9 34 31 00 EA 38 24 00   .8"......41..8$.
    0080   15 0D EA 00 E2 36 2F 00 0F 11 E0 00 FF 35 2D 00   .....6/......5-.
    0090   EA 35 33 00 EB 39 27 00 E3 37 31 00 DC 35 3B 00   .53..9'..71..5;.
    00A0   E4 34 3E 00 16 10 EB 00 E4 38 33 00 EC 37 36 00   .4>......83..76.
    00B0   E5 3C 28 00 E5 39 35 00 0E 13 EC 00 EE 3C 2D 00   .<(..95......<-.
    00C0   E8 3E 2C 00 D9 3A 3E 00 E1 3C 37 00 FF 37 40 00   .>,..:>..<7..7@.
    00D0   E2 40 2C 00 F1 3E 31 00 1A 19 E3 00 EA 40 30 00   .@,..>1......@0.
    00E0   E3 3E 3A 00 1B 1B E5 00 FF 3E 3C 00 E6 44 34 00   .>:......><..D4.
    00F0   EE 43 37 00 E8 45 35 00 E3 45 41 00 E4 46 43 00   .C7..E5..EA..FC.
    """)
```

另有一个解析`wav`格式文件的练习:
```
#!/usr/bin/python2

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
  with open("D:/Desktop/test.wav", "rb") as f:
    data = f.read()
    header = WAV.parse(data)
    print(header)
    # print("data len: " + hexdump(header.datas, 32))
```