# golang
Android的编译时主要启动golang脚本, 以编译为例:
```
$ . build/envsetup.sh
$ lunch aosp_crosshatch-userdebug
$ m
```

其对应的源码：
```
function _trigger_build()
(
    local -r bc="$1"; shift
    if T="$(gettop)"; then
      _wrap_build "$T/build/soong/soong_ui.bash" --build-mode --${bc} --dir="$(pwd)" "$@"
    else
      echo "Couldn't locate the top of the tree. Try setting TOP."
    fi
)

function m()
(
    _trigger_build "all-modules" "$@"
)
```
可以看到编译的命令为`build/soong/soong_ui.bash --build-mode --all-modules`

该脚本：
```
...
# Save the current PWD for use in soong_ui
export ORIGINAL_PWD=${PWD}
export TOP=$(gettop)
source ${TOP}/build/soong/scripts/microfactory.bash

soong_build_go soong_ui android/soong/cmd/soong_ui

cd ${TOP}
exec "$(getoutdir)/soong_ui" "$@"
```

则执行的命令为：`out/soong_ui --build-mode --all-modules`, 开始调试：
```
(gdb) set args --build-mode --all-modules --dir=.
(gdb) b main.main
Breakpoint 1 at 0x82ab20: file build/soong/cmd/soong_ui/main.go, line 153.
(gdb) r
Starting program: /media/sangfor/vdb/aosp/out/soong_ui --build-mode --all-modules --dir=.
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/x86_64-linux-gnu/libthread_db.so.1".
[New Thread 0x7fffd0cb1700 (LWP 6247)]
...
[New Thread 0x7fffc97fa700 (LWP 6253)]

Thread 1 "soong_ui" hit Breakpoint 1, main.main () at build/soong/cmd/soong_ui/main.go:153
153	func main() {
(gdb) b 289
Breakpoint 2 at 0x82ccb5: file build/soong/cmd/soong_ui/main.go, line 289.
(gdb) c
Continuing.
[New Thread 0x7fffc8ff9700 (LWP 7029)]
...
[Switching to Thread 0x7fffc8ff9700 (LWP 7029)]

Thread 9 "soong_ui" hit Breakpoint 2, main.main () at build/soong/cmd/soong_ui/main.go:289
289		c.run(buildCtx, config, args, logsDir)
(gdb) s
main.runMake (ctx=..., config=..., logsDir=...) at build/soong/cmd/soong_ui/main.go:519
```
可以看到执行了`main.runMak()`:
```
(gdb) b 547
Breakpoint 3 at 0x831af0: file build/soong/cmd/soong_ui/main.go, line 547.
(gdb) c
Continuing.

Thread 9 "soong_ui" hit Breakpoint 3, main.runMake (ctx=..., config=..., logsDir=...) at build/soong/cmd/soong_ui/main.go:547
547		build.Build(ctx, config)
(gdb) s
android/soong/ui/build.Build (ctx=..., config=...) at build/soong/ui/build/build.go:183
183	func Build(ctx Context, config Config) {
```
可以看到执行了`build.Build()`，然后在`runKatiBuild()`下断点:
```
(gdb) b 282
Breakpoint 4 at 0x7d7fa5: file build/soong/ui/build/build.go, line 282.
(gdb) c
Continuing.
build/make/core/soong_config.mk:195: warning: BOARD_PLAT_PUBLIC_SEPOLICY_DIR has been deprecated. Use SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS instead.
build/make/core/soong_config.mk:196: warning: BOARD_PLAT_PRIVATE_SEPOLICY_DIR has been deprecated. Use SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS instead.
============================================
PLATFORM_VERSION_CODENAME=REL
PLATFORM_VERSION=12
TARGET_PRODUCT=aosp_crosshatch
TARGET_BUILD_VARIANT=userdebug
TARGET_BUILD_TYPE=release
TARGET_ARCH=arm64
TARGET_ARCH_VARIANT=armv8-a
TARGET_CPU_VARIANT=generic
TARGET_2ND_ARCH=arm
TARGET_2ND_ARCH_VARIANT=armv8-a
TARGET_2ND_CPU_VARIANT=generic
HOST_ARCH=x86_64
HOST_2ND_ARCH=x86
HOST_OS=linux
HOST_OS_EXTRA=Linux-5.4.0-66-generic-x86_64-Ubuntu-18.04.5-LTS
HOST_CROSS_OS=windows
HOST_CROSS_ARCH=x86
HOST_CROSS_2ND_ARCH=x86_64
HOST_BUILD_TYPE=release
BUILD_ID=SP1A.210812.016.A1
OUT_DIR=out
PRODUCT_SOONG_NAMESPACES=device/google/crosshatch hardware/google/av hardware/google/camera hardware/google/interfaces hardware/google/pixel hardware/qcom/sdm845 vendor/google/camera vendor/qcom/sdm845 vendor/google/interfaces vendor/google_devices/common/proprietary/confirmatioui_hal vendor/google_nos/host/android vendor/google_nos/test/system-test-harness vendor/google_devices/crosshatch/proprietary/hardwareinfo
============================================
[New Thread 0x7fff89db4700 (LWP 24850)]
No need to regenerate ninja file[Switching to Thread 0x7fff89db4700 (LWP 24850)]

Thread 21 "soong_ui" hit Breakpoint 4, android/soong/ui/build.Build (ctx=..., config=...) at build/soong/ui/build/build.go:282
282			runKatiBuild(ctx, config)
```
查看参数ctx：
```
(gdb) set print pretty 
(gdb) p *ctx.ContextImpl
$4 = {
  Context = {
    tab = 0x97cb60 <cancelCtx,context.Context>, 
    data = 0xc0001cc280
  }, 
  Logger = {
    tab = 0x980fc0 <stdLogger,android/soong/ui/logger.Logger>, 
    data = 0xc0001cb110
  }, 
  Metrics = 0xc000152580, 
  Writer = {
    tab = 0x7fffd0488b58, 
    data = 0xc000142d10
  }, 
  Status = 0xc0001cc2c0, 
  Thread = 0, 
  Tracer = {
    tab = 0x97e320 <tracerImpl,android/soong/ui/tracer.Tracer>, 
    data = 0xc0001710a0
  }
}
```
查看参数config：
```
(gdb) p *config.configImpl
$6 = {
  arguments = {
    array = 0x0, 
    len = 0, 
    cap = 0
  }, 
  goma = false, 
  environ = 0xc000137060, 
  distDir = 0xc00012b860 "out/dist", 
  buildDateTime = 0xc00012b970 "1647423767", 
  parallel = 14, 
  keepGoing = 1, 
  verbose = false, 
  checkbuild = false, 
  dist = false, 
  skipConfig = false, 
  skipKati = false, 
  skipKatiNinja = false, 
  skipNinja = false, 
  skipSoongTests = false, 
  katiArgs = {
    array = 0xbc6010 <runtime.zerobase>, 
    len = 0, 
    cap = 0
  }, 
  ninjaArgs = {
    array = 0xc000f6aa90, 
    len = 1, 
    cap = 1
  }, 
  katiSuffix = 0xc007569cf0 "-aosp_crosshatch", 
  targetDevice = 0xc004766031 "crosshatch", 
  targetDeviceDir = 0xc004766050 "device/google/crosshatch/crosshatch", 
  totalRAM = 25220333568, 
  brokenDupRules = true, 
  brokenUsesNetwork = false, 
  brokenNinjaEnvVars = {
    array = 0xbc6010 <runtime.zerobase>, 
    len = 0, 
    cap = 0
  }, 
  pathReplaced = true, 
  useBazel = false, 
  riggedDistDirForBazel = 0xc00012b860 "out/dist", 
  emptyNinjaFile = false
}
```
后续更具实际的情况自行调试即可

