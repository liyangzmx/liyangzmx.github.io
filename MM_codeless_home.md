# MediaPlayer
## 初始化
`MediaPlayer`(Java)对象有自己的本地方法, 其位于`frameworks/base/media/jni/android_media_MediaPlayer.cpp`中, 这些方法均以`android_media_MediaPlayer_`开头, 因此"native_init"对应`android_media_MediaPlayer_native_setup()`.

`MediaPlayer`在构造时会做两件事情:
* 在加载`libmedia_jni.so`并执行`native_init`, 这个步骤只获取`MediaPlayer`类相关的一些信息, 并不会初始化 C++ 对象
* 调用其native方法`native_setup`, 这个步骤负责实例化一个`MediaPlayer`(C++)类, 并生成一个集成自`MediaPlayerListener`的`JNIMediaPlayerListener`用于监听来自播放器的消息. 新创建的`MediaPlayer`(C++)对象将被保存在`MediaPlayer`(Java)的`mNativeContext`中用于后续的下行调用.

`MediaPlayer`的初始化比较简单, 只有设置数据源之后才能开始数据源/解码/渲染等的工作.

## 设置数据源
数据源头在 Android Multimedia中主要以`IMediaSource`, 和`MediaSource`不同. 该类别通常针对一个具体的类型, 比如一个符合`VP9`编码规范的数据源, 从该数据源读取的数据应是编码过的数据.  
通常一个媒体文件中会包含很多个部分:
* 视频: 通常是指定的编码格式, 如: `VP9`
* 音频: 可能存在多条音轨, 每条音轨的编码不同
* 字幕: 多语言字母等  

以上信息都会经过具体的封装格式进行封装, 例如常见的`MP4`, 本文的视频封装以及音视频编码参考信息:
```
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2mp41
    encoder         : Lavf58.29.100
  Duration: 00:00:01.75, start: 0.000000, bitrate: 291 kb/s
    Stream #0:0(eng): Video: vp9 (Profile 0) (vp09 / 0x39307076), yuv420p(tv, progressive), 1080x1920, 216 kb/s, 30.13 fps, 30.13 tbr, 90k tbn, 90k tbc (default)
    Metadata:
      handler_name    : VideoHandle
    Stream #0:1(eng): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, mono, fltp, 73 kb/s (default)
    Metadata:
      handler_name    : SoundHandle
```
接下来播放器要通过`MeidaExtractor`(最终的工作位于`media.extractor`中)找到响应的数据源. 那么首先从封装信息中确定音视频`Track`数量, 其对应的编码格式, 然后再根据每条具体的`Track`构造`IMediaSource`.

`MediaPlayer.setDataSource`的Java部分过程比较复杂, 设计`ContentResolver`, 本文不讨论, 对于本地文件, 其最终配置到底层的`android_media_MediaPlayer_setDataSourceFD()` -> `MediaPlayer::setDataSource(int fd,...)`, 此时一个问题出现了:  
`MediaPlayer`是本地播放的么? 并不是, 是远程播放的, 那是谁在执行播放的动作? 是`MediaPlayerService`, 该服务运行在`mediaserver`中, 那么`mediaserver`中构造的播放器是什么? 接下来一起看看`MediaPlayer::setDataSource(int fd,...)`时发生了什么? 首先我们需要了解一个重要的服务: `MediaPlayerService`.

## MediaPlayerService
`mediaserver`创建`IMediaPlayerService`接口的`MediaPlayerService`实现, 该类将处理来自`MediaPlayer`的请求. 在`MediaPlayerService`创建时, 会注册多个`MediaPlayerFactory::IFactory`实现, 目前主要有两种:
* `NuPlayerFactory`: 主要的工厂类, 用于创建播放器实例: `NuPlayerDriver`, 其更底层的实现是`NuPlayer`
* `TestPlayerFactory`: 测试目的, 不关注

`MediaPlayer`设置数据源之前要先完成实际的播放器实例的创建, 它通过`IMediaPlayerService`接口访问了`mediaserver`中的`MediaPlayerService`服务, 然后申请创建播放器, 创建播放器后, 本地的`MediaPlayer`将通过`IMediaPlayer`接口引用服务器为其创建的播放器实例. 显然该`Client`实现了`BnMediaPlayer`并在创建后返回给应用, 它将作为一个引用传递给`MediaPlayer`并作为后续所有的请求的代理, `setDataSource()`也在其中.

