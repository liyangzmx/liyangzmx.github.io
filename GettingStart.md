- [Getting Start (M1 MacBook Pro)](#getting-start-m1-macbook-pro)
  - [Homebrew](#homebrew)
  - [vim 使用与配置](#vim-使用与配置)
  - [浏览器](#浏览器)
  - [VSCode](#vscode)
  - [Windows虚拟机](#windows虚拟机)
    - [VirtualBox 安装 Windows 11(x86/x64)](#virtualbox-安装-windows-11x86x64)
    - [UTM 安装Windows 11 ARM64](#utm-安装windows-11-arm64)
  - [**其它 PC** 上安装Ubuntu Desktop(x86/x64)](#其它-pc-上安装ubuntu-desktopx86x64)
  - [Ubuntu 配置源](#ubuntu-配置源)
  - [Git配置与使用](#git配置与使用)
- [学习](#学习)
  - [在线图书](#在线图书)
  - [OpenGL](#opengl)

# Getting Start (M1 MacBook Pro)
## Homebrew
[Homebrew](https://brew.sh/index_zh-cn)是非常重要的工具，其安装参考官网，非常简答。

Homebrew的国内镜像：
* [Homebrew 源使用帮助 - USTC](https://mirrors.ustc.edu.cn/help/brew.git.html)
* [Homebrew / Linuxbrew 镜像使用帮助](https://mirrors.tuna.tsinghua.edu.cn/help/homebrew/)

## vim 使用与配置
[vim](https://www.vim.org)有一个官网推荐的中文翻译手册：[Vimcdoc](https://vimcdoc.sourceforge.net)，其余的翻译版本可以从：[Vim in non-English languages](https://www.vim.org/translations.php) 找到。

## 浏览器
没啥好选择的，只有 [Chrome](https://www.google.cn/intl/zh-CN/chrome/)

## VSCode
官方的下载地址：https://code.visualstudio.com/Download

如果太慢，将下载链接中的“****.vo.msecnd.net”替换成“vscode.cdn.azure.cn”即可。

推荐的插件：[PlantUML](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)，可以用来画 [时序图](https://plantuml.com/zh/sequence-diagram)

## Windows虚拟机
如果Mac是Intel的芯片，则推荐的**免费**虚拟机：**[VirtualBox](https://www.virtualbox.org)**

如果Mac是M1(pro|ultra)的芯片，则推荐**免费**的虚拟机：**[UTM](https://mac.getutm.app)**

### VirtualBox 安装 Windows 11(x86/x64)
Virtualbox使用ISO方式安装虚拟机，且 VirtualBox **不支持** M1 系列芯片。

Windows 11 X86/X64的ISO镜像可以从 [下载 Windows 11](https://www.microsoft.com/zh-cn/software-download/windows11) 下载到。

VirtualBox可以从官网 [Download VirtualBox](https://www.virtualbox.org/wiki/Downloads) 下载到.

如何安装/使用 VirtualBox 创建/配置虚拟机可以参考：https://www.virtualbox.org/manual/UserManual.html

**获取 Ubuntu Desktop(x86/x64)**
以下地址为国内镜像：
* https://mirrors.ustc.edu.cn/ubuntu-releases/
* https://mirrors.ustc.edu.cn/ubuntu-releases/
* https://developer.aliyun.com/mirror/

**如何安装Ubuntu Desktop(x86/x64)？**
[Install Ubuntu desktop](https://ubuntu.com/tutorials/install-ubuntu-desktop#1-overview)

<!-- 有些厂商也提供了Ubuntu在对应机器上的安装指南，主要是BIOS的部分值得参考：
* [Ubuntu 22.04 Linux Setup Guide - For ThinkStation P360 Tower](https://download.lenovo.com/pccbbs/thinkcentre_pdf/ts_p360_ubuntu_22.04_lts_installation_guide.pdf)
* [如何在 Dell PC 上安装 Ubuntu Linux](https://www.dell.com/support/kbdoc/zh-cn/000131655/如何在-dell-pc-上安装-ubuntu-linux) -->


### UTM 安装Windows 11 ARM64
UTM基于qemu，它支持采用虚拟化技术或者模拟器技术创建虚拟机，**Windows 11 ARM64可以运行X86/X64应用程序**

**UTM的安装**

前往 https://mac.getutm.app/ 点击“Download”下载UTM，安装UTM。

前往 https://mac.getutm.app/support/ 点击“SPICE Guest Tools and QEMU Drivers (Windows)”下方的“Download”下载Windows支持包：spice-guest-tools-0.164.3.iso

启动UTM，点击“+”创建虚拟机，选择“虚拟化”，选择“Windows”，点击“下载Windows 11 ARM64 开发者预览版景象文件“跳转到：https://www.microsoft.com/en-us/software-download/windowsinsiderpreviewARM64

**创建Windows 11 ARM64 虚拟机**

回到UTM，点击“启动VHDX磁盘镜像“下的”浏览“选择 Windows11_InsiderPreview_Client_ARM64_en-us_22598.VHDX 文件，然后点击“下一步“，内存配置为8192MB”，核心数默认为“Default”，点击“下一步”。

在“文件共享”中点击浏览选择要共享目录，点击“下一步”，在总结中为虚拟机命名点击“保存”。

在UTM左侧虚拟机列表中点选创建的Windows虚拟机，在右侧配置窗口中点选“CD/DVD”，然后点击“浏览”，选择：spice-guest-tools-0.164.3.iso 文件，点击运行按钮启动虚拟机。

点击窗口右上角的“编辑选择的虚拟机”按钮，点击“网络”，点选网络模式为“桥接（高级）“

如果启动遇到死机的情况，可关闭虚拟机，并重启UTM再运行一次。

虚拟机启动后，在安装界面出现时按下 Shift + F10，然后在出现的界面点击“Yes“将出现”命令行提示符“窗口，如果弹出”Install a new build of Windows now“，点击”Close“即可。

在命令行提示窗口中输入：`D:`，回车再次输入`spice-guest-tools-0.164.exe` ，将出现“Welcome to SPICE Guest Tools Setup”窗口，点击“Next”，点击“I Agree”开始安装，安装完成后，点击“Finish”重启虚拟机。

然后按照正常安装Windows 10的过程安装即可。

共享文件讲出现在文件管理的“THis PC”中的“Z：”盘符。

## **其它 PC** 上安装Ubuntu Desktop(x86/x64)
**获取 Ubuntu Desktop(x86/x64)**
以下地址为国内镜像：
* https://mirrors.ustc.edu.cn/ubuntu-releases/
* https://mirrors.ustc.edu.cn/ubuntu-releases/
* https://developer.aliyun.com/mirror/

**创建Ubuntu安装盘**

下载完成后如何在Windows上制作安装U盘？这里使用了一款叫 [balenaEtcher](https://www.balena.io/etcher/) 的工具，它可以完成这项工作。

当然官方推荐的 [Create a bootable USB stick with Rufus on Windows](https://ubuntu.com/tutorials/create-a-usb-stick-on-windows#1-overview) 也不错。

如果你想在Ubuntu上创建一个启动盘，那更简单了：[Create a bootable USB stick on Ubuntu](https://ubuntu.com/tutorials/create-a-usb-stick-on-ubuntu)

## Ubuntu 配置源

安装好Ubunut后如何配置软件包的安装源来加快apt-get的速度？
可以参考 [Ubuntu 源使用帮助 - USTC](https://mirrors.ustc.edu.cn/help/ubuntu.html) 或者 [Ubuntu 镜像使用帮助 - TUNA](https://mirrors.tuna.tsinghua.edu.cn/help/git-repo/) 或者 [Ubuntu 镜像 - 阿里云](https://developer.aliyun.com/mirror/ubuntu?spm=a2c6h.13651102.0.0.3e221b11djhd2b)

## Git配置与使用
一切都那么美好，开始拉代码了，需要使用Git([起步 - Git 是什么？](https://git-scm.com/book/zh/v2/起步-Git-是什么？))，如何在Ubuntu下安装Git？参考：[起步-安装-Git](https://git-scm.com/book/zh/v2/起步-安装-Git)

安装好git需要进行基础的用户名、邮箱、默认提交消息的编辑器等配置，如何进行？参考：[自定义-Git-配置-Git](https://git-scm.com/book/zh/v2/自定义-Git-配置-Git)

配置好git如何想Git服务器提供SSH公钥？参考：[服务器上的 Git - 生成 SSH 公钥](https://git-scm.com/book/zh/v2/服务器上的-Git-生成-SSH-公钥)

如何正确的使用Git？参考：[Git Book (在线)](https://git-scm.com/book/zh/v2)，你也可以直接下载电子书：[Pro Git (PDF)](https://github.com/progit/progit2-zh/releases/download/2.1.62/progit.pdf)

拉好代码，是否有好用的图形界面工具？推荐：Gitk，有一些命令行参数在：[gitk - The Git repository browser](https://git-scm.com/docs/gitk)

# 学习
## 在线图书
* [Z-Library](http://z-lib.org/)
* [Z-Library - Books](https://zh.b-ok.asia/)

## OpenGL
[LearnOpenGL CN](https://learnopengl-cn.github.io) 是一个在线学习OpenGL的书籍