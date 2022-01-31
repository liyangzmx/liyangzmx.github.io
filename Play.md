- [系统相册播放相机录制的视频](#系统相册播放相机录制的视频)
- [MediaPlayer的创建与配置](#mediaplayer的创建与配置)
- [`mMediaPlayer.setOnPreparedListener()`](#mmediaplayersetonpreparedlistener)
- [`MediaPlayer.setDataSource()`](#mediaplayersetdatasource)
  - [Native层`MediaPlayer`的创建](#native层mediaplayer的创建)
  - [`MediaPlayer::setDataSource()`](#mediaplayersetdatasource-1)
    - [`mediaserver`中`MediaPlayerService::Client`的创建](#mediaserver中mediaplayerserviceclient的创建)
    - [`mediaserver`中`NuPlayerDriver`的创建](#mediaserver中nuplayerdriver的创建)
    - [`mediaserver`中`NuPlayerDriver`的`NuPlayer`的创建与初始化](#mediaserver中nuplayerdriver的nuplayer的创建与初始化)
  - [`NuPlayerDriver::setDataSource()`](#nuplayerdriversetdatasource)
  - [`NuPlayer::setDataSourceAsync()`](#nuplayersetdatasourceasync)
  - [`GenericSource`的创建](#genericsource的创建)
- [MediaPlayer.setDisplay()](#mediaplayersetdisplay)
  - [`NuPlayerDriver::setVideoSurfaceTexture()`](#nuplayerdriversetvideosurfacetexture)
  - [`NuPlayer::setVideoSurfaceTextureAsync()`](#nuplayersetvideosurfacetextureasync)
- [`MediaPlayer.prepareAsync()`](#mediaplayerprepareasync)
  - [`NuPlayerDriver::prepareAsync()`](#nuplayerdriverprepareasync)
  - [`NuPlayer::prepareAsync()`](#nuplayerprepareasync)

## 系统相册播放相机录制的视频
`VideoView`(继承自`SurfaceView`)通过`SurfaceHolder.Callback`(其成员`mSHCallback`)监听自身`SurfaceHolder`的事件, 在`public void surfaceCreated(SurfaceHolder holder)`时:
```
// frameworks/base/core/java/android/widget/VideoView.java
    @UnsupportedAppUsage
    SurfaceHolder.Callback mSHCallback = new SurfaceHolder.Callback()
    {
        public void surfaceCreated(SurfaceHolder holder)
        {
            mSurfaceHolder = holder;
            openVideo();
        }
        ... ...
```

而`mSHCallback`是在`VideoView`构造的时注册的:
```
// frameworks/base/core/java/android/widget/VideoView.java
    public VideoView(Context context, AttributeSet attrs, int defStyleAttr, int defStyleRes) {
        ... ...
        getHolder().addCallback(mSHCallback);
        getHolder().setType(SurfaceHolder.SURFACE_TYPE_PUSH_BUFFERS);
        ... ...
```

## MediaPlayer的创建与配置
当点击相册中的项目时, `VideoView`被创建, 且其`SurfaceControl`发出`surfaceCreated()`回调, 因此根据上文代码`openVideo()`被调用:
```
// frameworks/base/core/java/android/widget/VideoView.java
    private void openVideo() {
        ... ...
        try {
            ... ...
            mMediaPlayer = new MediaPlayer();
            ... ...
            mMediaPlayer.setOnPreparedListener(mPreparedListener);
            mMediaPlayer.setOnVideoSizeChangedListener(mSizeChangedListener);
            mMediaPlayer.setOnCompletionListener(mCompletionListener);
            mMediaPlayer.setOnErrorListener(mErrorListener);
            mMediaPlayer.setOnInfoListener(mInfoListener);
            mMediaPlayer.setOnBufferingUpdateListener(mBufferingUpdateListener);
            mCurrentBufferPercentage = 0;
            mMediaPlayer.setDataSource(mContext, mUri, mHeaders);
            mMediaPlayer.setDisplay(mSurfaceHolder);
            mMediaPlayer.setAudioAttributes(mAudioAttributes);
            mMediaPlayer.setScreenOnWhilePlaying(true);
            mMediaPlayer.prepareAsync();
            ... ...
            for (Pair<InputStream, MediaFormat> pending: mPendingSubtitleTracks) {
                try {
                    mMediaPlayer.addSubtitleSource(pending.first, pending.second);
                    ... ...
            mCurrentState = STATE_PREPARING;
            attachMediaController();
            ... ...
```

## `mMediaPlayer.setOnPreparedListener()`
```
// frameworks/base/media/java/android/media/MediaPlayer.java
    public void setOnPreparedListener(OnPreparedListener listener)
    {
        mOnPreparedListener = listener;
    }
```
应用设置了`OnPreparedListener`到`MediaPlayer`中, 改监听要等到`MediaPlayer.prepareAsync()`执行完成才会被调用, 后问会讲到.

## `MediaPlayer.setDataSource()`
先看`setDataSource()`:
```
// frameworks/base/media/java/android/media/MediaPlayer.java
    public void setDataSource(@NonNull Context context, @NonNull Uri uri,
            @Nullable Map<String, String> headers)
            throws IOException, IllegalArgumentException, SecurityException, IllegalStateException {
        setDataSource(context, uri, headers, null);
    }
    public void setDataSource(@NonNull Context context, @NonNull Uri uri,
            @Nullable Map<String, String> headers, @Nullable List<HttpCookie> cookies)
            throws IOException {
        ... ...
        if (ContentResolver.SCHEME_FILE.equals(scheme)) {
            ... ...
        } else if (ContentResolver.SCHEME_CONTENT.equals(scheme)
                && Settings.AUTHORITY.equals(authority)) {
            ... ...
        } else {
            if (attemptDataSource(resolver, uri)) {
                return;
            } .. ...
        }
        ... ...

    private boolean attemptDataSource(ContentResolver resolver, Uri uri) {
        ... ...
        try (AssetFileDescriptor afd = optimize
                ? resolver.openTypedAssetFileDescriptor(uri, "*/*", opts)
                : resolver.openAssetFileDescriptor(uri, "r")) {
            setDataSource(afd);
            ... ...

    public void setDataSource(@NonNull AssetFileDescriptor afd)
            throws IOException, IllegalArgumentException, IllegalStateException {
        ... ...
        if (afd.getDeclaredLength() < 0) {
            setDataSource(afd.getFileDescriptor());
            ... ...

    public void setDataSource(FileDescriptor fd)
            throws IOException, IllegalArgumentException, IllegalStateException {
        ... ...
        setDataSource(fd, 0, 0x7ffffffffffffffL);
    }

    public void setDataSource(FileDescriptor fd, long offset, long length)
            throws IOException, IllegalArgumentException, IllegalStateException {
        try (ParcelFileDescriptor modernFd = FileUtils.convertToModernFd(fd)) {
            if (modernFd == null) {
                _setDataSource(fd, offset, length);
            } else ... ...
            ... ...

    private native void _setDataSource(FileDescriptor fd, long offset, long length)
            throws IOException, IllegalArgumentException, IllegalStateException;
```
经过一系列的调用, `_setDataSource()`是个Native的方法, 注意该Native方法有两种实现:
```
// frameworks/base/media/jni/android_media_MediaPlayer.cpp
static const JNINativeMethod gMethods[] = {
    ... ...
    {"_setDataSource",      "(Ljava/io/FileDescriptor;JJ)V",    (void *)android_media_MediaPlayer_setDataSourceFD},
    {"_setDataSource",      "(Landroid/media/MediaDataSource;)V",(void *)android_media_MediaPlayer_setDataSourceCallback },
    ... ...
};

static void
android_media_MediaPlayer_setDataSourceFD(JNIEnv *env, jobject thiz, jobject fileDescriptor, jlong offset, jlong length)
{
    sp<MediaPlayer> mp = getMediaPlayer(env, thiz);
    ... ...
    int fd = jniGetFDFromFileDescriptor(env, fileDescriptor);
    ALOGV("setDataSourceFD: fd %d", fd);
    process_media_player_call( env, thiz, mp->setDataSource(fd, offset, length), "java/io/IOException", "setDataSourceFD failed." );
}
```

### Native层`MediaPlayer`的创建
其`mp`通过``获得, 而其对应的Java层的`MediaPlayer.mNativeContext`是在`MeidaCodec.native_setup()`时设置的:
```
// frameworks/base/media/jni/android_media_MediaPlayer.cpp
static void
android_media_MediaPlayer_native_setup(JNIEnv *env, jobject thiz, jobject weak_this,
                                       jobject jAttributionSource)
{
    ... ...
    sp<MediaPlayer> mp = new MediaPlayer(attributionSource);
    ... ...
    sp<JNIMediaPlayerListener> listener = new JNIMediaPlayerListener(env, thiz, weak_this);
    mp->setListener(listener);
    ... ...
    setMediaPlayer(env, thiz, mp);
}

static sp<MediaPlayer> setMediaPlayer(JNIEnv* env, jobject thiz, const sp<MediaPlayer>& player)
{
    Mutex::Autolock l(sLock);
    sp<MediaPlayer> old = (MediaPlayer*)env->GetLongField(thiz, fields.context);
    ... ...
    env->SetLongField(thiz, fields.context, (jlong)player.get());
    return old;
}
```
此处创建了一个`JNIMediaPlayerListener`, 用于接受`MediaPlayer`的回调, 而该回调是从`mediaerver`通过Binder发回的, 在`mediaserver`中的播放器完成准备工作后会体现到, 此处只关注`mp->setListener()`:
```
// frameworks/av/media/libmedia/mediaplayer.cpp
status_t MediaPlayer::setListener(const sp<MediaPlayerListener>& listener)
{
    ALOGV("setListener");
    Mutex::Autolock _l(mLock);
    mListener = listener;
    return NO_ERROR;
}
```
可以看出`JNIMediaPlayerListener`作为`MediaPlayerListener`被`MediaPlayer`的`mListener`保存.

### `MediaPlayer::setDataSource()`
上文 `env->SetLongField()`设置的正是 `mNativeContext`. 回到`android_media_MediaPlayer_setDataSourceFD()`, 此时`MediaPlayer::setDataSource()`被调用:
```
// frameworks/av/media/libmedia/mediaplayer.cpp
status_t MediaPlayer::setDataSource(int fd, int64_t offset, int64_t length)
{
    ... ...
    const sp<IMediaPlayerService> service(getMediaPlayerService());
    if (service != 0) {
        sp<IMediaPlayer> player(service->create(this, mAudioSessionId, mAttributionSource));
        if ((NO_ERROR != doSetRetransmitEndpoint(player)) ||
            (NO_ERROR != player->setDataSource(fd, offset, length))) {
            player.clear();
        }
        err = attachNewPlayer(player);
    }
    return err;
}
```

#### `mediaserver`中`MediaPlayerService::Client`的创建
首先通过Binder调用`IMediaPlayerService::create()`创建一个`IMediaPlayer`:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
sp<IMediaPlayer> MediaPlayerService::create(const sp<IMediaPlayerClient>& client,
        audio_session_t audioSessionId, const AttributionSourceState& attributionSource)
{
    ... ...
    sp<Client> c = new Client(
            this, verifiedAttributionSource, connId, client, audioSessionId);
    ... ...
    wp<Client> w = c;
    {
        Mutex::Autolock lock(mLock);
        mClients.add(w);
    }
    return c;
}
```
此处在`mediaserver`中, `Client`被构造:
```
MediaPlayerService::Client::Client(
        const sp<MediaPlayerService>& service, const AttributionSourceState& attributionSource,
        int32_t connId, const sp<IMediaPlayerClient>& client,
        audio_session_t audioSessionId)
        : mAttributionSource(attributionSource)
{
    ALOGV("Client(%d) constructor", connId);
    mConnId = connId;
    mService = service;
    ... ...
    mAudioSessionId = audioSessionId;
    ... ...
    mListener = new Listener(this);
    ... ....
}
```
`mListener`后文再说. `Client`可通过`mService`与`MediaPlayerService`交互. 综上所述`IMediaPlayer`的实现是`MediaPlayerService::Client`, 后续应用中的`MediaPlayer`(Native)将通过Binder与此`Client`通信.回到`MediaPlayer::setDataSource()`中, 创建完`IMediaPlayer`后调用`player->setDataSource()`:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
status_t MediaPlayerService::Client::setDataSource(int fd, int64_t offset, int64_t length)
{
    ... ...
    player_type playerType = MediaPlayerFactory::getPlayerType(this,
                                                               fd,
                                                               offset,
                                                               length);
    sp<MediaPlayerBase> p = setDataSource_pre(playerType);
    ... ...
    return mStatus = setDataSource_post(p, p->setDataSource(fd, offset, length));
    ... ...
}
```

#### `mediaserver`中`NuPlayerDriver`的创建
`setDataSource_pre()`时做了很多工作, 但主要还是创建了`MediaPlayerBase`, `playerType`确定了后续需要创建的播放器的类型, Android目前的播放器工厂类默认是`NuPlayerFactory`(还有一种是`TestPlayerFactory`):
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
sp<MediaPlayerBase> MediaPlayerService::Client::setDataSource_pre(
        player_type playerType)
{
    ... ...
    sp<MediaPlayerBase> p = createPlayer(playerType);
    ... ...
}

sp<MediaPlayerBase> MediaPlayerService::Client::createPlayer(player_type playerType)
{
    sp<MediaPlayerBase> p = getPlayer();
    ... ...
    if (p == NULL) {
        p = MediaPlayerFactory::createPlayer(playerType, mListener,
            VALUE_OR_FATAL(aidl2legacy_int32_t_pid_t(mAttributionSource.pid)));
    }
    ... ...
```
还记得`mListener`么? 在创建`Client`时, 它作为`Listener`被创建, 此时它通过`createPlayer()`设置给了新创建的播放器.

显然`p`在一开始是`nullptr`, `MediaPlayerFactory::createPlayer()`负责创建播放器:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerFactory.cpp
sp<MediaPlayerBase> MediaPlayerFactory::createPlayer(
        player_type playerType,
        const sp<MediaPlayerBase::Listener> &listener,
        pid_t pid) {
    sp<MediaPlayerBase> p;
    ... ...
    factory = sFactoryMap.valueFor(playerType);
    CHECK(NULL != factory);
    p = factory->createPlayer(pid);
    ... ...
    init_result = p->initCheck();
    if (init_result == NO_ERROR) {
        p->setNotifyCallback(listener);
    } else {
        ALOGE("Failed to create player object of type %d, initCheck failed"
              " (res = %d)", playerType, init_result);
        p.clear();
    }

    return p;
}
```
根据上文`factory`的类型显然是`NuPlayerFactory`, 因此:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerFactory.cpp
class NuPlayerFactory : public MediaPlayerFactory::IFactory {
    public:
        ... ...
    virtual sp<MediaPlayerBase> createPlayer(pid_t pid) {
        ALOGV(" create NuPlayer");
        return new NuPlayerDriver(pid);
    }
```
显然`NuPlayerDriver`被构造:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
NuPlayerDriver::NuPlayerDriver(pid_t pid)
    : ... ...
      mPlayer(new NuPlayer(pid, mMediaClock)),
      ... ...
      mAutoLoop(false) {
    mLooper->setName("NuPlayerDriver Looper");
    mMediaClock->init();
    // set up an analytics record
    mMetricsItem = mediametrics::Item::create(kKeyPlayer);
    mLooper->start(
            false, /* runOnCallingThread */
            true,  /* canCallJava */
            PRIORITY_AUDIO);
    mLooper->registerHandler(mPlayer);
    mPlayer->init(this);
}
```

#### `mediaserver`中`NuPlayerDriver`的`NuPlayer`的创建与初始化
显然这里有两个调用:
* NuPlayer::NuPlayer()
* NuPlayer::init()

先看`NuPlayer::NuPlayer()`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
NuPlayer::NuPlayer(pid_t pid, const sp<MediaClock> &mediaClock)
    : mUIDValid(false),
      mPID(pid),
      ... ...
      mIsDrmProtected(false),
      mDataSourceType(DATA_SOURCE_TYPE_NONE) {
    CHECK(mediaClock != NULL);
    clearFlushComplete();
}
```

再看`NuPlayer::init()`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::init(const wp<NuPlayerDriver> &driver) {
    mDriver = driver;

    sp<AMessage> notify = new AMessage(kWhatMediaClockNotify, this);
    mMediaClock->setNotificationMessage(notify);
}
```
`NuPlayer`通过`mDriver`持有`NuPlayerDriver`. 此时`NuPlayerDriver`构造完成, 且其继承关系:`MediaPlayerBase` -> `MediaPlayerInterface` -> `NuPlayerDriver`, `kWhatMediaClockNotify`本文不讨论.

回到`MediaPlayerFactory::createPlayer()`, 其完成对`NuPlayerDriver`的创建后, 通过`p->setNotifyCallback(listener)`设置了监听, 此时调用的是`NuPlayerDriver`的父类`MediaPlayerInterface`的接口:
```
// frameworks/av/media/libmediaplayerservice/include/MediaPlayerInterface.h

    void        setNotifyCallback(
            const sp<Listener> &listener) {
        Mutex::Autolock autoLock(mNotifyLock);
        mListener = listener;
    }
```
可以看到`MediaPlayerService::Client::Listener`被设置到了`NuPlayerDriver`(父类`MediaPlayerInterface`)的`mListener`上, 因此`NuPlayerDriver`可以通过此对象通知`MediaPlayerService::Client`的`notify()`方法, 在`prepareAsync()`完成后可以看到此类的参与.

### `NuPlayerDriver::setDataSource()`
而`MediaPlayerService::Client::setDataSource()`中的`p->setDataSource()`是对`NuPlayerDriver`(`MediaPlayerBase`的子类)的进一步设置:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
status_t NuPlayerDriver::setDataSource(int fd, int64_t offset, int64_t length) {
    ... ...
    mState = STATE_SET_DATASOURCE_PENDING;
    mPlayer->setDataSourceAsync(fd, offset, length);
    while (mState == STATE_SET_DATASOURCE_PENDING) {
        mCondition.wait(mLock);
    }
    return mAsyncResult;
}
```

### `NuPlayer::setDataSourceAsync()`
因为调用`NuPlayer`的`setDataSourceAsync()`方法是异步的, 此时通过`mCondition.wait()`等待`NuPlayer`消息.
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::setDataSourceAsync(const sp<IStreamSource> &source) {
    sp<AMessage> msg = new AMessage(kWhatSetDataSource, this);
    sp<AMessage> notify = new AMessage(kWhatSourceNotify, this);
    msg->setObject("source", new StreamingSource(notify, source));
    msg->post();
    mDataSourceType = DATA_SOURCE_TYPE_STREAM;
}

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        ... ...
        case kWhatSetDataSource:
        {
            ... ...
            if (obj != NULL) {
                Mutex::Autolock autoLock(mSourceLock);
                mSource = static_cast<Source *>(obj.get());
            } else ... ...
            sp<NuPlayerDriver> driver = mDriver.promote();
            if (driver != NULL) {
                driver->notifySetDataSourceCompleted(err);
            }
            break;
        }
        ... ...
    }
}
```
`notifySetDataSourceCompleted()`负责完成对`NuPlayerDriver`的通知:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
void NuPlayerDriver::notifySetDataSourceCompleted(status_t err) {
    mState = (err == OK) ? STATE_UNPREPARED : STATE_IDLE;
    mCondition.broadcast();
}
```

上文`NuPlayerDriver::setDataSource()`通过`mCondition.wait(mLock)`等待`NuPlayer`完成, 因此`NuPlayerDriver::notifySetDataSourceCompleted()`执行完成后 上文的`NuPlayerDriver::setDataSource()`返回.

### `GenericSource`的创建
根据上文, `mPlayer`的类型显然是`NuPlayer`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::setDataSourceAsync(int fd, int64_t offset, int64_t length) {
    ... ...
    sp<GenericSource> source =
            new GenericSource(notify, mUIDValid, mUID, mMediaClock);
    ... ...
    status_t err = source->setDataSource(fd, offset, length);
    ... ...
}
```
此处构造了`GenericSource`, 通过`setDataSource()`为其设置文件描述符:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/GenericSource.cpp
status_t NuPlayer::GenericSource::setDataSource(
        int fd, int64_t offset, int64_t length) {
    ... ...
    resetDataSource();
    mFd.reset(dup(fd));
    mOffset = offset;
    mLength = length;
    ... ...
}
```
上层传递的文件描述符被设置在了`GenericSource`的`mFd`中, 而`GenericSource`在`NuPlayer::setDataSourceAsync()`时通过`kWhatSetDataSource`消息通知`NuPlayer::onMessageReceived()`将其记录在`NuPlayer`的`mSource`中.


回到上文的`MediaPlayerService::Client::setDataSource()`:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
status_t MediaPlayerService::Client::setDataSource(int fd, int64_t offset, int64_t length)
{
    ... ...
    player_type playerType = MediaPlayerFactory::getPlayerType(this,
                                                               fd,
                                                               offset,
                                                               length);
    sp<MediaPlayerBase> p = setDataSource_pre(playerType);
    ... ...
    return mStatus = setDataSource_post(p, p->setDataSource(fd, offset, length));
    ... ...
}

status_t MediaPlayerService::Client::setDataSource_post(
        const sp<MediaPlayerBase>& p,
        status_t status)
{
    ... ...
    if (mRetransmitEndpointValid) {
        status = p->setRetransmitEndpoint(&mRetransmitEndpoint);
        if (status != NO_ERROR) {
            ALOGE("setRetransmitEndpoint error: %d", status);
        }
    }

    if (status == OK) {
        Mutex::Autolock lock(mLock);
        mPlayer = p;
    }
    return status;
}
```
`MediaPlayerService::Client::setDataSource()`最后通过`setDataSource_post()`将创建的`NuPlayerDriver`设置在`MediaPlayerService::Client`的`mPlayer`.


## MediaPlayer.setDisplay()
回到`VidewView.openVideo()`中, `mMediaPlayer.setDisplay()`将自身的`mSurfaceHolder`设置给了`MediaPlayer`:
```
// frameworks/base/media/java/android/media/MediaPlayer.java
    public void setDisplay(SurfaceHolder sh) {
        mSurfaceHolder = sh;
        Surface surface;
        if (sh != null) {
            surface = sh.getSurface();
        } else {
            surface = null;
        }
        _setVideoSurface(surface);
        updateSurfaceScreenOn();
    }
```
显然`_setVideoSurface()`也是Native方法, 直接查看代码:
```
// frameworks/base/media/jni/android_media_MediaPlayer.cpp
static void
android_media_MediaPlayer_setVideoSurface(JNIEnv *env, jobject thiz, jobject jsurface)
{
    setVideoSurface(env, thiz, jsurface, true /* mediaPlayerMustBeAlive */);
}

static void
setVideoSurface(JNIEnv *env, jobject thiz, jobject jsurface, jboolean mediaPlayerMustBeAlive)
{
    sp<MediaPlayer> mp = getMediaPlayer(env, thiz);
    ... ...
    decVideoSurfaceRef(env, thiz);
    sp<IGraphicBufferProducer> new_st;
    if (jsurface) {
        sp<Surface> surface(android_view_Surface_getSurface(env, jsurface));
        if (surface != NULL) {
            new_st = surface->getIGraphicBufferProducer();
            ... ...
            new_st->incStrong((void*)decVideoSurfaceRef);
        } else ... ...
    }
    env->SetLongField(thiz, fields.surface_texture, (jlong)new_st.get());
    mp->setVideoSurfaceTexture(new_st);
}
```
通过`android_view_Surface_getSurface()`将上层的`Surface`(Java)转换为底层的`Surface`(Native), 然后将该`Surface`(Native)指针记录在`MediaPlayer.mNativeSurfaceTexture`(Java)中, 最后通过`mp->setVideoSurfaceTexture()`也就是`MediaPlayer::setVideoSurfaceTexture()`设置从`Surface`(Native)调用`getIGraphicBufferProducer()`获得的`IGraphicBufferProducer`给底层的MediaPlayer(Native):
```
// frameworks/av/media/libmedia/mediaplayer.cpp
status_t MediaPlayer::setVideoSurfaceTexture(
        const sp<IGraphicBufferProducer>& bufferProducer)
{
    ... ...
    return mPlayer->setVideoSurfaceTexture(bufferProducer);
}
```
`mPlayer->setVideoSurfaceTexture()`通过Binder调用到:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
status_t MediaPlayerService::Client::setVideoSurfaceTexture(
        const sp<IGraphicBufferProducer>& bufferProducer)
{
    ... ...
    sp<MediaPlayerBase> p = getPlayer();
    ... ...
    sp<ANativeWindow> anw;
    if (bufferProducer != NULL) {
        anw = new Surface(bufferProducer, true /* controlledByApp */);
        status_t err = nativeWindowConnect(anw.get(), "setVideoSurfaceTexture");
        ... ...
    }
    status_t err = p->setVideoSurfaceTexture(bufferProducer);
    mLock.lock();
    disconnectNativeWindow_l();
    if (err == OK) {
        mConnectedWindow = anw;
        mConnectedWindowBinder = binder;
        mLock.unlock();
    } else ... ...
```

### `NuPlayerDriver::setVideoSurfaceTexture()`
通过上层传递的`bufferProducer`创建了新的`Surface`, 又通过`disconnectNativeWindow_l()`断开了`bufferProducer`与应用持有的`Surface`(Native)的联系, 然后将新创建的`Surface`保存到`Client::mConnectedWindow`, 这意味着, `mediaserver`直接负责生产`GraphicBuffer`给原本属于应用持有的`Surface`. 继续看此处的`p->setVideoSurfaceTexture()`, `p`的类型为`MediaPlayerBase`, 也就是`NuPlayerDriver`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
status_t NuPlayerDriver::setVideoSurfaceTexture(
        const sp<IGraphicBufferProducer> &bufferProducer) {
    mSetSurfaceInProgress = true;
    mPlayer->setVideoSurfaceTextureAsync(bufferProducer);
    while (mSetSurfaceInProgress) {
        mCondition.wait(mLock);
    }
    return OK;
}
```

### `NuPlayer::setVideoSurfaceTextureAsync()`
如上文, `mPlayer`的类型是`NuPlayer`, 和上文的`NuPlayer::setDataSource()`类似, `setVideoSurfaceTextureAsync()`也是异步的:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::setVideoSurfaceTextureAsync(
        const sp<IGraphicBufferProducer> &bufferProducer) {
    sp<AMessage> msg = new AMessage(kWhatSetVideoSurface, this);

    if (bufferProducer == NULL) {
        msg->setObject("surface", NULL);
    } else {
        msg->setObject("surface", new Surface(bufferProducer, true /* controlledByApp */));
    }
    msg->post();
}

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatSetDataSource:
        ... ...
        case kWhatSetVideoSurface:
        {

            sp<RefBase> obj;
            CHECK(msg->findObject("surface", &obj));
            sp<Surface> surface = static_cast<Surface *>(obj.get());
            if (mSource == NULL || !mStarted || mSource->getFormat(false /* audio */) == NULL
                    // NOTE: mVideoDecoder's mSurface is always non-null
                    || (mVideoDecoder != NULL && mVideoDecoder->setVideoSurface(surface) == OK)) {
                performSetSurface(surface);
                break;
            }
            ... ...
        }
        ... ...
    }
}
void NuPlayer::performSetSurface(const sp<Surface> &surface) {
    mSurface = surface;
    setVideoScalingMode(mVideoScalingMode);
    if (mDriver != NULL) {
        sp<NuPlayerDriver> driver = mDriver.promote();
        if (driver != NULL) {
            driver->notifySetSurfaceComplete();
        }
    }
}
```
注意, 在`NuPlayer::onMessageReceived()`响应消息`kWhatSetVideoSurface`时, 条件`!mStarted`成立. `NuPlayer`保存上层的`Surface`即`mediaserver`使用应用传递的`IGraphicBufferProducer`所创建的`Surface`到`mSurface`, 并调用`NuPlayerDriver::notifySetSurfaceComplete()`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
void NuPlayerDriver::notifySetSurfaceComplete() {
    ... ...
    mSetSurfaceInProgress = false;
    mCondition.broadcast();
}
```
同理可知`NuPlayerDriver::setVideoSurfaceTexture()`返回.

## `MediaPlayer.prepareAsync()`
回到`VidewView.openVideo()`中, `mMediaPlayer.prepareAsync()`即开始通知播放器做准备工作:
```
// frameworks/base/media/java/android/media/MediaPlayer.java
public class MediaPlayer extends PlayerBase
                         implements SubtitleController.Listener
                                  , VolumeAutomation
                                  , AudioRouting
{
    .. ...
    public native void prepareAsync() throws IllegalStateException;
```
`prepareAsync()`是个本地方法:
```
// frameworks/base/media/jni/android_media_MediaPlayer.cpp
static const JNINativeMethod gMethods[] = {
    ... ...
    {"prepareAsync",        "()V",                              (void *)android_media_MediaPlayer_prepareAsync},
    ... ...
};

static void
android_media_MediaPlayer_prepareAsync(JNIEnv *env, jobject thiz)
{
    sp<MediaPlayer> mp = getMediaPlayer(env, thiz);
    ... ...
    // Handle the case where the display surface was set before the mp was
    // initialized. We try again to make it stick.
    sp<IGraphicBufferProducer> st = getVideoSurfaceTexture(env, thiz);
    mp->setVideoSurfaceTexture(st);
    process_media_player_call( env, thiz, mp->prepareAsync(), "java/io/IOException", "Prepare Async failed." );
}
```

### `NuPlayerDriver::prepareAsync()`
`NuPlayerDriver::setVideoSurfaceTexture()`的调用是多余的, 但并没什么坏处:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
status_t NuPlayerDriver::prepareAsync() {
    ... ..
    switch (mState) {
        case STATE_UNPREPARED:
            mState = STATE_PREPARING;
            mIsAsyncPrepare = true;
            mPlayer->prepareAsync();
            return OK;
        case STATE_STOPPED:
            ... ...
        default:
            return INVALID_OPERATION;
    };
}

```

### `NuPlayer::prepareAsync()`
播放器的状态如果是还未播放过, 那肯定是`STATE_UNPREPARED`, `STATE_STOPPED`的情景这里不讨论:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::prepareAsync() {
    ... ...
    (new AMessage(kWhatPrepare, this))->post();
}

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatSetDataSource:
        ... ...
        case kWhatPrepare:
        {
            ... ...
            mSource->prepareAsync();
            break;
        }
        ... ...
```
如上文`mSource`的类型是`GenericSource`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/GenericSource.cpp
void NuPlayer::GenericSource::prepareAsync() {
    ... ...
    if (mLooper == NULL) {
        mLooper = new ALooper;
        mLooper->setName("generic");
        mLooper->start();
        mLooper->registerHandler(this);
    }
    sp<AMessage> msg = new AMessage(kWhatPrepareAsync, this);
    msg->post();
}
void NuPlayer::GenericSource::onMessageReceived(const sp<AMessage> &msg) {
    Mutex::Autolock _l(mLock);
    switch (msg->what()) {
        case kWhatPrepareAsync:
        {
            onPrepareAsync();
            break;
        }
        ... ...
    }
}

void NuPlayer::GenericSource::onPrepareAsync() {
    ... ...
    // delayed data source creation
    if (mDataSource == NULL) {
        ... ...
    }
    ... ...
    // init extractor from data source
    status_t err = initFromDataSource();
    ... ...
    if (mVideoTrack.mSource != NULL) {
        ... ...
    }
    notifyFlagsChanged(
            // FLAG_SECURE will be known if/when prepareDrm is called by the app
            // FLAG_PROTECTED will be known if/when prepareDrm is called by the app
            FLAG_CAN_PAUSE |
            FLAG_CAN_SEEK_BACKWARD |
            FLAG_CAN_SEEK_FORWARD |
            FLAG_CAN_SEEK);
    finishPrepareAsync();
    ... ...
}
void NuPlayer::GenericSource::finishPrepareAsync() {
    ... ...
    status_t err = startSources();
    ... ...
    if (mIsStreaming) {
        ... ...
    } else {
        notifyPrepared();
    }
    ... ...
}
```
大体说下这里, 主要是准备`DataSource`并设置给`mDataSource`, 该步骤不能失败, 如果成功, 且初始化没有问题, 则最终通过父类`NuPlayer::Source`的`notifyPrepared()`方法通知`NuPlayerDriver`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::Source::notifyPrepared(status_t err) {
    ... ...
    sp<AMessage> notify = dupNotify();
    notify->setInt32("what", kWhatPrepared);
    notify->setInt32("err", err);
    notify->post();
}
```

`NuPlayerDriver`处理`NuPlayer::Source::kWhatPrepared`消息:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        ... ...
        case Source::kWhatPrepared:
        {
            ... ...
            if (err != OK) {
                ... ...
            } else {
                mPrepared = true;
            }

            sp<NuPlayerDriver> driver = mDriver.promote();
            if (driver != NULL) {
                ... ...
                if (mSource->getDuration(&durationUs) == OK) {
                    driver->notifyDuration(durationUs);
                }
                driver->notifyPrepareCompleted(err);
            }

            break;
        }
        ... ...
    }
}
```
`NuPlayer`通过`NuPlayerDriver::notifyPrepareCompleted()`通知完成操作:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp

void NuPlayerDriver::notifyPrepareCompleted(status_t err) {
    ... ...
    mAsyncResult = err;
    if (err == OK) {
        // update state before notifying client, so that if client calls back into NuPlayerDriver
        // in response, NuPlayerDriver has the right state
        mState = STATE_PREPARED;
        if (mIsAsyncPrepare) {
            notifyListener_l(MEDIA_PREPARED);
        }
    } else ... ...
    sp<MetaData> meta = mPlayer->getFileMeta();
    int32_t loop;
    if (meta != NULL
            && meta->findInt32(kKeyAutoLoop, &loop) && loop != 0) {
        mAutoLoop = true;
    }
    mCondition.broadcast();
}
```
然而, `mCondition.broadcast()`的消息并没有对应的`mCondition.wait()`, 这是因为`NuPlayerDriver`实际上是通过`notifyListener_l()`同时上层的, 消息是`MEDIA_PREPARED`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
void NuPlayerDriver::notifyListener_l(
    int msg, int ext1, int ext2, const Parcel *in) {
    ALOGV("notifyListener_l(%p), (%d, %d, %d, %d), loop setting(%d, %d)",
            this, msg, ext1, ext2, (in == NULL ? -1 : (int)in->dataSize()), mAutoLoop, mLooping);
    switch (msg) {
        case MEDIA_PLAYBACK_COMPLETE:
        ... ...
    }
    mLock.unlock();
    sendEvent(msg, ext1, ext2, in);
    mLock.lock();
}
```
此处的`sendEvent()`方法是`NuPlayerDriver`父类`MediaPlayerBase`的:
```
// frameworks/av/include/media/MediaPlayerInterface.h
class MediaPlayerBase : public RefBase
{
public:
    ... ...
    void        sendEvent(int msg, int ext1=0, int ext2=0,
                          const Parcel *obj=NULL) {
        sp<Listener> listener;
        {
            Mutex::Autolock autoLock(mNotifyLock);
            listener = mListener;
        }
        if (listener != NULL) {
            listener->notify(msg, ext1, ext2, obj);
        }
    }
    ... ...
```
`mPlayer`的类型是`MediaPlayerBase::Listener`, 其还有一个子实现:`MediaPlayerService::Client::Listener`:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.h
class MediaPlayerService : public BnMediaPlayerService
{
    ... ...
    class Client : public BnMediaPlayer {
        ... ...
        class Listener : public MediaPlayerBase::Listener {
        public:
            Listener(const wp<Client> &client) : mClient(client) {}
            virtual ~Listener() {}
            virtual void notify(int msg, int ext1, int ext2, const Parcel *obj) {
                sp<Client> client = mClient.promote();
                if (client != NULL) {
                    client->notify(msg, ext1, ext2, obj);
                }
            }
        private:
            wp<Client> mClient;
        };
        ... ...
```
综上所述`MediaPlayerService::Client::notify()`被调用:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
void MediaPlayerService::Client::notify(
        int msg, int ext1, int ext2, const Parcel *obj)
{
    sp<IMediaPlayerClient> c;
    sp<Client> nextClient;
    status_t errStartNext = NO_ERROR;
    {
        Mutex::Autolock l(mLock);
        c = mClient;
        ... ...
    }
    ... ...
    if (c != NULL) {
        ALOGV("[%d] notify (%d, %d, %d)", mConnId, msg, ext1, ext2);
        c->notify(msg, ext1, ext2, obj);
    }
}
```
`IMediaPlayerClient`将调用回应用的`MediaPlayer`, 因此应用的`MediaPlayer::notify()`通过Binder被调用:
```
// frameworks/av/media/libmedia/mediaplayer.cpp
void MediaPlayer::notify(int msg, int ext1, int ext2, const Parcel *obj)
{
    ... ...
    switch (msg) {
    case MEDIA_NOP: // interface test message
        break;
    case MEDIA_PREPARED:
        ALOGV("MediaPlayer::notify() prepared");
        mCurrentState = MEDIA_PLAYER_PREPARED;
        if (mPrepareSync) {
            ALOGV("signal application thread");
            mPrepareSync = false;
            mPrepareStatus = NO_ERROR;
            mSignal.signal();
        }
        break;
        ... ...
    }
    sp<MediaPlayerListener> listener = mListener;
    if (locked) mLock.unlock();
    // this prevents re-entrant calls into client code
    if ((listener != 0) && send) {
        Mutex::Autolock _l(mNotifyLock);
        ALOGV("callback application");
        listener->notify(msg, ext1, ext2, obj);
        ALOGV("back from callback");
    }
}
```
`mSignal.signal()`此场景下没有流程在等待(只有`MediaPlayer::notify()`时才等待), 此时`mListener`的类型是`MediaPlayerListener`, 其实现是`JNIMediaPlayerListener`, 因此:
```
// frameworks/base/media/jni/android_media_MediaPlayer.cpp
void JNIMediaPlayerListener::notify(int msg, int ext1, int ext2, const Parcel *obj)
{
    JNIEnv *env = AndroidRuntime::getJNIEnv();
    if (obj && obj->dataSize() > 0) {
        jobject jParcel = createJavaParcelObject(env);
        if (jParcel != NULL) {
            Parcel* nativeParcel = parcelForJavaObject(env, jParcel);
            nativeParcel->setData(obj->data(), obj->dataSize());
            env->CallStaticVoidMethod(mClass, fields.post_event, mObject,
                    msg, ext1, ext2, jParcel);
            env->DeleteLocalRef(jParcel);
        }
    } else {
        env->CallStaticVoidMethod(mClass, fields.post_event, mObject,
                msg, ext1, ext2, NULL);
    }
    if (env->ExceptionCheck()) {
        ALOGW("An exception occurred while notifying an event.");
        LOGW_EX(env);
        env->ExceptionClear();
    }
}
```

```
// frameworks/base/media/java/android/media/MediaPlayer.java
public class MediaPlayer extends PlayerBase
                         implements SubtitleController.Listener
                                  , VolumeAutomation
                                  , AudioRouting
{
    ... ...
    private static void postEventFromNative(Object mediaplayer_ref,
                                            int what, int arg1, int arg2, Object obj)
    {
        final MediaPlayer mp = (MediaPlayer)((WeakReference)mediaplayer_ref).get();
        ... ...
        switch (what) {
            ... ...
        case MEDIA_PREPARED:
            // By this time, we've learned about DrmInfo's presence or absence. This is meant
            // mainly for prepareAsync() use case. For prepare(), this still can run to a race
            // condition b/c MediaPlayerNative releases the prepare() lock before calling notify
            // so we also set mDrmInfoResolved in prepare().
            synchronized (mp.mDrmLock) {
                mp.mDrmInfoResolved = true;
            }
            break;

        }
        if (mp.mEventHandler != null) {
            Message m = mp.mEventHandler.obtainMessage(what, arg1, arg2, obj);
            mp.mEventHandler.sendMessage(m);
        }
    }
```
`mEventHandler`的类型是`MediaPlayer.EventHandler`故:
```
// frameworks/base/media/java/android/media/MediaPlayer.java

    private class EventHandler extends Handler
    {
        private MediaPlayer mMediaPlayer;

        public EventHandler(MediaPlayer mp, Looper looper) {
            super(looper);
            mMediaPlayer = mp;
        }

        @Override
        public void handleMessage(Message msg) {
            if (mMediaPlayer.mNativeContext == 0) {
                Log.w(TAG, "mediaplayer went away with unhandled events");
                return;
            }
            switch(msg.what) {
            case MEDIA_PREPARED:
                try {
                    scanInternalSubtitleTracks();
                } catch (RuntimeException e) {
                    // send error message instead of crashing;
                    // send error message instead of inlining a call to onError
                    // to avoid code duplication.
                    Message msg2 = obtainMessage(
                            MEDIA_ERROR, MEDIA_ERROR_UNKNOWN, MEDIA_ERROR_UNSUPPORTED, null);
                    sendMessage(msg2);
                }

                OnPreparedListener onPreparedListener = mOnPreparedListener;
                if (onPreparedListener != null)
                    onPreparedListener.onPrepared(mMediaPlayer);
                return;
                ... ...
```
而`mOnPreparedListener`是上层通过`setOnPreparedListener()`设置的. 其实现:
```
// frameworks/base/core/java/android/widget/VideoView.java
    @UnsupportedAppUsage
    MediaPlayer.OnPreparedListener mPreparedListener = new MediaPlayer.OnPreparedListener() {
        public void onPrepared(MediaPlayer mp) {
            mCurrentState = STATE_PREPARED;

            // Get the capabilities of the player for this stream
            Metadata data = mp.getMetadata(MediaPlayer.METADATA_ALL,
                                      MediaPlayer.BYPASS_METADATA_FILTER);
            ... ...
            mVideoWidth = mp.getVideoWidth();
            mVideoHeight = mp.getVideoHeight();
            ... ...
            if (mVideoWidth != 0 && mVideoHeight != 0) {
                ... ...
            } else {
                // We don't know the video size yet, but should start anyway.
                // The video size might be reported to us later.
                if (mTargetState == STATE_PLAYING) {
                    start();
                }
            }
        }
    };
```
此时视频的播放仍未开始, 因此`if (mVideoWidth != 0 && mVideoHeight != 0)`条件不成立, 且此时`if (mTargetState == STATE_PLAYING)`条件也不满足.

`start()`后续再分析.