`MediaPlayerService`要具备通知`MediaPlayer`的能力才行, 后者实现了`BnMediaPlayerClient`, 将通过`IMediaPlayerClient`在创建`Client`时被设置在`Client`的`mClient`中

在创建`Client`是也创建了`MediaPlayerService::Listener`, 该类是继承自`MediaPlayerBase::Listener`, 显然该`Listener`将负责从底层的`MediaPlayerBase`监听播放时的各种消息, 从这里, 也知道了在`MediaPlayerService`中, 负责播放任务的实现是集成自`MediaPlayerBase`的, 本例中的继承: `MediaPlayerBase` -> `MediaPlayerInterface` -> `NuPlayerDriver`, `Listener`本身持有了`Client`的引用, 因此`Listener::notify()`将通知到`Client::notify()`, 而这时调用上文的`MediaPlayerService::Listener`的`notify()`将完成通过`IMediaPlayerClient`完成对对端`MediaPlayer`的通知.

## NuPlayer
上文说到, `Client`负责响应来自`MediaPlayer`的请请求, 现在`Client`已经创建, `MediaPlayer`该通过`IMediaPlayer`接口通过它发起`setDataSource()`操作了, 这里分两个步骤:
* 设置数据源创建实际的播放器
* 执行`setDataSource()`

创建播放器的实例, 将在`MediaPlayerService::Client`响应`createPlayer`消息时通过`MediaPlayerFactory::createPlayer()`静态方法从`NuPlayerFactory`构建.  

此时创建的是`NuPlayerDriver`, 但该类会马上创建`NuPlayer`方法.
`NuPlayer`后续则会通过`MediaPlayerService::Client` -> `NuPlayerDriver`响应来自应用中`MediaPlayer`的很多事件, 事件的类型很多,我们只讨论传统本地视频文件的播放,关注以下几种类型:
* `kWhatSetDataSource`: 设置数据源头  
  对应`MediaPlayer.setDataSource()`, 支持各种各样的数据源, 例如: URI/文件/数据源等等
* `kWhatPrepare`: 准备播放器
  对应`MediaPlayer.prepare()`
* `kWhatSetVideoSurface`: 设置视频输出
  对应`MediaPlayer.setDisplay()`或者`MediaPlayer.setSurface()`, 它们的参数不同
* `kWhatStart`: 开始播放
  对应`MediaPlayer.start()`
* `kWhatSeek`: seek操作
* 对应`MediaPlayer.seekTo()`, 该方法可以设置seek的方式, seek时需要的参数:
  * `"seekTimeUs"`: seek的目标事件, 单位`us`
  * `"mode"`: seek的模式(向前/向后/最近等)
  * `"needNotify"`: 是否需要通知上层, 如果需要, `NuPlayer`将通过父类`MediaPlayerInterface`的`sendEvent()`方法通知上层.
* `kWhatPause`: 暂停操作
* `kWhatResume`: 恢复播放

NuPlayer不但需要负责完成各种下行的控制, 还要通过`AMessage`响应来自底层的一系列请求, 主要有以下集中类型:  
* `kWhatMediaClockNotify`: 负责监听来自`MediaClock`的消息, 消息中有如下三种信息:
  * "anchor-media-us"
  * "anchor-real-us"
  * "playback-rate"
