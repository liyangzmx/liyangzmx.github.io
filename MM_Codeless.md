## MediaPlayer
`MediaPlayer`再Native主要的实现是通过binder将播放视频的数据发送给`mediaserver`中的播放器.

`mediaserver`创建`IMediaPlayerService`接口的`MediaPlayerService`实现, 该类将处理来自`MediaPlayer`的请求. 在`MediaPlayerService`创建时, 会注册多个`MediaPlayerFactory::IFactory`实现, 目前主要有两种:
* `NuPlayerFactory`: 主要的工厂类, 用于创建播放器实例: `NuPlayerDriver`, 其更底层的实现是`NuPlayer`
* `TestPlayerFactory`: 测试目的, 不关注

## NuPlayer
`NuPlayer`是多实例的, 通过`MediaPlayerService::Client`与`MediaPlayer`是一一对应的关系.
它将在`MediaPlayerService::Client`响应`createPlayer`消息时通过`MediaPlayerFactory::createPlayer()`静态方法从`NuPlayerFactory`构建.  
`NuPlayer`需要通过`MediaPlayerService::Client` -> `NuPlayerDriver`响应来自应用中`MediaPlayer`的很多事件, 事件的类型很多,我们只讨论传统本地视频文件的播放,关注以下几种类型:
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
  * `"needNotify"`: 是否需要通知上层, 如果需要, `NuPlayer`将通过父类`MediaPlayerInterface`的`sendEvent()`方法通知上层, 通知流程为: `NuPlayer` -> [`MediaPlayerBase::Listener` => `MediaPlayerService::Client::Listener`] -> `MediaPlayerService::Client` ---> [`IMediaPlayerClient` => `MediaPlayer`] -> [`MediaPlayerListener` => `JNIMediaPlayerListener`
* `kWhatPause`: 暂停操作
* `kWhatResume`: 恢复播放

## Apex
关于`Android.bp`中`apex_key`的部分, 参考`/system/apex/docs/README.md`以及`/system/apex/docs/howto.md`的部分.

## MediaCodec
实际的codec一般跑在独立的线程:
* codec2类型的编解码器运行在:`mediaswcodec`, 路径`frameworks/av/services/mediacodec/main_codecservice.cpp`, 其加载的插件属于Android APEX(可升级组件)的部分.
因此`media.codec`位于`frameworks/av/apex/`中. 
* omx类型的编解码器运行在`android.hardware.media.omx@1.0-service`

`media_codecs.xml`的查找顺序:
* `/apex/com.android.media.swcodec/etc`下查找:
  * `media_codecs.xml`
  * `media_codecs_performance.xml`
* 从`/[product|odm|vendor|system]/etc`中查找:
  * `media_codecs_c2.xml`
  * `media_codecs_performance_c2.xml`
* 从`/[product|odm|vendor|system]/etc`中查找:
  * `media_codecs.xml`
  * `media_codecs_performance.xml`

MediaCodec的创建方式有很多种:
* `CreateByType()`
* `CreateByComponentName()`

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