- [`MediaPlayer.start()`](#mediaplayerstart)
    - [`NuPlayerDriver::start()`](#nuplayerdriverstart)
    - [`NuPlayer::instantiateDecoder()`实例化音视频解码器](#nuplayerinstantiatedecoder实例化音视频解码器)
    - [视频解码器](#视频解码器)
      - [音频解码器](#音频解码器)
    - [解码器`NuPlayer::Decoder`的构造](#解码器nuplayerdecoder的构造)
    - [解码器`NuPlayer::Decoder`的初始化](#解码器nuplayerdecoder的初始化)
    - [`NuPlayer::Decoder::onConfigure()`](#nuplayerdecoderonconfigure)
      - [`MediaCodec::CreateByType()`](#mediacodeccreatebytype)
        - [`MediaCodec::MediaCodec()`, `MediaCodec`状态: `UNINITIALIZED`](#mediacodecmediacodec-mediacodec状态-uninitialized)
        - [`MediaCodec::init()`, `MediaCodec`状态: `UNINITIALIZED` -> `INITIALIZING` -> `INITIALIZED`](#mediacodecinit-mediacodec状态-uninitialized---initializing---initialized)
          - [`CCodec`的构造](#ccodec的构造)
          - [`CCodec::setCallback()`配置解码器回调](#ccodecsetcallback配置解码器回调)
          - [`CCodecBufferChannel::setCallback()`配置解码缓冲通道的回调](#ccodecbufferchannelsetcallback配置解码缓冲通道的回调)
          - [`CCodec::initiateAllocateComponent()`, `MediaCodec`状态: `UNINITIALIZED` -> `INITIALIZING`](#ccodecinitiateallocatecomponent-mediacodec状态-uninitialized---initializing)
          - [`CCodec::initiateAllocateComponent()`完成, `MediaCodec`状态: `INITIALIZING` -> `INITIALIZED`](#ccodecinitiateallocatecomponent完成-mediacodec状态-initializing---initialized)
      - [`MediaCodec::configure()`, `MediaCodec`状态: `INITIALIZED` -> `CONFIGURING`](#mediacodecconfigure-mediacodec状态-initialized---configuring)
        - [`CCodec::initiateConfigureComponent()`, `MediaCodec`状态: `CONFIGURING` -> `CONFIGURED`](#ccodecinitiateconfigurecomponent-mediacodec状态-configuring---configured)
      - [`MediaCodec::start()`, `MediaCodec`状态: `CONFIGURED` -> `STARTING`](#mediacodecstart-mediacodec状态-configured---starting)
        - [`CCodec::initiateStart()`, `MediaCodec`状态: `STARTING` -> `STARTED`](#ccodecinitiatestart-mediacodec状态-starting---started)
        - [`CCodec::start()`](#ccodecstart)
        - [`CCodecBufferChannel::start()`对视频输出缓冲队列`IGraphicBufferProducer`的配置](#ccodecbufferchannelstart对视频输出缓冲队列igraphicbufferproducer的配置)

# `MediaPlayer.start()`
回到`MoviePlayer`的构造:
```
// packages/apps/Gallery2/src/com/android/gallery3d/app/MoviePlayer.java
    public MoviePlayer(View rootView, final MovieActivity movieActivity,
            Uri videoUri, Bundle savedInstance, boolean canReplay) {
        mContext = movieActivity.getApplicationContext();
        mRootView = rootView;
        mVideoView = (VideoView) rootView.findViewById(R.id.surface_view);
        ... ...
        mVideoView.setOnErrorListener(this);
        mVideoView.setOnCompletionListener(this);
        mVideoView.setVideoURI(mUri);
        ... ...
        mVideoView.setOnPreparedListener(new MediaPlayer.OnPreparedListener() {
            @Override
            public void onPrepared(MediaPlayer player) {
                ... ...
            }
        });
        ... ...
        if (savedInstance != null) { // this is a resumed activity
            ... ...
        } else {
            final Integer bookmark = mBookmarker.getBookmark(mUri);
            if (bookmark != null) {
                showResumeDialog(movieActivity, bookmark);
            } else {
                startVideo();
            }
        }
    }
    private void startVideo() {
        ... ...
        mVideoView.start();
        setProgress();
    }
```
`mVideoView`是上文的`VideoView`:
```
// frameworks/base/core/java/android/widget/VideoView.java
    @Override
    public void start() {
        if (isInPlaybackState()) {
            mMediaPlayer.start();
            mCurrentState = STATE_PLAYING;
        }
        mTargetState = STATE_PLAYING;
    }
```
终于调用到`MediaPlayer.start()`了, 为了节省篇幅, 我们都写到一起:
```
// frameworks/base/media/java/android/media/MediaPlayer.java
public class MediaPlayer extends PlayerBase
                         implements SubtitleController.Listener
                                  , VolumeAutomation
                                  , AudioRouting
{
    ... ...
    public void start() throws IllegalStateException {
        //FIXME use lambda to pass startImpl to superclass
        final int delay = getStartDelayMs();
        if (delay == 0) {
            startImpl();
        } else ... // 单独启动线程做延迟处理, 此处不考虑
    }

    private void startImpl() {
        baseStart(0); // unknown device at this point
        stayAwake(true);
        tryToEnableNativeRoutingCallback();
        _start();
    }
    private native void _start() throws IllegalStateException;
    ... ...
}
```
### `NuPlayerDriver::start()`
```
// frameworks/base/media/jni/android_media_MediaPlayer.cpp
static const JNINativeMethod gMethods[] = {
    ... ...
    {"_start",              "()V",                              (void *)android_media_MediaPlayer_start},
    ... ...
}
static void
android_media_MediaPlayer_start(JNIEnv *env, jobject thiz)
{
    ... ...
    sp<MediaPlayer> mp = getMediaPlayer(env, thiz);
    ... ...
    process_media_player_call( env, thiz, mp->start(), NULL, NULL );
}

### `NuPlayer::start()`
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
status_t NuPlayerDriver::start() {
    ALOGV("start(%p), state is %d, eos is %d", this, mState, mAtEOS);
    Mutex::Autolock autoLock(mLock);
    return start_l();
}
status_t NuPlayerDriver::start_l() {
    switch (mState) {
        // 此时状态必定为 STATE_PREPARED
        case STATE_UNPREPARED:
        ... ...
        case STATE_PAUSED:
        case STATE_STOPPED_AND_PREPARED:
        case STATE_PREPARED:
        {
            mPlayer->start();
            FALLTHROUGH_INTENDED;
        }
        ... ...
    }
    mState = STATE_RUNNING;
    return OK;
}

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::start() {
    (new AMessage(kWhatStart, this))->post();
}

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatSetDataSource:
        ... ...
        case kWhatStart:
        {
            // 显然 mStarted 为: false
            if (mStarted) {
                ... ...
            } else {
                onStart();
            }
            mPausedByClient = false;
            break;
        }
        ... ....
    }
}

void NuPlayer::onStart(int64_t startPositionUs, MediaPlayerSeekMode mode) {
    ... ...
    mRenderer = new Renderer(mAudioSink, mMediaClock, notify, flags);
    if (mVideoDecoder != NULL) {
        mVideoDecoder->setRenderer(mRenderer);
    }
    if (mAudioDecoder != NULL) {
        mAudioDecoder->setRenderer(mRenderer);
    }
    ... ...
    postScanSources();
}

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerRenderer.cpp
NuPlayer::Renderer::Renderer(
        const sp<MediaPlayerBase::AudioSink> &sink,
        const sp<MediaClock> &mediaClock,
        const sp<AMessage> &notify,
        uint32_t flags)
    : mAudioSink(sink),
      ... ...
      mWakeLock(new AWakeLock()) {
    CHECK(mediaClock != NULL);
    mPlaybackRate = mPlaybackSettings.mSpeed;
    mMediaClock->setPlaybackRate(mPlaybackRate);
    (void)mSyncFlag.test_and_set();
}
```
`NuPlayer`的`mAudioSink`也就是`AudioOutput`被设置给了`NuPlayer::Renderer`的`mAudioSink`成员, 后续渲染时, 此处会用到.
通过`setRenderer()`, `NuPlayer::Renderer`均设置到了`mVideoDecoder`和`mAudioDecoder`所对应的`CCodec`的父类`CodecBase`的`mRender`中(过程略去).

### `NuPlayer::instantiateDecoder()`实例化音视频解码器
对于`NuPlayer::onStart()`, 接着接看`postScanSources()`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
void NuPlayer::postScanSources() {
    if (mScanSourcesPending) {
        return;
    }

    sp<AMessage> msg = new AMessage(kWhatScanSources, this);
    msg->setInt32("generation", mScanSourcesGeneration);
    msg->post();

    mScanSourcesPending = true;
}

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatSetDataSource:
        ... ...
        case kWhatScanSources:
        {
            ... ...
            // initialize video before audio because successful initialization of
            // video may change deep buffer mode of audio.
            if (mSurface != NULL) {
                if (instantiateDecoder(false, &mVideoDecoder) == -EWOULDBLOCK) {
                    rescan = true;
                }
            }
            ... ...
        }
        ... ...
    }
}
```

### 视频解码器
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
status_t NuPlayer::instantiateDecoder(
        bool audio, sp<DecoderBase> *decoder, bool checkAudioModeChange) {
    ... ...
    if (!audio) {
        ... ...
        if (mCCDecoder == NULL) {
            mCCDecoder = new CCDecoder(ccNotify);
        }
        ... ...
    }
    ... ...
    if (audio) {
        ... ...
    } else {
        ... ...
        *decoder = new Decoder(
                notify, mSource, mPID, mUID, mRenderer, mSurface, mCCDecoder);
        mVideoDecoderError = false;
        ... ...
    }
    (*decoder)->init();
    ... ...
    (*decoder)->configure(format);
    ... ...
}
```


#### 音频解码器
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
status_t NuPlayer::instantiateDecoder(
        bool audio, sp<DecoderBase> *decoder, bool checkAudioModeChange) {
    ... ...
    if (!audio) {
        ... ...
    }
    ... ...
    if (audio) {
        sp<AMessage> notify = new AMessage(kWhatAudioNotify, this);
        ++mAudioDecoderGeneration;
        notify->setInt32("generation", mAudioDecoderGeneration);

        if (checkAudioModeChange) {
            determineAudioModeChange(format);
        }
        if (mOffloadAudio) {
            mSource->setOffloadAudio(true /* offload */);
            ... ...
            *decoder = new DecoderPassThrough(notify, mSource, mRenderer);
            ALOGV("instantiateDecoder audio DecoderPassThrough  hasVideo: %d", hasVideo);
        } else {
            mSource->setOffloadAudio(false /* offload */);
            *decoder = new Decoder(notify, mSource, mPID, mUID, mRenderer);
            ALOGV("instantiateDecoder audio Decoder");
        }
        mAudioDecoderError = false;
    } else {
        ... ...
    }
    (*decoder)->init();
    ... ...
    (*decoder)->configure(format);
    ... ...
}
```

### 解码器`NuPlayer::Decoder`的构造
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoder.cpp
NuPlayer::Decoder::Decoder(
        const sp<AMessage> &notify,
        const sp<Source> &source,
        pid_t pid,
        uid_t uid,
        const sp<Renderer> &renderer,
        const sp<Surface> &surface,
        const sp<CCDecoder> &ccDecoder)
    : DecoderBase(notify),
      mSurface(surface),
      mSource(source),
      mRenderer(renderer),
      mCCDecoder(ccDecoder),
      ... ...
      mComponentName("decoder") {
    mCodecLooper = new ALooper;
    mCodecLooper->setName("NPDecoder-CL");
    mCodecLooper->start(false, false, ANDROID_PRIORITY_AUDIO);
    mVideoTemporalLayerAggregateFps[0] = mFrameRateTotal;
}

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoderBase.cpp
NuPlayer::DecoderBase::DecoderBase(const sp<AMessage> &notify)
    :  mNotify(notify),
       ... ...
       mRequestInputBuffersPending(false) {
    mDecoderLooper = new ALooper;
    mDecoderLooper->setName("NPDecoder");
    mDecoderLooper->start(false, false, ANDROID_PRIORITY_AUDIO);
}
```

### 解码器`NuPlayer::Decoder`的初始化
`NuPlayer::instantiateDecoder()`中, `(*decoder)->init()`负责初始化解码器:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoderBase.cpp
void NuPlayer::DecoderBase::init() {
    mDecoderLooper->registerHandler(this);
}
```

### `NuPlayer::Decoder::onConfigure()`
`NuPlayer::instantiateDecoder()`中, `(*decoder)->configure(format)`开始配置解码器:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoderBase.cpp
void NuPlayer::DecoderBase::configure(const sp<AMessage> &format) {
    sp<AMessage> msg = new AMessage(kWhatConfigure, this);
    msg->setMessage("format", format);
    msg->post();
}

void NuPlayer::DecoderBase::onMessageReceived(const sp<AMessage> &msg) {

    switch (msg->what()) {
        case kWhatConfigure:
        {
            sp<AMessage> format;
            CHECK(msg->findMessage("format", &format));
            onConfigure(format);
            break;
        }
        ... ...
    }
}
```
#### `MediaCodec::CreateByType()`
`onConfigure()`调用回子类`NuPlayer::Decoder::onConfigure()`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoder.cpp
void NuPlayer::Decoder::onConfigure(const sp<AMessage> &format) {
    ... ...
    mCodec = MediaCodec::CreateByType(
            mCodecLooper, mime.c_str(), false /* encoder */, NULL /* err */, mPid, mUid, format);
    int32_t secure = 0;
    if (format->findInt32("secure", &secure) && secure != 0) {
        ... ...
    }
    ... ...
    err = mCodec->configure(
            format, mSurface, crypto, 0 /* flags */);
    ... ...
    sp<AMessage> reply = new AMessage(kWhatCodecNotify, this);
    mCodec->setCallback(reply);
    ... ...
    err = mCodec->start();
    ... ...
}
```
`NuPlayer::Decoder::onConfigure()`中`MediaCodec::CreateByType()`负责创建`MediaCodec`:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
sp<MediaCodec> MediaCodec::CreateByType(
        const sp<ALooper> &looper, const AString &mime, bool encoder, status_t *err, pid_t pid,
        uid_t uid) {
    sp<AMessage> format;
    return CreateByType(looper, mime, encoder, err, pid, uid, format);
}
```

##### `MediaCodec::MediaCodec()`, `MediaCodec`状态: `UNINITIALIZED`
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
sp<MediaCodec> MediaCodec::CreateByType(
        const sp<ALooper> &looper, const AString &mime, bool encoder, status_t *err, pid_t pid,
        uid_t uid, sp<AMessage> format) {
    Vector<AString> matchingCodecs;

    MediaCodecList::findMatchingCodecs(
            mime.c_str(),
            encoder,
            0,
            format,
            &matchingCodecs);
    ... ...
    for (size_t i = 0; i < matchingCodecs.size(); ++i) {
        sp<MediaCodec> codec = new MediaCodec(looper, pid, uid);
        AString componentName = matchingCodecs[i];
        status_t ret = codec->init(componentName);
        ... ..
        if (ret == OK) {
            return codec;
        }
    }
    return NULL;
}
```

`MediaCodecList::findMatchingCodecs()`负责查找支持当前解码格式解码器的名字, 其定义在`MediaCodecList.cpp`:
```
// frameworks/av/media/libstagefright/MediaCodecList.cpp
void MediaCodecList::findMatchingCodecs(
        const char *mime, bool encoder, uint32_t flags,
        Vector<AString> *matches) {
    sp<AMessage> format;        // initializes as clear/null
    findMatchingCodecs(mime, encoder, flags, format, matches);
}

void MediaCodecList::findMatchingCodecs(
        const char *mime, bool encoder, uint32_t flags, sp<AMessage> format,
        Vector<AString> *matches) {
    matches->clear();
    const sp<IMediaCodecList> list = getInstance();
    ... ...
    size_t index = 0;
    for (;;) {
        ssize_t matchIndex =
            list->findCodecByType(mime, encoder, index);
        if (matchIndex < 0) {
            break;
        }
        index = matchIndex + 1;
        const sp<MediaCodecInfo> info = list->getCodecInfo(matchIndex);
        CHECK(info != nullptr);
        AString componentName = info->getCodecName();
        ... ...
        matches->push(componentName);
        ALOGV("matching '%s'", componentName.c_str());
    }

    if (flags & kPreferSoftwareCodecs ||
            property_get_bool("debug.stagefright.swcodec", false)) {
        matches->sort(compareSoftwareCodecsFirst);
    }
}
```
此时如果找到解码器, 回到`MediaCodec::CreateByType()`, 开始创建`MediaCodec`:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
MediaCodec::MediaCodec(
        const sp<ALooper> &looper, pid_t pid, uid_t uid,
        std::function<sp<CodecBase>(const AString &, const char *)> getCodecBase,
        std::function<status_t(const AString &, sp<MediaCodecInfo> *)> getCodecInfo)
    : mState(UNINITIALIZED),
      ... ...
      mGetCodecInfo(getCodecInfo) {
    ... ...
    mResourceManagerProxy = new ResourceManagerServiceProxy(pid, mUid,
            ::ndk::SharedRefBase::make<ResourceManagerClient>(this));
    if (!mGetCodecBase) {
        mGetCodecBase = [](const AString &name, const char *owner) {
            return GetCodecBase(name, owner);
        };
    }
    ... ...
    initMediametrics();
}
```
`mGetCodecBase`被初始化为一个`std::function<>`对象, 后文的`MediaCodec::init()`会调用此`lambada`.

##### `MediaCodec::init()`, `MediaCodec`状态: `UNINITIALIZED` -> `INITIALIZING` -> `INITIALIZED`
回到`MediaCodec::CreateByType()`中, `MediaCodec`创建完成后通过`init()`配置通过`MediaCodecList::findMatchingCodecs()`找到的解码器:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
status_t MediaCodec::init(const AString &name) {
    .... ...
    mCodec = mGetCodecBase(name, owner);
    ... ...
    mCodec->setCallback(
            std::unique_ptr<CodecBase::CodecCallback>(
                    new CodecCallback(new AMessage(kWhatCodecNotify, this))));
    mBufferChannel = mCodec->getBufferChannel();
    mBufferChannel->setCallback(
            std::unique_ptr<CodecBase::BufferCallback>(
                    new BufferCallback(new AMessage(kWhatCodecNotify, this))));
    sp<AMessage> msg = new AMessage(kWhatInit, this);
    ... ...
    for (int i = 0; i <= kMaxRetry; ++i) {
        ... ...
        err = PostAndAwaitResponse(msg, &response);
        ... ...
    }
    ... ...
```

###### `CCodec`的构造
`mGetCodecBase`上文已介绍过, 故:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
//static
sp<CodecBase> MediaCodec::GetCodecBase(const AString &name, const char *owner) {
    if (owner) {
        if (strcmp(owner, "default") == 0) {
            return new ACodec;
        } else if (strncmp(owner, "codec2", 6) == 0) {
            return CreateCCodec();
        }
    }
    if (name.startsWithIgnoreCase("c2.")) {
        return CreateCCodec();
    } else ... ...
}

static CodecBase *CreateCCodec() {
    return new CCodec;
}
```
有着一些列的判断, Android S现在已普遍采用`Codec2`的框架, 因此, 因此通过`CreateCCodec()`创建了`CCodec`.

###### `CCodec::setCallback()`配置解码器回调
回到`MediaCodec::init()`, 首先构造了`CodecCallback`, 其实现了`CodecBase::CodecCallback`接口, 而`CCodec::setCallback()`是在父类`CodecBase`实现的:
```
// frameworks/av/media/libstagefright/include/media/stagefright/CodecBase.h
struct CodecBase : public AHandler, /* static */ ColorUtils {
    ... ...
    inline void setCallback(std::unique_ptr<CodecCallback> &&callback) {
        mCallback = std::move(callback);
    }
```
因此`MediaCodec::CodecCallback`作为`CodecBase::CodecCallback`设置在了`CCodec`的`mCallback`方法.

###### `CCodecBufferChannel::setCallback()`配置解码缓冲通道的回调
回到`MediaCodec::init()`, 首先构造了`BufferCallback`, 其实现了`CodecBase::BufferCallback`接口, 而`mBufferChannel`的类型是`CCodecBufferChannel`, 其`setCallback()`是在父类``实现的:
```
// prebuilts/vndk/v30/arm/include/frameworks/av/media/libstagefright/include/media/stagefright/CodecBase.h
class BufferChannelBase {
public:
    ... ...
    inline void setCallback(std::unique_ptr<CodecBase::BufferCallback> &&callback) {
        mCallback = std::move(callback);
    }
```
因此`MediaCodec::BufferCallback`作为`CodecBase::BufferCallback`设置在了`CCodecBufferChannel`的`mCallback`方法.

###### `CCodec::initiateAllocateComponent()`, `MediaCodec`状态: `UNINITIALIZED` -> `INITIALIZING`
回到`MediaCodec::init()`后期`kWhatInit`消息被发出, 其响应:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        ... ...
        case kWhatInit:
        {
            ... ...
            setState(INITIALIZING);
            ... ...
            mCodec->initiateAllocateComponent(format);
            break;
        }
        ... ...
    }
}
```
###### `CCodec::initiateAllocateComponent()`完成, `MediaCodec`状态: `INITIALIZING` -> `INITIALIZED`
`mCodec`的类型是`CCodec`, 故:
```
// frameworks/av/media/codec2/sfplugin/CCodec.cpp
void CCodec::initiateAllocateComponent(const sp<AMessage> &msg) {
    ... ...
    sp<AMessage> allocMsg(new AMessage(kWhatAllocate, this));
    allocMsg->setObject("codecInfo", codecInfo);
    allocMsg->post();
}

void CCodec::onMessageReceived(const sp<AMessage> &msg) {
    TimePoint now = std::chrono::steady_clock::now();
    CCodecWatchdog::getInstance()->watch(this);
    switch (msg->what()) {
        case kWhatAllocate: {
            ... ...
            allocate((MediaCodecInfo *)obj.get());
            break;
        }
        ... ...

void CCodec::allocate(const sp<MediaCodecInfo> &codecInfo) {
    ... ...
    client = Codec2Client::CreateFromService("default");
    ... ...
    std::shared_ptr<Codec2Client::Component> comp;
    c2_status_t status = Codec2Client::CreateComponentByName(
            componentName.c_str(),
            mClientListener,
            &comp,
            &client);
    ... ...
    mChannel->setComponent(comp);
    ... ...
    mCallback->onComponentAllocated(componentName.c_str());
}
```
`mCallback`的类型是`CodecCallback`, 此处调用到`CodecCallback::onComponentAllocated()`:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
void CodecCallback::onComponentAllocated(const char *componentName) {
    sp<AMessage> notify(mNotify->dup());
    notify->setInt32("what", kWhatComponentAllocated);
    notify->setString("componentName", componentName);
    notify->post();
}

void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        {
            ... ...
            switch (what) {
                case kWhatError:
                ... ...
                case kWhatComponentAllocated:
                {
                    ... ...
                    setState(INITIALIZED);
                    ... ...
                    postPendingRepliesAndDeferredMessages("kWhatComponentAllocated");
                    break;
                }
                ... ...
```
至此`MediaCodec::init()`算结束了.

#### `MediaCodec::configure()`, `MediaCodec`状态: `INITIALIZED` -> `CONFIGURING`
回到`NuPlayer::Decoder::onConfigure()`, 开始通过`mCodec->configure()`对`MediaCodec`进行配置:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
status_t MediaCodec::configure(
        const sp<AMessage> &format,
        const sp<Surface> &nativeWindow,
        const sp<ICrypto> &crypto,
        uint32_t flags) {
    return configure(format, nativeWindow, crypto, NULL, flags);
}
status_t MediaCodec::configure(
        const sp<AMessage> &format,
        const sp<Surface> &surface,
        const sp<ICrypto> &crypto,
        const sp<IDescrambler> &descrambler,
        uint32_t flags) {
    ... ...
    sp<AMessage> msg = new AMessage(kWhatConfigure, this);
    updateLowLatency(format);
    msg->setMessage("format", format);
    msg->setInt32("flags", flags);
    msg->setObject("surface", surface);
    mConfigureMsg = msg;
    for (int i = 0; i <= kMaxRetry; ++i) {
        sp<AMessage> response;
        err = PostAndAwaitResponse(msg, &response);
        ... ...

void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        ... ...
        case kWhatConfigure:
        {
            ... ...
            mReplyID = replyID;
            setState(CONFIGURING);
            .. ...
            mCodec->initiateConfigureComponent(format);
            break;
        }
    ... ...
```
`PostAndAwaitResponse()`会等待`MediaCodec::onMessageReceived()`处理完成的消息回复, 后者通过`mReplyID`记录了回复的ID. 后问有用到.

##### `CCodec::initiateConfigureComponent()`, `MediaCodec`状态: `CONFIGURING` -> `CONFIGURED`
`mCodec`的类型是`CCodec`, 因此:
```
// frameworks/av/media/codec2/sfplugin/CCodec.cpp
void CCodec::initiateConfigureComponent(const sp<AMessage> &format) {
    ... ...
    sp<AMessage> msg(new AMessage(kWhatConfigure, this));
    msg->setMessage("format", format);
    msg->post();
}

void CCodec::onMessageReceived(const sp<AMessage> &msg) {
    ... ...
    switch (msg->what()) {
        ... ...
        case kWhatConfigure: {
            // C2Component::commit_sm() should return within 5ms.
            setDeadline(now, 1500ms, "configure");
            sp<AMessage> format;
            CHECK(msg->findMessage("format", &format));
            configure(format);
            break;
        }
        ... ...

void CCodec::configure(const sp<AMessage> &msg) {
    std::shared_ptr<Codec2Client::Component> comp;
    auto checkAllocated = [this, &comp] {
        ... ...
    }
    if (tryAndReportOnError(checkAllocated) != OK) {
        return;
    }
    auto doConfig = [msg, comp, this]() -> status_t {
        AString mime;
        ... ...
    }
    if (tryAndReportOnError(doConfig) != OK) {
        return;
    }
    Mutexed<std::unique_ptr<Config>>::Locked configLocked(mConfig);
    const std::unique_ptr<Config> &config = *configLocked;
    config->queryConfiguration(comp);
    mCallback->onComponentConfigured(config->mInputFormat, config->mOutputFormat);
}
```
`doConfig`是个`lambada`, 作为`std::fucntion`传递给`tryAndReportOnError()`, 该部分代码做了大量配置工作, 完成配置后, `mCallback->onComponentConfigured()`回调到上文设置的`MediaCodec::CodecCallback::onComponentConfigured()`:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
void CodecCallback::onComponentConfigured(
        const sp<AMessage> &inputFormat, const sp<AMessage> &outputFormat) {
    ... ...
    notify->setInt32("what", kWhatComponentConfigured);
    ... ...
    notify->post();
}
void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        {
            ... ...
            switch (what) {
                case kWhatError:
                ... ....
                case kWhatComponentConfigured:
                {
                    ... ...
                    setState(CONFIGURED);
                    postPendingRepliesAndDeferredMessages("kWhatComponentConfigured");
                    ... ...

void MediaCodec::postPendingRepliesAndDeferredMessages(
        std::string origin, status_t err /* = OK */) {
    ... ...
    postPendingRepliesAndDeferredMessages(origin, response);
}

void MediaCodec::postPendingRepliesAndDeferredMessages(
        std::string origin, const sp<AMessage> &response) {
    LOG_ALWAYS_FATAL_IF(
            !mReplyID,
            "postPendingRepliesAndDeferredMessages: mReplyID == null, from %s following %s",
            origin.c_str(),
            mLastReplyOrigin.c_str());
    mLastReplyOrigin = origin;
    response->postReply(mReplyID);
    ... ...
}
```
此时上文的`PostAndAwaitResponse()`返回, `MediaCodec::configure()`结束.

#### `MediaCodec::start()`, `MediaCodec`状态: `CONFIGURED` -> `STARTING`
回到`NuPlayer::Decoder::onConfigure()`中, 此时调用到`mCodec->start()`:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
status_t MediaCodec::start() {
    sp<AMessage> msg = new AMessage(kWhatStart, this);
    ... ...
    for (int i = 0; i <= kMaxRetry; ++i) {
        ... ...
        err = PostAndAwaitResponse(msg, &response);
        ... ...
    }
    ... ...
}

void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        ... ...
        case kWhatStart:
        {
            ... ...
            mReplyID = replyID;
            setState(STARTING);
            mCodec->initiateStart();
            break;
        }
        ... ...
```
##### `CCodec::initiateStart()`, `MediaCodec`状态: `STARTING` -> `STARTED`
`PostAndAwaitResponse()`和上文的流程基本相同, 仅关注主要的流程`CCodec::initiateStart()`:
```
// frameworks/av/media/codec2/sfplugin/CCodec.cpp
void CCodec::initiateStart() {
    auto setStarting = [this] {
        Mutexed<State>::Locked state(mState);
        if (state->get() != ALLOCATED) {
            return UNKNOWN_ERROR;
        }
        state->set(STARTING);
        return OK;
    };
    if (tryAndReportOnError(setStarting) != OK) {
        return;
    }
    (new AMessage(kWhatStart, this))->post();
}
```

##### `CCodec::start()`
`kWhatStart`消息由`CCodec::onMessageReceived()`处理:
```
// frameworks/av/media/codec2/sfplugin/CCodec.cpp
void CCodec::onMessageReceived(const sp<AMessage> &msg) {
    TimePoint now = std::chrono::steady_clock::now();
    CCodecWatchdog::getInstance()->watch(this);
    switch (msg->what()) {
        case kWhatAllocate: 
        ... ...
        case kWhatStart: {
            // C2Component::start() should return within 500ms.
            setDeadline(now, 1500ms, "start");
            start();
            break;
        }
        ... ...
    }
    setDeadline(TimePoint::max(), 0ms, "none");
}

void CCodec::start() {
    ... ...
    c2_status_t err = comp->start();
    ... ...
    err2 = mChannel->start(inputFormat, outputFormat, buffersBoundToCodec);
    ... ...
    mCallback->onStartCompleted();
    (void)mChannel->requestInitialInputBuffers();
}
```
##### `CCodecBufferChannel::start()`对视频输出缓冲队列`IGraphicBufferProducer`的配置
```
// frameworks/av/media/codec2/sfplugin/CCodecBufferChannel.cpp
status_t CCodecBufferChannel::start(
        const sp<AMessage> &inputFormat,
        const sp<AMessage> &outputFormat,
        bool buffersBoundToCodec) {
    ... ...
    if (outputFormat != nullptr) {
        ... ...
        // Try to set output surface to created block pool if given.
        if (outputSurface) {
            mComponent->setOutputSurface(
                    outputPoolId_,
                    outputSurface,
                    outputGeneration,
                    maxDequeueCount);
        } else ... ...
        ... ...
    }
    ... ...
    mInputMetEos = false;
    mSync.start();
    return OK;
}
```
继续对`mComponent`也就是``进行配置:
```
// frameworks/av/media/codec2/hidl/client/client.cpp
c2_status_t Codec2Client::Component::setOutputSurface(
        C2BlockPool::local_id_t blockPoolId,
        const sp<IGraphicBufferProducer>& surface,
        uint32_t generation,
        int maxDequeueCount) {
    ... ...
    if (!surface) {
        mOutputBufferQueue->configure(nullIgbp, generation, 0, maxDequeueCount, nullptr);
    } else if (surface->getUniqueId(&bqId) != OK) {
        ... ...
        mOutputBufferQueue->configure(nullIgbp, generation, 0, maxDequeueCount, nullptr);
    } else {
        mOutputBufferQueue->configure(surface, generation, bqId, maxDequeueCount, mBase1_2 ?
                                      &syncObj : nullptr);
    }
    ... ...
}
```
`mOutputBufferQueue`的类型是`OutputBufferQueue`, 因此不管那个分支, 都调用了`OutputBufferQueue::configure()`:
```
// frameworks/av/media/codec2/hidl/client/output.cpp
bool OutputBufferQueue::configure(const sp<IGraphicBufferProducer>& igbp,
                                  uint32_t generation,
                                  uint64_t bqId,
                                  int maxDequeueBufferCount,
                                  std::shared_ptr<V1_2::SurfaceSyncObj> *syncObj) {
    ... ...
    sp<GraphicBuffer> buffers[BufferQueueDefs::NUM_BUFFER_SLOTS];
    std::weak_ptr<_C2BlockPoolData>
            poolDatas[BufferQueueDefs::NUM_BUFFER_SLOTS];
    {
        ... ...
        mIgbp = igbp;
        ... ...
        for (int i = 0; i < BufferQueueDefs::NUM_BUFFER_SLOTS; ++i) {
            ... ...
            status_t result = igbp->attachBuffer(&bqSlot, mBuffers[i]);
            if (result != OK) {
                continue;
            }
            bool attach =
                    _C2BlockFactory::EndAttachBlockToBufferQueue(
                            data, mOwner, getHgbp(mIgbp), mSyncMem,
                            generation, bqId, bqSlot);
            ... ...
        }
        ... ...
    }
    ... ...
}
```
`IGraphicBufferProducer`被设置到了`OutputBufferQueue`的`mIgbp`, 在后文`OutputBufferQueue::outputBuffer()`时会用到

```
// frameworks/av/media/libstagefright/MediaCodec.cpp
void CodecCallback::onStartCompleted() {
    sp<AMessage> notify(mNotify->dup());
    notify->setInt32("what", kWhatStartCompleted);
    notify->post();
}

void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        {
            ... ...
            switch (what) {
                case kWhatError:
                ... ...
                case kWhatStartCompleted:
                {
                    ... ...
                    if (mIsVideo) {
                        mResourceManagerProxy->addResource(
                                MediaResource::GraphicMemoryResource(getGraphicBufferSize()));
                    }
                    setState(STARTED);
                    postPendingRepliesAndDeferredMessages("kWhatStartCompleted");
                    break;
                }
```
`postPendingRepliesAndDeferredMessages("kWhatStartCompleted")`完成后, `MediaCodec::start()`返回.