# python调试
OTA升级过程中将引用脚本`build/make/tools/releasetools/ota_from_target_files.py`，该脚本在`make otapackage`后执行：`build/make/tools/releasetools/ota_from_target_files.py out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip ota.zip`，调试该脚本应使用命令：`python -m pdb build/make/tools/releasetools/ota_from_target_files.py out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip ota.zip`：
```
$  export PYTHONPATH=$PYTHONPATH:/media/sangfor/vdb/aosp/external/protobuf/python
$ python -m pdb build/make/tools/releasetools/ota_from_target_files.py out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip ota.zip
--- [Output] ----
> /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py(224)<module>()
-> """
(Pdb) b main
Breakpoint 1 at /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py:1201
(Pdb) r
Warning: releasetools script should be invoked as hermetic Python executable -- build and run `ota_from_target_files` directly.
> /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py(1203)main()
-> def option_handler(o, a):
(Pdb) p argv
['out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip', 'ota.zip']
(Pdb) b GenerateAbOtaPackage
Breakpoint 2 at /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py:1043
(Pdb) c
2022-03-16 17:52:38 - common.py - WARNING : Failed to read SYSTEM/etc/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read VENDOR/etc/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read VENDOR/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read ODM/etc/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read ODM/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read VENDOR_DLKM/etc/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read VENDOR_DLKM/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read ODM_DLKM/etc/build.prop
2022-03-16 17:52:38 - common.py - WARNING : Failed to read ODM_DLKM/build.prop
> /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py(1046)GenerateAbOtaPackage()
-> if not OPTIONS.no_signing:
```
通过阅读源码我们知道将调用`Payload.Generate()`生成`payload.bin`, 因此：
```
(Pdb) b Payload.Generate
Breakpoint 3 at /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py:398
(Pdb) c
> /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py(408)Generate()
-> if additional_args is None:
```
在执行`cmd`前：
```
(Pdb) b 422
Breakpoint 4 at /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py:422
(Pdb) c
> /media/sangfor/vdb/aosp/build/make/tools/releasetools/ota_from_target_files.py(422)Generate()
-> self._Run(cmd)
(Pdb) p cmd
['brillo_update_payload', 'generate', '--payload', '/tmp/payload-DoeliI.bin', '--target_image', 'out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip', '--max_timestamp', '1647225546', '--partition_timestamps', u'boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546']
```

