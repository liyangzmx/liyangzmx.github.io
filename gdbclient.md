# 参考资料
[使用调试程序](https://source.android.google.cn/devices/tech/debug/gdb?hl=zh-cn)

# 准备代码和ROM
## 分支确定
在[源代码标记和 build](https://source.android.com/setup/start/build-numbers#source-code-tags-and-builds)中可查得`Pixel 3 XL`可以支持的最新Android Build为:`SP1A.210812.016.A1`, 对应的分支: `android-12.0.0_r3	`.

在[Driver Binaries for Nexus and Pixel Devices](https://developers.google.com/android/drivers/)中可以找到对应的驱动为:[Pixel 3 XL binaries for Android 12.0.0 (SP1A.210812.016.A1)](https://developers.google.com/android/drivers/#crosshatchsp1a.210812.016.a1)

## 准备代码
```
$ mkdir -p ~/bin/
$ mkdir ~/work/aosp/
$ cd ~/work/aosp/
$ repo init -u https://mirrors.tuna.tsinghua.edu.cn/git/AOSP/platform/manifest -b android-12.0.0_r3
$ repo sync
```

## 下载驱动并解压
```
$ cd ~/Downloads
$ tar xvf qcom-crosshatch-*.tgz
$ tar xvf google_devices-crosshatch-*.tgz
$ cd ~/work/aosp/
$ ~/Downloads/extract-qcom-crosshatch.sh
$ ~/Downloads/extract-google_devices-crosshatch.sh
```

## 编译固件
```
$ source build/envsetup.sh
$ lunch aosp_crosshatch-userdebug
$ m
```

# 刷写固件
## 配置adb
```
$ sudo usermod -aG plugdev $LOGNAME
$ apt-get install android-sdk-platform-tools-common
```
重新插拔USB, 然后手机选择总是信任当前已经连接的计算机.

## 刷写固件
```
$ adb reboot bootloader
$ fastboot flashall -w
```
等待设备刷写完成.

# 使用gdb调试cameraserver
## 基本步骤
```
$ adb root
$ gdbclient.py -n cameraserver
Redirecting gdbserver output to /tmp/gdbclient.log

GNU gdb (GDB) 8.3
Copyright (C) 2019 Free Software Foundation, Inc.
... ...
Find the GDB manual and other documentation resources online at:
    <http://www.gnu.org/software/gdb/documentation/>.

For help, type "help".
Type "apropos word" to search for commands related to "word".
__ioctl () at out/soong/.intermediates/bionic/libc/syscalls-arm.S/gen/syscalls-arm.S:850
850	    swi     #0
```

## 打断点调试
```
(gdb) b CameraProviderManager::openSession
Breakpoint 1 at 0xed4c7f1a: CameraProviderManager::openSession. (3 locations)
(gdb) c
Continuing.
[New Thread 10170.11808]
[Switching to Thread 10170.10286]
```

## 打开相机APP验证断点
```
Thread 6 "Binder:10170_3" hit Breakpoint 1, android::CameraProviderManager::openSession (this=0xeab00590, id=..., callback=..., session=0xe9d7bb4c)
    at frameworks/av/services/camera/libcameraservice/common/CameraProviderManager.cpp:379
379	    std::lock_guard<std::mutex> lock(mInterfaceMutex);
```

## 查看堆栈
```
(gdb) bt
#0  android::CameraProviderManager::openSession (this=0xeab00590, id=..., callback=..., session=0xe9d7bb4c)
    at frameworks/av/services/camera/libcameraservice/common/CameraProviderManager.cpp:379
#1  0xed51bd12 in android::Camera3Device::initialize (this=0xedc05c80, manager=..., monitorTags=...)
    at frameworks/av/services/camera/libcameraservice/device3/Camera3Device.cpp:123
#2  0xed4c5786 in android::Camera2ClientBase<android::CameraDeviceClientBase>::initializeImpl<android::sp<android::CameraProviderManager> > (
    this=0xeaa404d0, providerPtr=..., monitorTags=...) at frameworks/av/services/camera/libcameraservice/common/Camera2ClientBase.cpp:107
#3  0xed4c56f0 in android::Camera2ClientBase<android::CameraDeviceClientBase>::initialize (this=0xaa716, manager=..., monitorTags=...)
    at frameworks/av/services/camera/libcameraservice/common/Camera2ClientBase.cpp:83
#4  ... ...
... ...
```

# 使用VSCode调试cameraserver
## 导出配置到VSCode
执行:
```
$ gdbclient.py --setup-forwarding vscode -n cameraserver
Redirecting gdbserver output to /tmp/gdbclient.log

{
    "miDebuggerPath": "/home/nickli/work/aosp/prebuilts/gdb/linux-x86/bin/gdb", 
    "program": "/home/nickli/work/aosp/out/target/product/crosshatch/symbols/system/bin/cameraserver", 
    "setupCommands": [
        {
            ... ...
        }
    ]
}
... ...
```

将导出的配置(`{}`中的部分)粘贴到`~/work/aosp/.vscode/launch.json`的如下位置:
```
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            <粘贴到此处>
        }
    ]
}
```

使用vscode打开`~/work/aosp`目录, 然后打开`frameworks/av/services/camera/libcameraservice/common/CameraProviderManager.cpp`文件在:  
```
status_t CameraProviderManager::openSession(const std::string &id,
        const sp<device::V1_0::ICameraDeviceCallback>& callback,
        /*out*/
        sp<device::V1_0::ICameraDevice> *session)
```
内下断点, 然后点击"Run" -> "Start Debugging"

# 使用lldb调试cameraserver
## VSCode插件安装
安装[CodeLLDB 扩展程序](https://marketplace.visualstudio.com/items?itemName=vadimcn.vscode-lldb)插件

## 命令
执行:
```
$ gdbclient.py -n cameraserver --setup-forwarding vscode-lldb
gdb is deprecated in favor of lldb. If you can't use lldb, please set --no-lldb and file a bug asap.
Redirecting lldb-server output to /tmp/lldb-client.log

{
    "initCommands": [
        ... ....
    ], 
    "targetCreateCommands": [
        "target create /home/nickli/work/aosp/out/target/product/crosshatch/symbols/system/bin/cameraserver", 
        "target modules search-paths add / /home/nickli/work/aosp/out/target/product/crosshatch/symbols/"
    ], 
    "sourceMap": {
        "": "/home/nickli/work/aosp", 
        "/b/f/w": "/home/nickli/work/aosp", 
        ".": "/home/nickli/work/aosp"
    }, 
    "processCreateCommands": [
        "gdb-remote 5039"
    ], 
    "name": "(lldbclient.py) Attach cameraserver (port: 5039)", 
    "relativePathBase": "/home/nickli/work/aosp", 
    "request": "custom", 
    "type": "lldb"
}


Paste the above json into .vscode/launch.json and start the debugger as
normal. Press enter in this terminal once debugging is finished to shutdown
the gdbserver and close all the ports.

Press enter to shutdown gdbserver

```

如上文gdb一样对VSCode进行配置即可.

# 使用jdb对Camera2 App进行调试
1. 依次转到设置 > 开发者选项 > 选择调试应用, 并从列表中选择您的应用, (例如:`Camera`), 然后点击等待调试程序.
2. 启动应用. 您可以从启动器启动, 也可以在命令行中运行以下命令来启动:
```
adb shell am start -a android.intent.action.MAIN -n APP_NAME/.APP_ACTIVITY
```
例如:
```
adb shell am start -a android.intent.action.MAIN -n com.android.camera2/com.android.camera.CameraActivity
```

然后执行 :
```
$ adb shell ps -ef | grep camera2
u0_a72       21454  1028 0 21:10:53 ?     00:00:00 com.android.camera2
$ gdbclient.py -p 21454
gdb is deprecated in favor of lldb. If you can't use lldb, please set --no-lldb and file a bug asap.
Redirecting lldb-server output to /tmp/lldb-client.log

(lldb) command source -s 0 '/tmp/tmpVjvVHE'
Executing commands in '/tmp/tmpVjvVHE'.
... ...
Cannot read termcap database;
using dumb terminal settings.
(lldb) c
```
注意上述输出中的进程ID: `21454`很重要, 下文也要用

然后新打开一个终端执行:
```
$ adb forward tcp:12345 jdwp:21454
$ jdb -attach localhost:12345
Set uncaught java.lang.Throwable
Set deferred uncaught java.lang.Throwable
Initializing jdb ...
> stop in com.android.camera.CameraActivity.onCreateTasks
Set breakpoint com.android.camera.CameraActivity.onCreateTa
... ...
```

此时在`Camera2`启动界面返回并重新进入可以看到:
```
> 
Breakpoint hit: "thread=main", com.android.camera.CameraActivity.onCreateTasks(), line=1,432 bci=2

main[1] where
  [1] com.android.camera.CameraActivity.onCreateTasks (CameraActivity.java:1,432)
  [2] com.android.camera.util.QuickActivity.onCreate (QuickActivity.java:114)
  [3] android.app.Activity.performCreate (Activity.java:8,051)
  [4] android.app.Activity.performCreate (Activity.java:8,031)
  [5] android.app.Instrumentation.callActivityOnCreate (Instrumentation.java:1,329)
  [6] android.app.ActivityThread.performLaunchActivity (ActivityThread.java:3,612)
  [7] android.app.ActivityThread.handleLaunchActivity (ActivityThread.java:3,796)
  [8] android.app.servertransaction.LaunchActivityItem.execute (LaunchActivityItem.java:103)
  [9] android.app.servertransaction.TransactionExecutor.executeCallbacks (TransactionExecutor.java:135)
  [10] android.app.servertransaction.TransactionExecutor.execute (TransactionExecutor.java:95)
  [11] android.app.ActivityThread$H.handleMessage (ActivityThread.java:2,214)
  [12] android.os.Handler.dispatchMessage (Handler.java:106)
  [13] android.os.Looper.loopOnce (Looper.java:201)
  [14] android.os.Looper.loop (Looper.java:288)
  [15] android.app.ActivityThread.main (ActivityThread.java:7,842)
  [16] java.lang.reflect.Method.invoke (native method)
  [17] com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run (RuntimeInit.java:548)
  [18] com.android.internal.os.ZygoteInit.main (ZygoteInit.java:1,003)
```
可以看到程序成功停止在:`com.android.camera.CameraActivity.onCreateTasks()`断点处.