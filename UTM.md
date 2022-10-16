# macOS Monterey通过UTM安装Windows 11

## UTM的安装
前往 https://mac.getutm.app/ 点击“Download”下载UTM，安装UTM。

前往 https://mac.getutm.app/support/ 点击“SPICE Guest Tools and QEMU Drivers (Windows)”下方的“Download”下载Windows支持包：spice-guest-tools-0.164.3.iso

启动UTM，点击“+”创建虚拟机，选择“虚拟化”，选择“Windows”，点击“下载Windows 11 ARM64 开发者预览版景象文件“跳转到：https://www.microsoft.com/en-us/software-download/windowsinsiderpreviewARM64

## 注册Windows账号和Windows Insider，并下载Windows 11 ARM64镜像
登录Windows账号，如果没有需要注册，前往 https://insider.windows.com/zh-cn/getting-started#flight 点击 “立即注册”进行 Insider的注册

回到：https://www.microsoft.com/en-us/software-download/windowsinsiderpreviewARM64 在“Select edition“中选择 “Windows 11 Client Arm64 Insider Preview(Beta Channel) - Build 22598”，点击“Confirm”。

在“Select the product language“中选择“Engilish (Unitied States)"
点击“Confirm”，再次点击“Download Now”，下载得到：Windows11_InsiderPreview_Client_ARM64_en-us_22598.VHDX 文件。

## 创建Windows 11 ARM64 虚拟机
回到UTM，点击“启动VHDX磁盘镜像“下的”浏览“选择 Windows11_InsiderPreview_Client_ARM64_en-us_22598.VHDX 文件，然后点击“下一步“，内存配置为8192MB”，核心数默认为“Default”，点击“下一步”。

在“文件共享”中点击浏览选择要共享目录，点击“下一步”，在总结中为虚拟机命名点击“保存”。

在UTM左侧虚拟机列表中点选创建的Windows虚拟机，在右侧配置窗口中点选“CD/DVD”，然后点击“浏览”，选择：spice-guest-tools-0.164.3.iso 文件，点击运行按钮启动虚拟机。

点击窗口右上角的“编辑选择的虚拟机”按钮，点击“网络”，点选网络模式为“桥接（高级）“

如果启动遇到死机的情况，可关闭虚拟机，并重启UTM再运行一次。

虚拟机启动后，在安装界面出现时按下 Shift + F10，然后在出现的界面点击“Yes“将出现”命令行提示符“窗口，如果弹出”Install a new build of Windows now“，点击”Close“即可。

在命令行提示窗口中输入：`D:`，回车再次输入`spice-guest-tools-0.164.exe` ，将出现“Welcome to SPICE Guest Tools Setup”窗口，点击“Next”，点击“I Agree”开始安装，安装完成后，点击“Finish”重启虚拟机。

然后按照正常安装Windows 10的过程安装即可。

## 关于共享文件
共享文件讲出现在文件管理的“THis PC”中的“Z：”盘符。