因此执行的命令：
```
$ out/host/linux-x86/bin/brillo_update_payload generate --payload /tmp/payload-DoeliI.bin --target_image out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip --max_timestamp 1647225546 --partition_timestamps boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546
```

# bash调试
bash调试可以使用VSCode进行，安装`Bash-Debug`插件， 然后创建`aosp/.vscode/launch.json`：
```
{
    "version": "0.2.0",
    "configurations": [
        {
            "type": "bashdb",
            "request": "launch",
            "name": "Bash-Debug (simplest configuration)",
            "program": "out/host/linux-x86/bin/brillo_update_payload",
            "args": [
                "generate",
                "--payload",
                "/tmp/payload-8g4JbR.bin",
                "--target_image",
                "out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip",
                "--max_timestamp",
                "1647225546",
                "--partition_timestamps",
                "boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546"
            ]
        }
    ]
}
```

为了直接可以调试shell脚本，可能需要对` out/host/linux-x86/bin/brillo_update_payload`其进行一点修改：
```
$ diff system/update_engine/scripts/brillo_update_payload out/host/linux-x86/bin/brillo_update_payload 
95c95,96
<   local my_dir="$(dirname "$(readlink -f "$0")")"
---
>   # local my_dir="$(dirname "$(readlink -f "$0")")"
>   local my_dir="out/host/linux-x86/bin"
352,353c353,354
< trap cleanup_on_error INT TERM ERR
< trap cleanup_on_exit EXIT
---
> # trap cleanup_on_error INT TERM ERR
> # trap cleanup_on_exit EXIT
757d757
<   echo "jms: ${GENERATOR} ${GENERATOR_ARGS[@]}"
946a947
> [[ -x "${GENERATOR}" ]] || GENERATOR="out/host/linux-x86/bin/delta_generator"
```

然后开始调试， 在  758 行下断点继续，在经过如下输出：
```
Extracting images for full update.
Detected .zip file, extracting Brillo image.
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
 extracting: /tmp/TEMP.7TTDuW/META/ab_partitions.txt  
List of A/B partitions for DST_PARTITIONS: system dtbo boot vbmeta product system_ext
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.EgOLYD/META/postinstall_config.txt  
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.AhTGPm/META/dynamic_partitions_info.txt  
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.zc6jfa/META/apex_info.pb  
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.AQiy8U/IMAGES/system.img  Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.sHR4B8/IMAGES/dtbo.img  
Extracted DST_PARTITIONS[dtbo]: 8388608 bytes
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.wNKaDH/IMAGES/boot.img  Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.7RZj0o/IMAGES/vbmeta.img  
```
后， 停止在如下位置：
```
  "${GENERATOR}" "${GENERATOR_ARGS[@]}"
```
`GENERATOR`的值: 
```
GENERATOR="out/host/linux-x86/bin/delta_generator"
```  
`GENERATOR_ARGS`的值:   
```
GENERATOR_ARGS=([0]="--out_file=/tmp/payload-8g4JbR.bin" [1]="--partition_names=system:dtbo:boot:vbmeta:product:system_ext" [2]="--new_partitions=/tmp/system.img.Syeapz:/tmp/dtbo.img.gvu64S:/tmp/boot.img.9xn5Z1:/tmp/vbmeta.img.tjAJA7:/tmp/product.img.JP5pSv:/tmp/system_ext.img.npiygv" [3]="--new_mapfiles=/tmp/system.map.QNC4kJ::::/tmp/product.map.JC7vdP:/tmp/system_ext.map.bl8dJH" [4]="--major_version=2" [5]="--max_timestamp=1647225546" [6]="--partition_timestamps=boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546" [7]="--new_postinstall_config_file=/tmp/postinstall_config.6uszsl" [8]="--dynamic_partition_info_file=/tmp/dynamic_partitions_info.Vhm75y" [9]="--apex_info_file=/tmp/apex_info.YKQF4M")
```

