- [系统相册播放相机录制的视频](#系统相册播放相机录制的视频)
- [MediaPlayer的创建与配置](#mediaplayer的创建与配置)
  - [`MediaPlayer.setDataSource()`](#mediaplayersetdatasource)
  - [Native层`MediaPlayer`的创建](#native层mediaplayer的创建)
  - [`mediaserver`中`MediaPlayerService::Client`的创建](#mediaserver中mediaplayerserviceclient的创建)
  - [`mediaserver`中`NuPlayerDriver`的创建](#mediaserver中nuplayerdriver的创建)
  - [`mediaserver`中`NuPlayerDriver`的`NuPlayer`的创建](#mediaserver中nuplayerdriver的nuplayer的创建)
  - [`mediaserver`中`GenericSource`的创建](#mediaserver中genericsource的创建)
- [MediaPlayer.setDisplay()](#mediaplayersetdisplay)

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

### `MediaPlayer.setDataSource()`
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
这里`env->SetLongField()`设置的正是 `mNativeContext`. 回到`android_media_MediaPlayer_setDataSourceFD()`, 此时`MediaPlayer::setDataSource()`被调用:
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

### `mediaserver`中`MediaPlayerService::Client`的创建
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
`Client`可通过`mService`与`MediaPlayerService`交互. 综上所述`IMediaPlayer`的实现是`MediaPlayerService::Client`, 后续应用中的`MediaPlayer`(Native)将通过Binder与此`Client`通信.回到`MediaPlayer::setDataSource()`中, 创建完`IMediaPlayer`后调用`player->setDataSource()`:
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

### `mediaserver`中`NuPlayerDriver`的创建
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
    ... ...
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

### `mediaserver`中`NuPlayerDriver`的`NuPlayer`的创建
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
`NuPlayer`通过`mDriver`持有`NuPlayerDriver`. 此时`NuPlayerDriver`构造完成, 且其继承关系:`MediaPlayerBase` -> `MediaPlayerInterface` -> `NuPlayerDriver`

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

### `mediaserver`中`GenericSource`的创建
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

`MediaPlayerService::Client::setDataSource()`最后通过
```
status_t MediaPlayerService::Client::setDataSource_post(
        const sp<MediaPlayerBase>& p,
        status_t status)
{
    ... ...

    if (status == OK) {
        Mutex::Autolock lock(mLock);
        mPlayer = p;
    }
    return status;
}
```
将创建的`NuPlayerDriver`设置在`MediaPlayerService::Client`的`mPlayer`.

`MediaPlayer::setDataSource()`最后调用的`attachNewPlayer()`方法, 又一次将`IMediaPlayer`保存到`MediaPlayer::mPlayer`中(?):
```?
status_t MediaPlayer::attachNewPlayer(const sp<IMediaPlayer>& player)
{
    status_t err = UNKNOWN_ERROR;
    sp<IMediaPlayer> p;
    { // scope for the lock
        ... ...
        p = mPlayer;
        mPlayer = player;
        if (player != 0) {
            mCurrentState = MEDIA_PLAYER_INITIALIZED;
            err = NO_ERROR;
        } else ... ...
    ... ...
}
```

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
通过上层传递的`bufferProducer`创建了新的`Surface`, 又通过`disconnectNativeWindow_l()`断开了`bufferProducer`与应用持有的`Surface`(Native)的联系, 然后将新创建的`Surface`保存到`Client::mConnectedWindow`, 这意味着, `mediaserver`直接负责生产`GraphicBuffer`给原本属于应用持有的`Surface`. 继续看此处的`p->setVideoSurfaceTexture()`, `p`的类型为`MediaPlayerBase`, 