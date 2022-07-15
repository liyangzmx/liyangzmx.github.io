
- [`MediaPlayer.setDisplay()`](#mediaplayersetdisplay)
    - [`NuPlayerDriver::setVideoSurfaceTexture()`](#nuplayerdriversetvideosurfacetexture)
    - [`NuPlayer::setVideoSurfaceTextureAsync()`](#nuplayersetvideosurfacetextureasync)

# `MediaPlayer.setDisplay()`
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