可以看到直径的命令为：
```
$ out/host/linux-x86/bin/delta_generator --out_file=/tmp/payload-8g4JbR.bin --partition_names=system:dtbo:boot:vbmeta:product:system_ext --new_partitions=/tmp/system.img.tYYd1A:/tmp/dtbo.img.QJjHPQ:/tmp/boot.img.bVaETE:/tmp/vbmeta.img.whx32K:/tmp/product.img.EyO6aZ:/tmp/system_ext.img.xhbQWP --new_mapfiles=/tmp/system.map.qFD0sB::::/tmp/product.map.v69qYp:/tmp/system_ext.map.jCXR9C --major_version=2 --max_timestamp=1647225546 --partition_timestamps=boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546 --new_postinstall_config_file=/tmp/postinstall_config.zK65kZ --dynamic_partition_info_file=/tmp/dynamic_partitions_info.Nunjh6 --apex_info_file=/tmp/apex_info.p8E6RZ
```

你也可以直接在命令行下调试：
```
$ /home/ubuntu/.vscode/extensions/rogalmic.bash-debug-0.3.9/bashdb_dir/bashdb --library /home/ubuntu/.vscode/extensions/rogalmic.bash-debug-0.3.9/bashdb_dir -- out/host/linux-x86/bin/brillo_update_payload generate --payload /tmp/payload-8g4JbR.bin --target_image out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip --max_timestamp 1647225546 --partition_timestamps boot\:1647225546\,product\:1647225546\,system\:1647225546\,system_ext\:1647225546
bash debugger, bashdb, release 4.4-0.94-mod

Copyright 2002-2004, 2006-2012, 2014, 2016-2017 Rocky Bernstein
This is free software, covered by the GNU General Public License, and you are
welcome to change it and/or distribute copies of it under certain conditions.

(/media/sangfor/vdb/aosp/out/host/linux-x86/bin/brillo_update_payload:81):
81:	EX_UNSUPPORTED_DELTA=100
bashdb<0> b 758
Breakpoint 1 set in file /media/sangfor/vdb/aosp/out/host/linux-x86/bin/brillo_update_payload, line 758.
bashdb<1> c
Extracting images for full update.
Detected .zip file, extracting Brillo image.
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
 extracting: /tmp/TEMP.khdYc5/META/ab_partitions.txt  
List of A/B partitions for DST_PARTITIONS: system dtbo boot vbmeta product system_ext
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.BFtxJk/META/postinstall_config.txt  
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.WrkmZc/META/dynamic_partitions_info.txt  
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.KICHtd/META/apex_info.pb  
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.RltEXs/IMAGES/system.img  Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.Qmzknt/IMAGES/dtbo.img  
Extracted DST_PARTITIONS[dtbo]: 8388608 bytes
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.zJtWqF/IMAGES/boot.img  Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.ORwxQf/IMAGES/vbmeta.img  
Extracted DST_PARTITIONS[vbmeta]: 8192 bytes

Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.fLxsHU/IMAGES/product.img  Extracted DST_PARTITIONS[boot]: 67108864 bytes
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.T1nWph/IMAGES/system_ext.img  
Converting Android sparse image system_ext.img to RAW.
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.2sbCMX/IMAGES/system_ext.map  
Extracted DST_PARTITIONS[system_ext]: 130408448 bytes

Converting Android sparse image product.img to RAW.
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.CzEyw1/IMAGES/product.map  
Extracted DST_PARTITIONS[product]: 275607552 bytes

Converting Android sparse image system.img to RAW.
Archive:  out/target/product/crosshatch/obj/PACKAGING/target_files_intermediates/aosp_crosshatch-target_files-eng.ubuntu.zip
  inflating: /tmp/TEMP.gXOEP3/IMAGES/system.map  
Extracted DST_PARTITIONS[system]: 834273280 bytes
Generating full update.
Running delta_generator with args: --out_file=/tmp/payload-8g4JbR.bin --partition_names=system:dtbo:boot:vbmeta:product:system_ext --new_partitions=/tmp/system.img.AIxoYb:/tmp/dtbo.img.B2nMUA:/tmp/boot.img.YKYy1D:/tmp/vbmeta.img.rLTwrI:/tmp/product.img.Sn800q:/tmp/system_ext.img.V5lp5M --new_mapfiles=/tmp/system.map.VJt2Ei::::/tmp/product.map.e1ke3R:/tmp/system_ext.map.DBdTjb --major_version=2 --max_timestamp=1647225546 --partition_timestamps=boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546 --new_postinstall_config_file=/tmp/postinstall_config.2MCxKY --dynamic_partition_info_file=/tmp/dynamic_partitions_info.LA3mqR --apex_info_file=/tmp/apex_info.KGjxVp
Breakpoint 1 hit (1 times).
(/media/sangfor/vdb/aosp/out/host/linux-x86/bin/brillo_update_payload:758):
758:	  "${GENERATOR}" "${GENERATOR_ARGS[@]}"
```
此时再查看参数：
```
bashdb<2> print ${GENERATOR}
/media/sangfor/vdb/aosp/out/soong/host/linux-x86/bin/delta_generator
bashdb<3> print ${GENERATOR_ARGS[@]}
--out_file=/tmp/payload-8g4JbR.bin --partition_names=system:dtbo:boot:vbmeta:product:system_ext --new_partitions=/tmp/system.img.AIxoYb:/tmp/dtbo.img.B2nMUA:/tmp/boot.img.YKYy1D:/tmp/vbmeta.img.rLTwrI:/tmp/product.img.Sn800q:/tmp/system_ext.img.V5lp5M --new_mapfiles=/tmp/system.map.VJt2Ei::::/tmp/product.map.e1ke3R:/tmp/system_ext.map.DBdTjb --major_version=2 --max_timestamp=1647225546 --partition_timestamps=boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546 --new_postinstall_config_file=/tmp/postinstall_config.2MCxKY --dynamic_partition_info_file=/tmp/dynamic_partitions_info.LA3mqR --apex_info_file=/tmp/apex_info.KGjxVp

```

