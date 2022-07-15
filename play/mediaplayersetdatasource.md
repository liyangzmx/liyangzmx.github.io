- [`MediaPlayer.setDataSource()`](#mediaplayersetdatasource)
    - [Native层`MediaPlayer`的创建](#native层mediaplayer的创建)
    - [`MediaPlayer::setDataSource()`](#mediaplayersetdatasource-1)
    - [`MediaPlayerService::create()`创建播放器](#mediaplayerservicecreate创建播放器)
      - [`MediaPlayerService::Client`的创建](#mediaplayerserviceclient的创建)
        - [`NuPlayerDriver`的创建](#nuplayerdriver的创建)
        - [`NuPlayer`的创建与初始化](#nuplayer的创建与初始化)
        - [`AudioOutput`的创建与配置](#audiooutput的创建与配置)
      - [`NuPlayerDriver::setDataSource()`](#nuplayerdriversetdatasource)
      - [`NuPlayer::setDataSourceAsync()`](#nuplayersetdatasourceasync)
      - [`GenericSource`的创建](#genericsource的创建)


# `MediaPlayer.setDataSource()`
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

### `MediaPlayerService::create()`创建播放器
#### `MediaPlayerService::Client`的创建
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

##### `NuPlayerDriver`的创建
`setDataSource_pre()`时做了很多工作, 但主要还是创建了`MediaPlayerBase`, `playerType`确定了后续需要创建的播放器的类型, Android目前的播放器工厂类默认是`NuPlayerFactory`(还有一种是`TestPlayerFactory`):
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
sp<MediaPlayerBase> MediaPlayerService::Client::setDataSource_pre(
        player_type playerType)
{
    ... ...
    sp<MediaPlayerBase> p = createPlayer(playerType);
    ... ...
    if (!p->hardwareOutput()) {
        mAudioOutput = new AudioOutput(mAudioSessionId, mAttributionSource,
                mAudioAttributes, mAudioDeviceUpdatedListener);
        static_cast<MediaPlayerInterface*>(p.get())->setAudioSink(mAudioOutput);
    }

    return p;
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

##### `NuPlayer`的创建与初始化
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

##### `AudioOutput`的创建与配置
回到`MediaPlayerService::Client::setDataSource_pre()`中, `AudioOutput`被创建, 且通过`static_cast<MediaPlayerInterface*>(p.get())->setAudioSink(mAudioOutput)`进行配置:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::setAudioSink(const sp<MediaPlayerBase::AudioSink> &sink) {
    sp<AMessage> msg = new AMessage(kWhatSetAudioSink, this);
    msg->setObject("sink", sink);
    msg->post();
}

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatSetDataSource:
        ... ...
        case kWhatSetAudioSink:
        {
            ... ...
            mAudioSink = static_cast<MediaPlayerBase::AudioSink *>(obj.get());
            break;
        }
        ... ...
```
此时`MediaPlayerService::Client`创建的`AudioOutput`被设置在`NuPlayer`的`mAudioSink`.

#### `NuPlayerDriver::setDataSource()`
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

#### `NuPlayer::setDataSourceAsync()`
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

#### `GenericSource`的创建
根据上文, `mPlayer`的类型显然是`NuPlayer`, 回到`uPlayer::setDataSourceAsync()`:
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
`onPrepareAsync()`构造了`GenericSource`, 通过`setDataSource()`为其设置文件描述符:
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