* `kWhatSourceNotify`: 负责处理来自`NuPlayer::Source`的消息
  * 对于`public NuPlayer::Source`有以下集中主要类型:
    * `StreamingSource`
    * `HTTPLiveSource`
    * `RTSPSource`
    * `RTPSource`
    * `GenericSource`  
  * 对于消息本身, 则有以下信息:
    * "what": 具体的数据源消息类型, 又分以下几种类型:
      * `kWhatInstantiateSecureDecoders`: 数据源是安全类型, 通知创建安全类型的解码器
        * `"reply"`: 等待消息的`AMesage`对象, 用于通知数据源安全解码器的创建完成
      * `kWhatPrepared`: 数据源已准备好, 可以读取数据
        * `"err"`: 准备结束不代表成功, 该字段返回具体的状态码
      * `kWhatDrmInfo`: 有关于`DRM`信息
        * `"drmInfo"`一个类型为`ABuffer`的对象
      * `kWhatFlagsChanged`播放标识改变
        * `"flags"`改变的标识
      * `kWhatVideoSizeChanged`: 播放源表示播放的解码信息发生改变
        * `"format"`为具体改变的格式信息, 一`AMessage`体现, 其中主要的信息有
          * `"width"`
          * `"height"`  
            可能包含的信息:
          * `"sar-width"`
          * `"sar-height"`
          * `"display-width"`
          * `"display-height"`
          * `"rotation-degrees"`

`NuPlayer`在创建完成后会保存在`NuPlayerDriver`的`mPlayer`中, 而`NuPlayerDriver`作为`MediaPlayerInterface`(父类`MediaPlayerBase`)被`Client`的`mPlayer`引用, 因此总结

下行整体的调用流程:  
`MediaPlayer`(Java) -> `MediaPlayer`(C++) --[`binder`]--> [`IMediaPlayer` => `MediaPlayerService::Client`] -> `NuPlayerDriver` -> `NuPlayer`

上行消息流程:  
`NuPlayer` -> [`MediaPlayerBase::Listener` => `MediaPlayerService::Client::Listener`] -> `MediaPlayerService::Client` --[`binder`]--> [`IMediaPlayerClient` => `MediaPlayer`] -> [`MediaPlayerListener` => `JNIMediaPlayerListener`] -> `MediaPlayer`(Java)

后续所有的流程将按照总结的过程默认, 有特殊情况再进行标记.

`NuPlayer::setDataSourceAsync()`(在`NuPlayerDriver`被转换为异步处理)如何处理接下来的工作呢?


## 播放器准备工作

## 解码器加载过程
`C2SoftVpxDec`的加载过程:
* `libcodec2_soft_vp9dec.so`对应的`ComponentModule`创建
  * `media.swcodec`启动时, 通过`RegisterCodecServices`注册`ComponentStore`服务, 此时会创建`C2PlatformComponentStore`, 其集成关系:`C2PlatformComponentStore ` -> `C2ComponentStore`
  * `C2PlatformComponentStore`将创建`mLibPath`为`libcodec2_soft_vp9dec.so`的`ComponentLoader`类型
  * 最后通过`C2ComponentStore`创建实现了`IComponentStore`的`V1_2::utils::ComponentStore`实例, 并返回给`Codec2Client`
  * `Codec2Client`在查找组件是时, 如果找到了匹配的`ComponentLoader`, 在Loader的初始化过程中欧给你, 将创建`ComponentModule`对象  
* 组建的查找
  * `ComponentLoader`对象从对应的`libcodec2_soft_vp9dec.so`中查找`CreateCodec2Factory`符号
  * 调用`CreateCodec2Factory`符号将返回`C2ComponentFactory`类型, 其实现为`C2SoftVpxFactory`
  * 然后调用工厂类的`createInterface`方法, 返回一个`C2ComponentInterface`接口, 其实现为`SimpleC2Interface`模板类
  * 调用`C2ComponentFactory`的`createInterface`方法, 也就是`C2SoftVpxFactory::createInterface`, 这将欻功能键一个`C2ComponentInterface`接口, 实现为`SimpleC2Interface`模板类, 对于`Vpx9`该类的实现为`C2SoftVpxDec::IntfImpl`, 其将被记录在`C2Component::Traits`中
* 组建的创建
  * 查找组建的工作完成后, `ComponentModule`组建的`createComponent`方法被调用, 该方法将调用上文`CreateCodec2Factory`的对应方法, 而`CreateCodec2Factory::createComponent`负责创建`C2SoftVpxDec`, 继承关系: `C2SoftVpxDec` -> `SimpleC2Component` -> `C2Component`, 而该`C2Component`最后由`ComponentStore`创建的`Component`对象持有, 而`Component`对象实现了`IComponent`, 其后续将被返回给`Codec2Client`.

## 音画同步

## 视频渲染

## 音频渲染

## DRM

## Seek操作