# c/c++调试
接下来，我们使用gdb调试c/c++代码：
```
$ gdb out/host/linux-x86/bin/delta_generator
---- [Output] ----
...s
(gdb) set args --out_file=/tmp/payload-8g4JbR.bin --partition_names=system:dtbo:boot:vbmeta:product:system_ext --new_partitions=/tmp/system.img.tYYd1A:/tmp/dtbo.img.QJjHPQ:/tmp/boot.img.bVaETE:/tmp/vbmeta.img.whx32K:/tmp/product.img.EyO6aZ:/tmp/system_ext.img.xhbQWP --new_mapfiles=/tmp/system.map.qFD0sB::::/tmp/product.map.v69qYp:/tmp/system_ext.map.jCXR9C --major_version=2 --max_timestamp=1647225546 --partition_timestamps=boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546 --new_postinstall_config_file=/tmp/postinstall_config.zK65kZ --dynamic_partition_info_file=/tmp/dynamic_partitions_info.Nunjh6 --apex_info_file=/tmp/apex_info.p8E6RZ
(gdb) b main
Breakpoint 1 at 0xc19f0: file system/update_engine/payload_generator/generate_delta_main.cc, line 729.
(gdb) r
Starting program: /media/sangfor/vdb/aosp/out/host/linux-x86/bin/delta_generator --out_file=/tmp/payload-8g4JbR.bin --partition_names=system:dtbo:boot:vbmeta:product:system_ext --new_partitions=/tmp/system.img.tYYd1A:/tmp/dtbo.img.QJjHPQ:/tmp/boot.img.bVaETE:/tmp/vbmeta.img.whx32K:/tmp/product.img.EyO6aZ:/tmp/system_ext.img.xhbQWP --new_mapfiles=/tmp/system.map.qFD0sB::::/tmp/product.map.v69qYp:/tmp/system_ext.map.jCXR9C --major_version=2 --max_timestamp=1647225546 --partition_timestamps=boot:1647225546,product:1647225546,system:1647225546,system_ext:1647225546 --new_postinstall_config_file=/tmp/postinstall_config.zK65kZ --dynamic_partition_info_file=/tmp/dynamic_partitions_info.Nunjh6 --apex_info_file=/tmp/apex_info.p8E6RZ
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/x86_64-linux-gnu/libthread_db.so.1".

Breakpoint 1, main (argc=11, argv=0x7fffffffcc98) at system/update_engine/payload_generator/generate_delta_main.cc:729
729	  return chromeos_update_engine::Main(argc, argv);

(gdb) p argv[0]
$2 = 0x7fffffffd142 "/media/sangfor/vdb/aosp/out/host/linux-x86/bin/delta_generator"
```

接下来就是对`delta_generator`的调试了