- [`MediaPlayer.prepareAsync()`](#mediaplayerprepareasync)
  - [`NuPlayerDriver::prepareAsync()`](#nuplayerdriverprepareasync)
  - [`NuPlayer::prepareAsync()`](#nuplayerprepareasync)
  - [`GenericSource::prepareAsync()`](#genericsourceprepareasync)
  - [用于文件读取的`IDataSource`的创建](#用于文件读取的idatasource的创建)
  - [`initFromDataSource()`对解封装器的创建](#initfromdatasource对解封装器的创建)
    - [用于解封装的`MediaExtractor`的创建](#用于解封装的mediaextractor的创建)
    - [`media.extractor`对封装插件的加载](#mediaextractor对封装插件的加载)
    - [`MPEG4Extractor.cpp:Sniff()`的调用](#mpeg4extractorcppsniff的调用)
    - [`MPEG4Extractor.cpp:CreateExtractor()`创建`CMediaExtractor`](#mpeg4extractorcppcreateextractor创建cmediaextractor)
    - [媒体文件元数据信息`MetaData`的获取](#媒体文件元数据信息metadata的获取)
    - [媒体文件中`MPEG4Extractor::Track`数量的获取](#媒体文件中mpeg4extractortrack数量的获取)
    - [`IMediaSource`的获取](#imediasource的获取)
    - [媒体文件中`MPEG4Extractor::Track`元数据`MetaData`的获取](#媒体文件中mpeg4extractortrack元数据metadata的获取)
    - [音频`GenericSource::Track`的创建](#音频genericsourcetrack的创建)
    - [视频`GenericSource::Track`的创建](#视频genericsourcetrack的创建)
  - [`GenericSource::finishPrepareAsync()`](#genericsourcefinishprepareasync)
    - [`NuPlayer::GenericSource::startSources()`创建`Extractor`的缓冲区](#nuplayergenericsourcestartsources创建extractor的缓冲区)
    - [`NuPlayer::Source::notifyPrepared()`发出`kWhatPrepared`消息通知准备完成](#nuplayersourcenotifyprepared发出kwhatprepared消息通知准备完成)
    - [`NuPlayer::GenericSource::postReadBuffer()`开始预读取解码数据](#nuplayergenericsourcepostreadbuffer开始预读取解码数据)


# `MediaPlayer.prepareAsync()`
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

## `NuPlayerDriver::prepareAsync()`
`NuPlayerDriver::setVideoSurfaceTexture()`的调用是多余的, 但并没什么坏处:  
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
status_t NuPlayerDriver::prepareAsync() {
    ...
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

## `NuPlayer::prepareAsync()`
播放器的状态如果是还未播放过, 那肯定是`STATE_UNPREPARED`, `STATE_STOPPED`的情景这里不讨论:  
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
void NuPlayer::prepareAsync() {
    ... ...
    (new AMessage(kWhatPrepare, this))->post();
}
```
## `GenericSource::prepareAsync()`
```
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
## 用于文件读取的`IDataSource`的创建
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
        mIsSecure = false;
        if (!mUri.empty()) {
            ...
        } else {
            if (property_get_bool("media.stagefright.extractremote", true) &&
                    !PlayerServiceFileSource::requiresDrm(
                            mFd.get(), mOffset, mLength, nullptr /* mime */)) {
                sp<IBinder> binder = defaultServiceManager()->getService(String16("media.extractor"));
                sp<IMediaExtractorService> mediaExService(interface_cast<IMediaExtractorService>(binder));
                ...
                mediaExService->makeIDataSource(base::unique_fd(dup(mFd.get())), mOffset, mLength, &source);
                ...
                mDataSource = CreateDataSourceFromIDataSource(source);
                ...
            }
            ...
        }
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
```
`mediaExService->makeIDataSource()`将调用到`media.extractor`服务, 对应的函数是: `MediaExtractorService::makeIDataSource(`:  
```
// frameworks/av/services/mediaextractor/MediaExtractorService.cpp
::android::binder::Status MediaExtractorService::makeIDataSource(
        base::unique_fd fd,
        int64_t offset,
        int64_t length,
        ::android::sp<::android::IDataSource>* _aidl_return) {
    sp<DataSource> source = DataSourceFactory::getInstance()->CreateFromFd(fd.release(), offset, length);
    *_aidl_return = CreateIDataSourceFromDataSource(source);
    return binder::Status::ok();
}
```
此处分两步:
* `DataSource`的创建
* `DataSource`需要通过一个`IDataSource`接口返回给`mediaserver`

首先看创建:  
```
// frameworks/av/media/libdatasource/DataSourceFactory.cpp
sp<DataSource> DataSourceFactory::CreateFromFd(int fd, int64_t offset, int64_t length) {
    sp<FileSource> source = new FileSource(fd, offset, length);
    return source->initCheck() != OK ? nullptr : source;
}
```
`FileSource`是`DataSource`的子类, 该数据源主要针对文件类型. 继续看`IDataSource`的创建:  
```
// frameworks/av/media/libstagefright/InterfaceUtils.cpp
sp<IDataSource> CreateIDataSourceFromDataSource(const sp<DataSource> &source) {
    ...
    return RemoteDataSource::wrap(source);
}

// frameworks/av/media/libstagefright/include/media/stagefright/RemoteDataSource.h
class RemoteDataSource : public BnDataSource {
public:
    static sp<IDataSource> wrap(const sp<DataSource> &source) {
        ...
        return new RemoteDataSource(source);
    }
    ...
private:
    ...
    explicit RemoteDataSource(const sp<DataSource> &source) {
        Mutex::Autolock lock(mLock);
        mSource = source;
        sp<MemoryDealer> memoryDealer = new MemoryDealer(kBufferSize, "RemoteDataSource");
        mMemory = memoryDealer->allocate(kBufferSize);
        if (mMemory.get() == nullptr) {
            ALOGE("Failed to allocate memory!");
        }
        mName = String8::format("RemoteDataSource(%s)", mSource->toString().string());
    }
    ...
}
```

以上过程几个重要环节:
* 首先创建`RemoteDataSource`, 其实现了`IDataSource`接口, 用于响应客户端`mediaserver`的后续请求
* 在`RemoteDataSource`中, 创建了`MemoryDealer`内存分配器
* 然后分配了一定量的内存(64kB), 用户后续从DataSource中读取数据

回到`GenericSource::onPrepareAsync()`中, 通过`CreateDataSourceFromIDataSource()`创建了`mediaserver`中本地的`DataSource`:  
```
// frameworks/av/media/libstagefright/InterfaceUtils.cpp
sp<DataSource> CreateDataSourceFromIDataSource(const sp<IDataSource> &source) {
    if (source == nullptr) {
        return nullptr;
    }
    return new TinyCacheSource(new CallbackDataSource(source));
}

// frameworks/av/media/libstagefright/CallbackDataSource.cpp
CallbackDataSource::CallbackDataSource(
    const sp<IDataSource>& binderDataSource)
    : mIDataSource(binderDataSource),
      mIsClosed(false) {
    // Set up the buffer to read into.
    mMemory = mIDataSource->getIMemory();
    mName = String8::format("CallbackDataSource(%d->%d, %s)",
            getpid(),
            IPCThreadState::self()->getCallingPid(),
            mIDataSource->toString().string());

}
```
本地的`DataSource`类型为`TinyCacheSource`, 其`mSource`的成员为`CallbackDataSource`, 而`CallbackDataSource`的`mSource`为`media.extractor`返回的`IDataSource`.

`CallbackDataSource`之所以是这个名字是因为其持有`IMemory`, 该接口是通过`mIDataSource->getIMemory()`获得的:  
```
// frameworks/av/media/libstagefright/include/media/stagefright/RemoteDataSource.h
class RemoteDataSource : public BnDataSource {
    ...
    virtual sp<IMemory> getIMemory() {
        Mutex::Autolock lock(mLock);
        if (mMemory.get() == nullptr) {
            ALOGE("getIMemory() failed, mMemory is nullptr");
            return nullptr;
        }
        return mMemory;
    }
```
也就是说`CallbackDataSource`每次从`media.extractor`中的`RemoteDataSource`读取 64kB 的数据, 然后传递给`TinyCacheSource`, 但`TinyCacheSource`的`mCache`仅仅有 2kB.

**但是:** 这里`mediaserver`现在并不会使用`TinyCacheSource`, 我们后文再看

## `initFromDataSource()`对解封装器的创建

### 用于解封装的`MediaExtractor`的创建
回到`GenericSource::onPrepareAsync()`中, 通过`initFromDataSource()`创建解封装:  
```
// frameworks/av/media/libmediaplayerservice/nuplayer/GenericSource.cpp
status_t NuPlayer::GenericSource::initFromDataSource() {
    ...
    // This might take long time if data source is not reliable.
    extractor = MediaExtractorFactory::Create(dataSource, NULL);
    ...
    sp<MetaData> fileMeta = extractor->getMetaData();
    size_t numtracks = extractor->countTracks();
    for (size_t i = 0; i < numtracks; ++i) {
        sp<IMediaSource> track = extractor->getTrack(i);
        ...
        sp<MetaData> meta = extractor->getTrackMetaData(i);
        ...
        CHECK(meta->findCString(kKeyMIMEType, &mime));
        if (!strncasecmp(mime, "audio/", 6)) {
            ...
            mAudioTrack.mSource = track;
            mAudioTrack.mPackets =
                new AnotherPacketSource(mAudioTrack.mSource->getFormat());
        } else {
            mVideoTrack.mSource = track;
            mVideoTrack.mPackets =
                new AnotherPacketSource(mVideoTrack.mSource->getFormat());
        }
        ...
        mSources.push(track);
        ...
    }
    ...
    // Modular DRM: The return value doesn't affect source initialization.
    (void)checkDrmInfo()
    ...
    mBitrate = totalBitrate;
    return OK;
}
```
`MediaExtractorFactory::Create()`也是通过`IMediaExtractorService`服务创建`IMediaExtractor`的:  
```
// frameworks/av/media/libstagefright/MediaExtractorFactory.cpp
// static
sp<IMediaExtractor> MediaExtractorFactory::Create(
        const sp<DataSource> &source, const char *mime) {
    ...
    if (!property_get_bool("media.stagefright.extractremote", true)) {
        // local extractor
        ...
    } else {
        // remote extractor
        ALOGV("get service manager");
        sp<IBinder> binder = defaultServiceManager()->getService(String16("media.extractor"));

        if (binder != 0) {
            sp<IMediaExtractorService> mediaExService(
                    interface_cast<IMediaExtractorService>(binder));
            sp<IMediaExtractor> ex;
            mediaExService->makeExtractor(
                    CreateIDataSourceFromDataSource(source),
                    mime ? std::optional<std::string>(mime) : std::nullopt,
                    &ex);
            return ex;
        } else ...
    }
    return NULL;
}
```
首先这里的`CreateIDataSourceFromDataSource()`的调用路径和上文有区别:  
```
// frameworks/av/media/libstagefright/InterfaceUtils.cpp
sp<IDataSource> CreateIDataSourceFromDataSource(const sp<DataSource> &source) {
    if (source == nullptr) {
        return nullptr;
    }
    return RemoteDataSource::wrap(source);
}

// frameworks/av/media/libstagefright/include/media/stagefright/RemoteDataSource.h
// Originally in MediaExtractor.cpp
class RemoteDataSource : public BnDataSource {
    static sp<IDataSource> wrap(const sp<DataSource> &source) {
        if (source.get() == nullptr) {
            return nullptr;
        }
        if (source->getIDataSource().get() != nullptr) {
            return source->getIDataSource();
        }
        return new RemoteDataSource(source);
    }
```
`source->getIDataSource().get()`是成立的, 此时`source`的类型是`TinyCacheSource`, 因此:  
```
// frameworks/av/media/libstagefright/CallbackDataSource.cpp
sp<IDataSource> TinyCacheSource::getIDataSource() const {
    return mSource->getIDataSource();
}

sp<IDataSource> CallbackDataSource::getIDataSource() const {
    return mIDataSource;
}
```
`source->getIDataSource().get()`返回的`IDataSource`这是此前`media.extractor`返回给`mediaserver`的, 因此传递给`mediaExService->makeExtractor()`的`IDataSource`对于`media.extractor`而言是本地的了.

`mediaExService->makeExtractor()`就是`MediaExtractorService::makeExtractor()`, 再次回到`media.extractor`中:  
```
// frameworks/av/services/mediaextractor/MediaExtractorService.cpp
::android::binder::Status MediaExtractorService::makeExtractor(
        const ::android::sp<::android::IDataSource>& remoteSource,
        const ::std::optional< ::std::string> &mime,
        ::android::sp<::android::IMediaExtractor>* _aidl_return) {
    ALOGV("@@@ MediaExtractorService::makeExtractor for %s", mime ? mime->c_str() : nullptr);
    sp<DataSource> localSource = CreateDataSourceFromIDataSource(remoteSource);
    MediaBuffer::useSharedMemory();
    sp<IMediaExtractor> extractor = MediaExtractorFactory::CreateFromService(
            localSource,
            mime ? mime->c_str() : nullptr);
    ALOGV("extractor service created %p (%s)",
            extractor.get(),
            extractor == nullptr ? "" : extractor->name());
    if (extractor != nullptr) {
        registerMediaExtractor(extractor, localSource, mime ? mime->c_str() : nullptr);
    }
    *_aidl_return = extractor;
    return binder::Status::ok();
}
```

`CreateDataSourceFromIDataSource()`在`media.extractor`中创建了和在`mediaserver`中一样的`TinyCacheSource`, 这里流程上没啥区别. 紧接着通过`TinyCacheSource`创建了`IMediaExtractor`:  
```
// frameworks/av/media/libstagefright/MediaExtractorFactory.cpp
sp<IMediaExtractor> MediaExtractorFactory::CreateFromService(
        const sp<DataSource> &source, const char *mime) {

    ...
    creator = sniff(source, &confidence, &meta, &freeMeta, plugin, &creatorVersion);
    if (!creator) {
        ALOGV("FAILED to autodetect media content.");
        return NULL;
    }
    MediaExtractor *ex = nullptr;
    if (creatorVersion == EXTRACTORDEF_VERSION_NDK_V1 ||
            creatorVersion == EXTRACTORDEF_VERSION_NDK_V2) {
        CMediaExtractor *ret = ((CreatorFunc)creator)(source->wrap(), meta);
        if (meta != nullptr && freeMeta != nullptr) {
            freeMeta(meta);
        }
        ex = ret != nullptr ? new MediaExtractorCUnwrapper(ret) : nullptr;
    }

    ALOGV("Created an extractor '%s' with confidence %.2f",
         ex != nullptr ? ex->name() : "<null>", confidence);

    return CreateIMediaExtractorFromMediaExtractor(ex, source, plugin);
}
```

### `media.extractor`对封装插件的加载
在分析`sniff()`函数之前, 先分析下`media.extractor`对接封装插件的加载, 在`media.extractor`启动时:  
```
// frameworks/av/services/mediaextractor/main_extractorservice.cpp
int main(int argc __unused, char** argv)
{
    ...
    MediaExtractorService::instantiate();

    ProcessState::self()->startThreadPool();
    IPCThreadState::self()->joinThreadPool();
}

// frameworks/native/libs/binder/include/binder/BinderService.h
class BinderService
{
public:
    static void instantiate() { publish(); }
    static status_t publish(bool allowIsolated = false,
                            int dumpFlags = IServiceManager::DUMP_FLAG_PRIORITY_DEFAULT) {
        sp<IServiceManager> sm(defaultServiceManager());
        return sm->addService(String16(SERVICE::getServiceName()), new SERVICE(), allowIsolated,
                              dumpFlags);
    }
    ...

// frameworks/av/services/mediaextractor/MediaExtractorService.cpp
MediaExtractorService::MediaExtractorService() {
    MediaExtractorFactory::LoadExtractors();
}
```
`SERVICE`就是`MediaExtractorService`, 在例化`MediaExtractorService`时, 执行了`MediaExtractorFactory::LoadExtractors()`.
```
// frameworks/av/media/libstagefright/MediaExtractorFactory.cpp
// static
void MediaExtractorFactory::LoadExtractors() {
    ...
    std::shared_ptr<std::list<sp<ExtractorPlugin>>> newList(new std::list<sp<ExtractorPlugin>>());

    android_namespace_t *mediaNs = android_get_exported_namespace("com_android_media");
    if (mediaNs != NULL) {
        const android_dlextinfo dlextinfo = {
            .flags = ANDROID_DLEXT_USE_NAMESPACE,
            .library_namespace = mediaNs,
        };
        RegisterExtractors("/apex/com.android.media/lib"
#ifdef __LP64__
                "64"
#endif
                "/extractors", &dlextinfo, *newList);
        ...
    } else ...
    ...
    newList->sort(compareFunc);
    gPlugins = newList;
    ...
}
```

首先是`RegisterExtractors()`, 它完成单个路径下的所有插件的加载:  
```
//static
void MediaExtractorFactory::RegisterExtractors(
        const char *libDirPath, const android_dlextinfo* dlextinfo,
        std::list<sp<ExtractorPlugin>> &pluginList) {
    ...
    DIR *libDir = opendir(libDirPath);
    if (libDir) {
        struct dirent* libEntry;
        while ((libEntry = readdir(libDir))) {
            ...
            String8 libPath = String8(libDirPath) + "/" + libEntry->d_name;
            if (!libPath.contains("extractor.so")) {
                continue;
            }
            void *libHandle = android_dlopen_ext(
                    libPath.string(),
                    RTLD_NOW | RTLD_LOCAL, dlextinfo);
            ...
            GetExtractorDef getDef =
                (GetExtractorDef) dlsym(libHandle, "GETEXTRACTORDEF");
            ...
            RegisterExtractor(
                    new ExtractorPlugin(getDef(), libHandle, libPath), pluginList);
            ...
```
在本文讨论的情况, `getDef`的类型有:  
```
// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
extern "C" {
// This is the only symbol that needs to be exported
__attribute__ ((visibility ("default")))
ExtractorDef GETEXTRACTORDEF() {
    return {
        EXTRACTORDEF_VERSION,
        UUID("27575c67-4417-4c54-8d3d-8e626985a164"),
        2, // version
        "MP4 Extractor",
        { .v3 = {Sniff, extensions} },
    };
}

} // extern "C"
```
因此`getDef()`返回的就是`GETEXTRACTORDEF`函数, 函数被调用后, 返回一个`ExtractorDef`被用于构造`ExtractorPlugin`:  
```
// frameworks/av/media/libstagefright/MediaExtractorFactory.cpp
struct ExtractorPlugin : public RefBase {
    ExtractorDef def;
    void *libHandle;
    String8 libPath;
    String8 uuidString;

    ExtractorPlugin(ExtractorDef definition, void *handle, String8 &path)
        : def(definition), libHandle(handle), libPath(path) {
        for (size_t i = 0; i < sizeof ExtractorDef::extractor_uuid; i++) {
            uuidString.appendFormat("%02x", def.extractor_uuid.b[i]);
        }
    }
    ...
};
```
`ExtractorPlugin::def`将在上文提到的`sniff()`函数中被获取到. `RegisterExtractor()`为插件的注册:  
```
// frameworks/av/media/libstagefright/MediaExtractorFactory.cpp
// static
void MediaExtractorFactory::RegisterExtractor(const sp<ExtractorPlugin> &plugin,
        std::list<sp<ExtractorPlugin>> &pluginList) {
    ...
    memcmp(&plugin->def.extractor_uuid, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 16) == 0);
        for (auto it = pluginList.begin(); it != pluginList.end(); ++it) {
            if (memcmp(&((*it)->def.extractor_uuid), &plugin->def.extractor_uuid, 16) == 0) {
                ...
            } else ...
        }
    ALOGV("registering extractor for %s", plugin->def.extractor_name);
    pluginList.push_back(plugin);
}
```
至此插件的`MPEG4Extractor.cpp:Sniff()`函数将最终保存在:`MediaService::gPlugins[...].m_ptr.def.u.v3.sniff`中.

### `MPEG4Extractor.cpp:Sniff()`的调用 
回到`MediaExtractorFactory::CreateFromService()`通过`sniff()`函数主要完成`DataSource`中流媒体文件格式的探测工作:  
```
// frameworks/av/media/libstagefright/MediaExtractorFactory.cpp
void *MediaExtractorFactory::sniff(
        const sp<DataSource> &source, float *confidence, void **meta,
        FreeMetaFunc *freeMeta, sp<ExtractorPlugin> &plugin, uint32_t *creatorVersion) {
    ...
    for (auto it = plugins->begin(); it != plugins->end(); ++it) {
        ...
        if ((*it)->def.def_version == EXTRACTORDEF_VERSION_NDK_V1) {
            curCreator = (void*) (*it)->def.u.v2.sniff(
                    source->wrap(), &newConfidence, &newMeta, &newFreeMeta);
        } else if ((*it)->def.def_version == EXTRACTORDEF_VERSION_NDK_V2) {
            curCreator = (void*) (*it)->def.u.v3.sniff(
                    source->wrap(), &newConfidence, &newMeta, &newFreeMeta);
        }
        ...
        if (curCreator) {
            if (newConfidence > *confidence) {
                *confidence = newConfidence;
                if (*meta != nullptr && *freeMeta != nullptr) {
                    (*freeMeta)(*meta);
                }
                *meta = newMeta;
                *freeMeta = newFreeMeta;
                plugin = *it;
                bestCreator = curCreator;
                *creatorVersion = (*it)->def.def_version;
            } else ...
        }
    }
    return bestCreator;
}
```
此处`(void*) (*it)->def.u.v3.sniff()`调用的就是上文的`MPEG4Extractor.cpp:Sniff()`:  
```
// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
static CreatorFunc Sniff(
        CDataSource *source, float *confidence, void **,
        FreeMetaFunc *) {
    DataSourceHelper helper(source);
    if (BetterSniffMPEG4(&helper, confidence)) {
        return CreateExtractor;
    }

    if (LegacySniffMPEG4(&helper, confidence)) {
        ALOGW("Identified supported mpeg4 through LegacySniffMPEG4.");
        return CreateExtractor;
    }

    return NULL;
}

```
如果`MPEG4Extractor.cpp:Sniff()`判定为是自己能解析的格式, 则返回`MPEG4Extractor.cpp:CreateExtractor()`

### `MPEG4Extractor.cpp:CreateExtractor()`创建`CMediaExtractor`
回到`MediaExtractorFactory::CreateFromService()`中, `((CreatorFunc)creator)(source->wrap(), meta)`将调用`MPEG4Extractor.cpp:CreateExtractor()`, 在调用该方法之前`TinyCacheSource`的父类`DataSource`的wrap()方法被调用, 生成`CDataSource`:  
```
// frameworks/av/include/media/DataSource.h
class DataSource : public DataSourceBase, public virtual RefBase {
public:
    ...
    CDataSource *wrap() {
        if (mWrapper) {
            return mWrapper;
        }
        mWrapper = new CDataSource();
        mWrapper->handle = this;

        mWrapper->readAt = [](void *handle, off64_t offset, void *data, size_t size) -> ssize_t {
            return ((DataSource*)handle)->readAt(offset, data, size);
        };
        mWrapper->getSize = [](void *handle, off64_t *size) -> status_t {
            return ((DataSource*)handle)->getSize(size);
        };
        mWrapper->flags = [](void *handle) -> uint32_t {
            return ((DataSource*)handle)->flags();
        };
        mWrapper->getUri = [](void *handle, char *uriString, size_t bufferSize) -> bool {
            return ((DataSource*)handle)->getUri(uriString, bufferSize);
        };
        return mWrapper;
    }
    ...
}
```
此时`TinyCachedSource`的父类`DataSource`被设置到了其`mWrapper.handle`中

再看`MPEG4Extractor.cpp:CreateExtractor()`的调用(注意此处传递的已经是`CDataSource`了):  
```
// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
static CMediaExtractor* CreateExtractor(CDataSource *source, void *) {
    return wrap(new MPEG4Extractor(new DataSourceHelper(source)));
}
```

`DataSourceHelper`的创建:  
```
// frameworks/av/include/media/MediaExtractorPluginHelper.h
/* adds some convience methods */
class DataSourceHelper {
public:
    explicit DataSourceHelper(CDataSource *csource) {
        mSource = csource;
    }
    ...
```

`MPEG4Extractor`的创建:  
```
// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
MPEG4Extractor::MPEG4Extractor(DataSourceHelper *source, const char *mime)
    : mMoofOffset(0),
      mMoofFound(false),
      mMdatFound(false),
      mDataSource(source),
      mInitCheck(NO_INIT),
      mHeaderTimescale(0),
      mIsQT(false),
      mIsHeif(false),
      mHasMoovBox(false),
      mPreferHeif(mime != NULL && !strcasecmp(mime, MEDIA_MIMETYPE_CONTAINER_HEIF)),
      mIsAvif(false),
      mFirstTrack(NULL),
      mLastTrack(NULL) {
    ALOGV("mime=%s, mPreferHeif=%d", mime, mPreferHeif);
    mFileMetaData = AMediaFormat_new();
}
```
至此, `TinyCachedSource`的父类`DataSource`被设置到了`MPEG4Extractor.mDataSource->mSource->handle`

`wrap()`函数创建`CMediaExtractor`并对其进行设置:  
```
inline CMediaExtractor *wrap(MediaExtractorPluginHelper *extractor) {
    CMediaExtractor *wrapper = (CMediaExtractor*) malloc(sizeof(CMediaExtractor));
    wrapper->data = extractor;
    wrapper->free = [](void *data) -> void {
        delete (MediaExtractorPluginHelper*)(data);
    };
    wrapper->countTracks = [](void *data) -> size_t {
        return ((MediaExtractorPluginHelper*)data)->countTracks();
    };
    wrapper->getTrack = [](void *data, size_t index) -> CMediaTrack* {
        return wrap(((MediaExtractorPluginHelper*)data)->getTrack(index));
    };
    wrapper->getTrackMetaData = [](
            void *data,
            AMediaFormat *meta,
            size_t index, uint32_t flags) -> media_status_t {
        return ((MediaExtractorPluginHelper*)data)->getTrackMetaData(meta, index, flags);
    };
    wrapper->getMetaData = [](
            void *data,
            AMediaFormat *meta) -> media_status_t {
        return ((MediaExtractorPluginHelper*)data)->getMetaData(meta);
    };
    wrapper->flags = [](
            void *data) -> uint32_t {
        return ((MediaExtractorPluginHelper*)data)->flags();
    };
    wrapper->setMediaCas = [](
            void *data, const uint8_t *casToken, size_t size) -> media_status_t {
        return ((MediaExtractorPluginHelper*)data)->setMediaCas(casToken, size);
    };
    wrapper->name = [](
            void *data) -> const char * {
        return ((MediaExtractorPluginHelper*)data)->name();
    };
    return wrapper;
}
```
至此, `MPEG4Extractor.cpp:CreateExtractor()`创建了`CMediaExtractor`, `TinyDataSource`被设置到了:`MediaExtractorFactory::CreateFromService()`中的`ret->data->mDataSource->mSource->handle`

其中`data`类型为`MediaExtractorPluginHelper`, 也就是`MPEG4Extractor`, 但是这里有个问题:`CMediaExtractor`毕竟不是`IMediaExtractor`, 首先`MediaExtractorFactory::CreateFromService()`最终创建了:`MediaExtractorCUnwrapper`:`
```
// frameworks/av/media/libstagefright/MediaExtractor.cpp
MediaExtractorCUnwrapper::MediaExtractorCUnwrapper(CMediaExtractor *plugin) {
    this->plugin = plugin;
}
```
至此, `TinyDataSource`被设置到了:`MediaExtractorFactory::CreateFromService()`中的`ret->plugin->data->mDataSource->mSource->handle`

最后为了返回`IMediaExtractor`, `MediaExtractorFactory::CreateFromService()`调用了`CreateIMediaExtractorFromMediaExtractor()`:  
```
// frameworks/av/media/libstagefright/InterfaceUtils.cpp
sp<IMediaExtractor> CreateIMediaExtractorFromMediaExtractor(
        MediaExtractor *extractor,
        const sp<DataSource> &source,
        const sp<RefBase> &plugin) {
    if (extractor == nullptr) {
        return nullptr;
    }
    return RemoteMediaExtractor::wrap(extractor, source, plugin);
}

// frameworks/av/media/libstagefright/RemoteMediaExtractor.cpp
// static
sp<IMediaExtractor> RemoteMediaExtractor::wrap(
        MediaExtractor *extractor,
        const sp<DataSource> &source,
        const sp<RefBase> &plugin) {
    if (extractor == nullptr) {
        return nullptr;
    }
    return new RemoteMediaExtractor(extractor, source, plugin);
}

// frameworks/av/media/libstagefright/RemoteMediaExtractor.cpp
RemoteMediaExtractor::RemoteMediaExtractor(
        MediaExtractor *extractor,
        const sp<DataSource> &source,
        const sp<RefBase> &plugin)
    :mExtractor(extractor),
     mSource(source),
     mExtractorPlugin(plugin) {
    ...
}
```
此处`RemoteMediaExtractor`就是`IMediaExtractor`的实现了.
至此, `TinyDataSource`被设置到了:`MediaExtractorService::makeExtractor()`中的`extractor->mExtractor->plugin->data->mDataSource->mSource->handle`
其中:
* `extractor`: `IMediaExtractor` -> `RemoteMediaExtractor`
* `extractor->mExtractor`: `MediaExtractor` -> `MediaExtractorCUnwrapper`
* `extractor->mExtractor->plugin`: `CMediaExtractor`
* `extractor->mExtractor->plugin->data`: `void *` -> `MediaExtractorPluginHelper` -> `MPEG4Extractor`
* `extractor->mExtractor->plugin->data->mDataSource`: `DataSourceHelper`
* `extractor->mExtractor->plugin->data->mDataSource->mSource`: `CDataSource`
* `extractor->mExtractor->plugin->data->mDataSource->mSource->handle`: `DataSource` -> `TinyDataSource`

最后回到`MediaExtractorService::makeExtractor()`中, 通过调试验证上述言论:  
```
p *((TinyCacheSource *)((RemoteMediaExtractor *)0x0000007d68639df0)->mSource.m_ptr->mWrapper->handle)
warning: `this' is not accessible (substituting 0). Couldn't load 'this' because its value couldn't be evaluated
(android::TinyCacheSource) $35 = {
  android::DataSource = {
    mWrapper = 0x0000007d4864b410
  }
  mSource = {
    m_ptr = 0x0000007d58647640
  }
  mCache = "..."...
  mCachedOffset = 405144
  mCachedSize = 2048
  mName = (mString = "TinyCacheSource(CallbackDataSource(4894->4875, RemoteDataSource(FileSource(fd(/storage/emulated/0/Movies/VID_20220317_221515.mp4), 0, 4948142))))")
}
```

对于地址`0x0000007d58647640`, 已经知道其类型为`CallbackDataSource`, 因此:  
```
p *(CallbackDataSource *)0x0000007d58647640
warning: `this' is not accessible (substituting 0). Couldn't load 'this' because its value couldn't be evaluated
(android::CallbackDataSource) $37 = {
  android::DataSource = {
    mWrapper = nullptr
  }
  mIDataSource = (m_ptr = 0x0000007d88645ab0)
  mMemory = (m_ptr = 0x0000007d68639cd0)
  mIsClosed = false
  mName = (mString = "CallbackDataSource(4894->4875, RemoteDataSource(FileSource(fd(/storage/emulated/0/Movies/VID_20220317_221515.mp4), 0, 4948142)))")
}
```
通过`mName`确认到以上所有类型行的总结都是正确的, 至此到`media.extractor`的 IPC 过程结束.

### 媒体文件元数据信息`MetaData`的获取
回到`NuPlayer::GenericSource::initFromDataSource()`中, 继续查看`extractor->getMetaData()`, 该调用将再次通过 `binder` 调用到 `meida.extracotr`中的`RemoteMediaExtractor::getMedtaData()`:  
```
// frameworks/av/media/libstagefright/RemoteMediaExtractor.cpp
sp<MetaData> RemoteMediaExtractor::getMetaData() {
    sp<MetaData> meta = new MetaData();
    if (mExtractor->getMetaData(*meta.get()) == OK) {
        return meta;
    }
    return nullptr;
}

// frameworks/av/media/libstagefright/MediaExtractor.cpp
status_t MediaExtractorCUnwrapper::getMetaData(MetaDataBase& meta) {
    sp<AMessage> msg = new AMessage();
    AMediaFormat *format =  AMediaFormat_fromMsg(&msg);
    media_status_t ret = plugin->getMetaData(plugin->data, format);
    sp<MetaData> newMeta = new MetaData();
    convertMessageToMetaData(msg, newMeta);
    delete format;
    meta = *newMeta;
    return reverse_translate_error(ret);
}

// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaExtractor *wrap(MediaExtractorPluginHelper *extractor) {
    ...
    wrapper->getMetaData = [](
            void *data,
            AMediaFormat *meta) -> media_status_t {
        return ((MediaExtractorPluginHelper*)data)->getMetaData(meta);
    };
    ...
}

// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
media_status_t MPEG4Extractor::getMetaData(AMediaFormat *meta) {
    status_t err;
    if ((err = readMetaData()) != OK) {
        return AMEDIA_ERROR_UNKNOWN;
    }
    AMediaFormat_copy(meta, mFileMetaData);
    return AMEDIA_OK;
}

status_t MPEG4Extractor::readMetaData() {
    ...
}
```
`MPEG4Extractor::readMetaData()`比较复杂, 放弃分析, 该函数负责将获取到的元数据保存在`MPEG4Extracotr`的`mFileMetaData`(类型为`AMediaFormat`)成员中, 该信息将在`MPEG4Extractor::getMetaData)`函数中通过`AMediaFormat_copy()`方法拷贝到调用方`MediaExtractorCUnwrapper::getMetaData()`的临时变量`format`中.

在`MediaExtractorCUnwrapper::getMetaData()`函数中, 获取到的`AMediaFormat`需要通过`convertMessageToMetaData()`函数转化到`MetaData`类型, 此处过程较长, 本文不分析.

`MetaData`通过`binder`返回给`mediaserver`时是通过``MetaDataBase::writeToParcel()完成序列化的, 不文也不分析该过程.

### 媒体文件中`MPEG4Extractor::Track`数量的获取
回到`NuPlayer::GenericSource::initFromDataSource()`中, 继续查看`extractor->countTracks()`, 该调用将再次通过 `binder` 调用到 `meida.extracotr`中的`RemoteMediaExtractor::countTracks()`:  
```
// frameworks/av/media/libstagefright/RemoteMediaExtractor.cpp
size_t RemoteMediaExtractor::countTracks() {
    return mExtractor->countTracks();
}

// frameworks/av/media/libstagefright/MediaExtractor.cpp
size_t MediaExtractorCUnwrapper::countTracks() {
    return plugin->countTracks(plugin->data);
}

// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaExtractor *wrap(MediaExtractorPluginHelper *extractor) {
    ...
    wrapper->countTracks = [](void *data) -> size_t {
        return ((MediaExtractorPluginHelper*)data)->countTracks();
    };
    ...
}

// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
size_t MPEG4Extractor::countTracks() {
    status_t err;
    if ((err = readMetaData()) != OK) {
        ALOGV("MPEG4Extractor::countTracks: no tracks");
        return 0;
    }

    size_t n = 0;
    Track *track = mFirstTrack;
    while (track) {
        ++n;
        track = track->next;
    }

    ALOGV("MPEG4Extractor::countTracks: %zu tracks", n);
    return n;
}
```
`MPEG4Extractor::readMetaData()`在上文提到的`MPEG4Extractor::getMetaData()`已经调用过了, 这里跳过, 函数主体主要统计`MPEG4Extractor`中 `MPEG4Extractor::Track`的数量.

### `IMediaSource`的获取
回到`NuPlayer::GenericSource::initFromDataSource()`中, 继续查看`extractor->getTrack(i)`, 该调用将再次通过 `binder` 调用到 `meida.extracotr`中的`RemoteMediaExtractor::getTrack()`:  
```
// frameworks/av/media/libstagefright/RemoteMediaExtractor.cpp
sp<IMediaSource> RemoteMediaExtractor::getTrack(size_t index) {
    MediaTrack *source = mExtractor->getTrack(index);
    return (source == nullptr)
            ? nullptr : CreateIMediaSourceFromMediaSourceBase(this, source, mExtractorPlugin);
}
```
分两部分, 首先看`mExtractor->getTrack()`:  
```
// frameworks/av/media/libstagefright/MediaExtractor.cpp
MediaTrack *MediaExtractorCUnwrapper::getTrack(size_t index) {
    return MediaTrackCUnwrapper::create(plugin->getTrack(plugin->data, index));
}
```
首先`plugin->getTrack()`负责创建`CMediaTrack`:  
```
// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaExtractor *wrap(MediaExtractorPluginHelper *extractor) {
    ...
    wrapper->getTrack = [](void *data, size_t index) -> CMediaTrack* {
        return wrap(((MediaExtractorPluginHelper*)data)->getTrack(index));
    };
```
首先`MediaExtractorPluginHelper*)data)->getTrack()`负责获取`MediaTrackHelper`:  
```
// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
MediaTrackHelper *MPEG4Extractor::getTrack(size_t index) {
    status_t err;
    if ((err = readMetaData()) != OK) {
        return NULL;
    }
    Track *track = mFirstTrack;
    ...
    MPEG4Source* source =
            new MPEG4Source(track->meta, mDataSource, track->timescale, track->sampleTable,
                            mSidxEntries, trex, mMoofOffset, itemTable,
                            track->elst_shift_start_ticks, elst_initial_empty_edit_ticks);
    if (source->init() != OK) {
        delete source;
        return NULL;
    }
    return source;
}
```
`MPEG4Source`正是`MediaTrackHelper`的子类. 回到`MPEG4Extractor::MediaExtractorPluginHelper::wrap()`中, `wrap()`函数:  
```
// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaTrack *wrap(MediaTrackHelper *track) {
    if (track == nullptr) {
        return nullptr;
    }
    CMediaTrack *wrapper = (CMediaTrack*) malloc(sizeof(CMediaTrack));
    wrapper->data = track;
    ...
}
```
至此`CMediaTrack`被创建, 且`MPEG4Source`作为`MediaTrackHelper`被传递给`MediaExtractorCUnwrapper::getTrack()`的`MediaTrackCUnwrapper::create()`函数:  
```
// frameworks/av/media/libstagefright/MediaTrack.cpp
MediaTrackCUnwrapper *MediaTrackCUnwrapper::create(CMediaTrack *cmediatrack) {
    if (cmediatrack == nullptr) {
        return nullptr;
    }
    return new MediaTrackCUnwrapper(cmediatrack);
}

MediaTrackCUnwrapper::MediaTrackCUnwrapper(CMediaTrack *cmediatrack) {
    wrapper = cmediatrack;
    bufferGroup = nullptr;
}
```
至此`MPEG4Source`作为`MediaTrackHelper`被设置在`RemoteMediaExtractor::getTrack()`的变量`source->wrapper->data`, 并且`MediaTrackCUnwrapper`的父类是`MediaTrack`.

回到`RemoteMediaExtractor::getTrack()`中, 从`CreateIMediaSourceFromMediaSourceBase()`继续分析:  
```
// frameworks/av/media/libstagefright/InterfaceUtils.cpp
sp<IMediaSource> CreateIMediaSourceFromMediaSourceBase(
        const sp<RemoteMediaExtractor> &extractor,
        MediaTrack *source, const sp<RefBase> &plugin) {
    if (source == nullptr) {
        return nullptr;
    }
    return RemoteMediaSource::wrap(extractor, source, plugin);
}

// frameworks/av/media/libstagefright/RemoteMediaSource.cpp
// static
sp<IMediaSource> RemoteMediaSource::wrap(
        const sp<RemoteMediaExtractor> &extractor,
        MediaTrack *source, const sp<RefBase> &plugin) {
    if (source == nullptr) {
        return nullptr;
    }
    return new RemoteMediaSource(extractor, source, plugin);
}

RemoteMediaSource::RemoteMediaSource(
        const sp<RemoteMediaExtractor> &extractor,
        MediaTrack *source,
        const sp<RefBase> &plugin)
    : mExtractor(extractor),
      mTrack(source),
      mExtractorPlugin(plugin) {}
```
至此, `MPEG4Source`作为`MediaTrackHelper`被设置在: `RemoteMediaSource.mTrack->wrapper->data`, 其中:
* `RemoteMediaSource.mTrack`: `MediaTrackCUnwrapper`
* `RemoteMediaSource.mTrack->wrapper`: `CMediaTrack`
* `RemoteMediaSource.mTrack->wrapper->data`: `MediaTrackHelper` -> `MPEG4Source`

为了验证该总结的正确性, 通过调试器:  
```
p track
(const android::sp<android::IMediaSource>) $79 = (m_ptr = 0x0000007d98639b10)
// 得到的 track 的类型应为 RemoteMediaSource, 因此:

p *(android::RemoteMediaSource *)0x0000007d98639b10
(android::RemoteMediaSource) $80 = {
  mExtractor = {
    m_ptr = 0x0000007d68639fd0
  }
  mTrack = 0x0000007d3863c290
  mExtractorPlugin = (m_ptr = 0x0000007d7863d9b0)
}
// 得到的 mTrack 类型应为 MediaTrackCUnwrapper, 因此
p *(android::MediaTrackCUnwrapper *)0x0000007d3863c290
(android::MediaTrackCUnwrapper) $81 = {
  wrapper = 0x0000007d586463d0
  bufferGroup = nullptr
}
// 得到的 wrapper 类型应为 CMediaTrack, 因此
p *(CMediaTrack *)0x0000007d586463d0
(CMediaTrack) $83 = {
  data = 0x0000007de8638ed0
  free = 0x0000007d143696b8 (libmp4extractor.so`android::wrap(android::MediaExtractorPluginHelper*)::'lambda'(void*)::__invoke(void*) + 4)
  start = 0x0000007d143696bc (libmp4extractor.so`android::wrap(android::MediaTrackHelper*)::'lambda'(void*)::__invoke(void*) + 4)
  stop = 0x0000007d143696c0 (libmp4extractor.so`android::wrap(android::MediaTrackHelper*)::'lambda0'(void*)::__invoke(void*))
  getFormat = 0x0000007d143696c8 (libmp4extractor.so`android::wrap(android::MediaExtractorPluginHelper*)::'lambda'(void*, AMediaFormat*)::__invoke(void*, AMediaFormat*) + 4)
  read = 0x0000007d143696cc (libmp4extractor.so`android::wrap(android::MediaTrackHelper*)::'lambda'(void*, AMediaFormat*)::__invoke(void*, AMediaFormat*) + 4)
  supportsNonBlockingRead = 0x0000007d143696d0 (libmp4extractor.so`__typeid__ZTSFbPvE_global_addr)
}
// 得到的 data 的类型为: MPEG4Source, 因此:

p *((android::MPEG4Source *)0x0000007de8638ed0)
(android::MPEG4Source) $67 = {
  android::MediaTrackHelper = {
    mBufferGroup = nullptr
  }
  mLock = {
    mMutex = {
      __private = ([0] = 0, [1] = 0, [2] = 0, [3] = 0, [4] = 0, [5] = 0, [6] = 0, [7] = 0, [8] = 0, [9] = 0)
    }
  }
  mFormat = 0x0000007d586489a0
  mDataSource = 0x0000007d2863b850
  mTimescale = 90000
  ...
}

// 此时关注 mFormat 我们打印其内容:
p *(AMediaFormat *)0x0000007d586489a0
(AMediaFormat) $87 = {
  mFormat = {
    m_ptr = 0x0000007d686398b0
  }
  mDebug = (mString = "")
}

此处 mFormat 的类型为 android::AMessage, 因此:
p *(android::AMessage *)0x0000007d686398b0
(android::AMessage) $89 = {
  android::RefBase = {
    mRefs = 0x0000007d3863c230
  }
  mWhat = 0
  mTarget = 0
  mHandler = {
    m_ptr = nullptr
    m_refs = nullptr
  }
  mLooper = {
    m_ptr = nullptr
    m_refs = nullptr
  }
  mItems = size=16 {
    [0] = {
      u = {
        int32Value = 946061584
        int64Value = 537816973584
        sizeValue = 537816973584
        floatValue = 0.0000543008209
        doubleValue = 2.6571689039816359E-312
        ptrValue = 0x0000007d3863c110
        refValue = 0x0000007d3863c110
        stringValue = 0x0000007d3863c110
        rectValue = (mLeft = 946061584, mTop = 125, mRight = 0, mBottom = 0)
      }
      mName = 0x0000007d2863c270 "mime"
      mNameLength = 4
      mType = kTypeString
    }
    ...
  }
  ...
}
// AMessage 中, mItems 的第一个 Item 类型中的 stringValue 类型为: AString *, 因此可以求 "mime" 的值:
p *(android::AString *)0x0000007d3863c110
(android::AString) $91 = (mData = "video/avc", mSize = 9, mAllocSize = 32)
```
可以清晰的看到, 有一个`Track`的`mime`类型为`"video/avc"`, 而另一个通过同样的方法可得知为: `"audio/mp4a-latm"`.

### 媒体文件中`MPEG4Extractor::Track`元数据`MetaData`的获取
回到`NuPlayer::GenericSource::initFromDataSource()`中, 继续查看`extractor->getTrackMetaData(i)`, 该调用将再次通过 `binder` 调用到 `meida.extracotr`中的`RemoteMediaExtractor::getTrackMetaData()`:  
```
// frameworks/av/media/libstagefright/RemoteMediaExtractor.cpp
sp<MetaData> RemoteMediaExtractor::getTrackMetaData(size_t index, uint32_t flags) {
    sp<MetaData> meta = new MetaData();
    if (mExtractor->getTrackMetaData(*meta.get(), index, flags) == OK) {
        return meta;
    }
    return nullptr;
}

// frameworks/av/media/libstagefright/MediaExtractor.cpp
status_t MediaExtractorCUnwrapper::getTrackMetaData(
        MetaDataBase& meta, size_t index, uint32_t flags) {
    sp<AMessage> msg = new AMessage();
    AMediaFormat *format =  AMediaFormat_fromMsg(&msg);
    media_status_t ret = plugin->getTrackMetaData(plugin->data, format, index, flags);
    sp<MetaData> newMeta = new MetaData();
    convertMessageToMetaData(msg, newMeta);
    delete format;
    meta = *newMeta;
    return reverse_translate_error(ret);
}

// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaExtractor *wrap(MediaExtractorPluginHelper *extractor) {
    ...
    wrapper->getTrackMetaData = [](
            void *data,
            AMediaFormat *meta,
            size_t index, uint32_t flags) -> media_status_t {
        return ((MediaExtractorPluginHelper*)data)->getTrackMetaData(meta, index, flags);
    };
    ...
}

// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
media_status_t MPEG4Extractor::getTrackMetaData(
        AMediaFormat *meta,
        size_t index, uint32_t flags) {
    status_t err;
    if ((err = readMetaData()) != OK) {
        return AMEDIA_ERROR_UNKNOWN;
    }
    ...
    return AMediaFormat_copy(meta, track->meta);
}
```
上文已经调试过, `track->meta`的数据结构就是`AMediaFormat`, 它其实也是`MPEG4Extractor::Track`的`mFormat`. 回到`MediaExtractorCUnwrapper::getTrackMetaData()`中, `convertMessageToMetaData()`将

### 音频`GenericSource::Track`的创建
回到`NuPlayer::GenericSource::initFromDataSource()`中, 如果`mime`类型是`"audio/"`开头, 则当前`Track`为音频, 则配置`mAudioTrack`, 分别配置其`mIndex`, `mSource`(类型为`IMediaSource`), `mPackets`(类型为`AnotherPacketSource`). 

### 视频`GenericSource::Track`的创建
与音频的情况类似


## `GenericSource::finishPrepareAsync()`
回到`NuPlayer::GenericSource::onPrepareAsync()`中, `NuPlayer`结束`GenericSource`的配置:  
```
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
    if (mAudioTrack.mSource != NULL) {
        postReadBuffer(MEDIA_TRACK_TYPE_AUDIO);
    }

    if (mVideoTrack.mSource != NULL) {
        postReadBuffer(MEDIA_TRACK_TYPE_VIDEO);
    }
}
```

### `NuPlayer::GenericSource::startSources()`创建`Extractor`的缓冲区
先看`startSources()`:  
```
// frameworks/av/media/libmediaplayerservice/nuplayer/GenericSource.cpp
status_t NuPlayer::GenericSource::startSources() {
    if (mAudioTrack.mSource != NULL && mAudioTrack.mSource->start() != OK) {
        ALOGE("failed to start audio track!");
        return UNKNOWN_ERROR;
    }

    if (mVideoTrack.mSource != NULL && mVideoTrack.mSource->start() != OK) {
        ALOGE("failed to start video track!");
        return UNKNOWN_ERROR;
    }

    return OK;
}
```
由于`mSource`的类型为`IMediaSource`, 因此会通过`binder`调用到`media.extractor`一侧:  
```
// frameworks/av/media/libstagefright/RemoteMediaSource.cpp
status_t RemoteMediaSource::start(MetaData *params) {
    if (params) {
        ALOGW("dropping start parameters:");
        params->dumpToLog();
    }
    return mTrack->start();
}

// frameworks/av/media/libstagefright/MediaTrack.cpp
status_t MediaTrackCUnwrapper::start() {
    if (bufferGroup == nullptr) {
        bufferGroup = new MediaBufferGroup();
    }
    return reverse_translate_error(wrapper->start(wrapper->data, bufferGroup->wrap()));
}
```
这里操作比较多, 拆开看, 先看`MediaBufferGroup`创建后, `MediaBufferGroup::wrap()`的执行:  
```
// frameworks/av/media/libstagefright/include/media/stagefright/MediaBufferGroup.h
class MediaBufferGroup : public MediaBufferObserver {
public:
    CMediaBufferGroup *wrap() {
        if (mWrapper) {
            return mWrapper;
        }

        mWrapper = new CMediaBufferGroup;
        mWrapper->handle = this;
        ...
    }
    ...
```
可以看到创建了`CMediaBufferGroup`, 并将上面创建的`MediaBufferGroup`设置给该对象的`handle`.

再看`wrapper->start`方法:  
```
// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaTrack *wrap(MediaTrackHelper *track) {
    ...
    wrapper->start = [](void *data, CMediaBufferGroup *bufferGroup) -> media_status_t {
        if (((MediaTrackHelper*)data)->mBufferGroup) {
            // this shouldn't happen, but handle it anyway
            delete ((MediaTrackHelper*)data)->mBufferGroup;
        }
        ((MediaTrackHelper*)data)->mBufferGroup = new MediaBufferGroupHelper(bufferGroup);
        return ((MediaTrackHelper*)data)->start();
    };
    ...
}
```
可以看到该`lambda`创建了`MediaBufferGroupHelper`, 并设置给了`wrapper->data`(类型为`MPEG4Source`)的`mBufferGroup`成员, 至此:
* `MPEG4Source.mBufferGroup`: `MediaBufferGroupHelper`
* `MPEG4Source.mBufferGroup->mGroup`: `CMediaBufferGroup`
* `MPEG4Source.mBufferGroup->mGroup->handle` : `MediaBufferGroup`

然后`wrapper->start`通过`((MediaTrackHelper*)data)->start()`调用到`MPEG4Source::start()`:  
```
// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
media_status_t MPEG4Source::start() {
    Mutex::Autolock autoLock(mLock);
    ...
    // Allow up to kMaxBuffers, but not if the total exceeds kMaxBufferSize.
    const size_t kInitialBuffers = 2;
    const size_t kMaxBuffers = 8;
    const size_t realMaxBuffers = min(kMaxBufferSize / max_size, kMaxBuffers);
    mBufferGroup->init(kInitialBuffers, max_size, realMaxBuffers);
    mSrcBuffer = new (std::nothrow) uint8_t[max_size];
    if (mSrcBuffer == NULL) {
        // file probably specified a bad max size
        return AMEDIA_ERROR_MALFORMED;
    }

    mStarted = true;

    return AMEDIA_OK;
}
```
如上文`mBufferGroup`的类型为`MediaBufferGroupHelper`, 因此:  
```
// frameworks/av/include/media/MediaExtractorPluginHelper.h
class MediaBufferGroupHelper {
public:
    bool init(size_t buffers, size_t buffer_size, size_t growthLimit = 0) {
        return mGroup->init(mGroup->handle, buffers, buffer_size, growthLimit);
    }

// frameworks/av/media/libstagefright/include/media/stagefright/MediaBufferGroup.h
class MediaBufferGroup : public MediaBufferObserver {
public:
    CMediaBufferGroup *wrap() {
        ...
        mWrapper->init = [](void *handle,
                size_t buffers, size_t buffer_size, size_t growthLimit) -> bool {
            ((MediaBufferGroup*)handle)->init(buffers, buffer_size, growthLimit);
          //  ((MediaBufferGroup*)handle)->mWrapper->init = nullptr; // enforce call-once
            return true;
        };
        ...
    }
    ...
}

// frameworks/av/media/libstagefright/foundation/MediaBufferGroup.cpp
void MediaBufferGroup::init(size_t buffers, size_t buffer_size, size_t growthLimit) {
    mInternal->mGrowthLimit = growthLimit;

    if (mInternal->mGrowthLimit > 0 && buffers > mInternal->mGrowthLimit) {
        ALOGW("Preallocated buffers %zu > growthLimit %zu, increasing growthLimit",
                buffers, mInternal->mGrowthLimit);
        mInternal->mGrowthLimit = buffers;
    }
    ...
    if (buffer_size >= kSharedMemoryThreshold) {
        // Using a single MemoryDealer is efficient for a group of shared memory objects.
        // This loop guarantees that we use shared memory (no fallback to malloc).

        size_t alignment = MemoryDealer::getAllocationAlignment();
        size_t augmented_size = buffer_size + sizeof(MediaBuffer::SharedControl);
        size_t total = (augmented_size + alignment - 1) / alignment * alignment * buffers;
        sp<MemoryDealer> memoryDealer = new MemoryDealer(total, "MediaBufferGroup");

        for (size_t i = 0; i < buffers; ++i) {
            sp<IMemory> mem = memoryDealer->allocate(augmented_size);
            if (mem.get() == nullptr || mem->unsecurePointer() == nullptr) {
                ALOGW("Only allocated %zu shared buffers of size %zu", i, buffer_size);
                break;
            }
            MediaBuffer *buffer = new MediaBuffer(mem);
            buffer->getSharedControl()->clear();
            add_buffer(buffer);
        }
        return;
    }
    ...
    // Non-shared memory allocation.
    for (size_t i = 0; i < buffers; ++i) {
        MediaBuffer *buffer = new MediaBuffer(buffer_size);
        if (buffer->data() == nullptr) {
            delete buffer; // don't call release, it's not properly formed
            ALOGW("Only allocated %zu malloc buffers of size %zu", i, buffer_size);
            break;
        }
        add_buffer(buffer);
    }
}

void MediaBufferGroup::add_buffer(MediaBufferBase *buffer) {
    Mutex::Autolock autoLock(mInternal->mLock);

    // if we're above our growth limit, release buffers if we can
    for (auto it = mInternal->mBuffers.begin();
            mInternal->mGrowthLimit > 0
            && mInternal->mBuffers.size() >= mInternal->mGrowthLimit
            && it != mInternal->mBuffers.end();) {
        if ((*it)->refcount() == 0) {
            (*it)->setObserver(nullptr);
            (*it)->release();
            it = mInternal->mBuffers.erase(it);
        } else {
            ++it;
        }
    }

    buffer->setObserver(this);
    mInternal->mBuffers.emplace_back(buffer);
}
```
这里其实比较直接, 创建`MemoryDealer`, 然后创建一串`MediaBuffer`并通过`add_buffer()`添加到本地

### `NuPlayer::Source::notifyPrepared()`发出`kWhatPrepared`消息通知准备完成
然后再看`notifyPrepared()`, 准备`DataSource`并设置给`mDataSource`, 该步骤不能失败, 如果成功, 且初始化没有问题, 则最终通过父类`NuPlayer::Source`的`notifyPrepared()`方法通知`NuPlayerDriver`:  
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

### `NuPlayer::GenericSource::postReadBuffer()`开始预读取解码数据
回到`NuPlayer::GenericSource::finishPrepareAsync()`中, 通过`NuPlayer::GenericSource::postReadBuffer()`预读取一些数据:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/GenericSource.cpp
void NuPlayer::GenericSource::postReadBuffer(media_track_type trackType) {
    if ((mPendingReadBufferTypes & (1 << trackType)) == 0) {
        mPendingReadBufferTypes |= (1 << trackType);
        sp<AMessage> msg = new AMessage(kWhatReadBuffer, this);
        msg->setInt32("trackType", trackType);
        msg->post();
    }
}

void NuPlayer::GenericSource::onMessageReceived(const sp<AMessage> &msg) {
    Mutex::Autolock _l(mLock);
    switch (msg->what()) {
        ...
      case kWhatReadBuffer:
      {
          onReadBuffer(msg);
          break;
      }
      ...
    }
    ...
}

void NuPlayer::GenericSource::onReadBuffer(const sp<AMessage>& msg) {
    int32_t tmpType;
    CHECK(msg->findInt32("trackType", &tmpType));
    media_track_type trackType = (media_track_type)tmpType;
    mPendingReadBufferTypes &= ~(1 << trackType);
    readBuffer(trackType);
}

void NuPlayer::GenericSource::readBuffer(
        media_track_type trackType, int64_t seekTimeUs, MediaPlayerSeekMode mode,
        int64_t *actualTimeUs, bool formatChange) {
    Track *track;
    size_t maxBuffers = 1;
    ...
    int32_t generation = getDataGeneration(trackType);
    for (size_t numBuffers = 0; numBuffers < maxBuffers; ) {
        Vector<MediaBufferBase *> mediaBuffers;
        status_t err = NO_ERROR;

        sp<IMediaSource> source = track->mSource;
        mLock.unlock();
        if (couldReadMultiple) {
            err = source->readMultiple(
                    &mediaBuffers, maxBuffers - numBuffers, &options);
        } else ...
        ...
        for (; id < count; ++id) {
            int64_t timeUs;
            MediaBufferBase *mbuf = mediaBuffers[id];
            ...
            queueDiscontinuityIfNeeded(seeking, formatChange, trackType, track);

            sp<ABuffer> buffer = mediaBufferToABuffer(mbuf, trackType);
            ...
            track->mPackets->queueAccessUnit(buffer);
            formatChange = false;
            seeking = false;
            ++numBuffers;
        }
        ...
    }
    ...
}

// frameworks/av/media/libmedia/IMediaSource.cpp
class BpMediaSource : public BpInterface<IMediaSource> {
public:
    ...
    virtual status_t readMultiple(
            Vector<MediaBufferBase *> *buffers, uint32_t maxNumBuffers,
            const MediaSource::ReadOptions *options) {
        ALOGV("readMultiple");
        if (buffers == NULL || !buffers->isEmpty()) {
            return BAD_VALUE;
        }
        Parcel data, reply;
        data.writeInterfaceToken(BpMediaSource::getInterfaceDescriptor());
        data.writeUint32(maxNumBuffers);
        if (options != nullptr) {
            data.writeByteArray(sizeof(*options), (uint8_t*) options);
        }
        status_t ret = remote()->transact(READMULTIPLE, data, &reply);
        ...
    }
    ...
}
```
`source`的类型是`IMediaSource`, 所以会调用到:`media.extractor`中的`status_t BnMediaSource::onTransact()`:
```
// frameworks/av/media/libmedia/IMediaSource.cpp
status_t BnMediaSource::onTransact(
    uint32_t code, const Parcel& data, Parcel* reply, uint32_t flags)
{
    switch (code) {
        ...
        case READMULTIPLE: {
            ALOGV("readMultiple");
            ...
            for (; bufferCount < maxNumBuffers; ++bufferCount, ++mBuffersSinceStop) {
                MediaBuffer *buf = nullptr;
                ret = read((MediaBufferBase **)&buf, useOptions ? &opts : nullptr);
                ...
                if (length >= (supportNonblockingRead() && buf->mMemory != nullptr ?
                        kTransferSharedAsSharedThreshold : kTransferInlineAsSharedThreshold)) {
                    if (buf->mMemory != nullptr) {
                        ALOGV("Use shared memory: %zu", length);
                        transferBuf = buf;
                    } else {
                        ALOGV("Large buffer %zu without IMemory!", length);
                        ret = mGroup->acquire_buffer(...
                        if (ret != OK
                                || transferBuf == nullptr
                                || transferBuf->mMemory == nullptr) {
                            ...
                        } else {
                            memcpy(transferBuf->data(), (uint8_t*)buf->data() + offset, length);
                            ...
                        }
                    }
                }
                if (transferBuf != nullptr) { // Using shared buffers.
                    uint64_t index = mIndexCache.lookup(transferBuf->mMemory);
                    if (index == 0) {
                        index = mIndexCache.insert(transferBuf->mMemory);
                        reply->writeInt32(SHARED_BUFFER);
                        reply->writeUint64(index);
                        reply->writeStrongBinder(IInterface::asBinder(transferBuf->mMemory));
                        ALOGV("SHARED_BUFFER(%p) %llu",
                                transferBuf, (unsigned long long)index);
                    } else {
                        reply->writeInt32(SHARED_BUFFER_INDEX);
                        reply->writeUint64(index);
                        ALOGV("SHARED_BUFFER_INDEX(%p) %llu",
                                transferBuf, (unsigned long long)index);
                    }
                    reply->writeInt32(offset);
                    reply->writeInt32(length);
                    buf->meta_data().writeToParcel(*reply);
                    transferBuf->addRemoteRefcount(1);
                    if (transferBuf != buf) {
                        transferBuf->release(); // release local ref
                    } else if (!supportNonblockingRead()) {
                        maxNumBuffers = 0; // stop readMultiple with one shared buffer.
                    }
                } else {
                    ALOGV_IF(buf->mMemory != nullptr,
                            "INLINE(%p) %zu shared mem available, but only %zu used",
                            buf, buf->mMemory->size(), length);
                    reply->writeInt32(INLINE_BUFFER);
                    reply->writeByteArray(length, (uint8_t*)buf->data() + offset);
                    buf->meta_data().writeToParcel(*reply);
                    inlineTransferSize += length;
                    if (inlineTransferSize > kInlineMaxTransfer) {
                        maxNumBuffers = 0; // stop readMultiple if inline transfer is too large.
                    }
                }
                buf->release();
            }
            reply->writeInt32(NULL_BUFFER); // Indicate no more MediaBuffers.
            reply->writeInt32(ret);
            ALOGV("readMultiple status %d, bufferCount %u, sinceStop %u",
                    ret, bufferCount, mBuffersSinceStop);
            return NO_ERROR;
        }
        ...
        default:
            return BBinder::onTransact(code, data, reply, flags);
    }
}
```
这个函数看起来比较复杂, 大体叙述一下它主要的工作:
* 循环读取请求的buffer
  * 调用`read()`执行读取, 结果为一个`MediaBuffer`
  * 判断解析出来的`MediaBuffer`, 分两种情况:
    * `MediaBuffer`能用`binder`传递, 直接到最后一个`else`的位置通过`reply->writeByteArray()`写入数据到`binder`
    * `MediaBuffer`不能通过`binder`传递, 这里又分两种情况:
      * 返回的`MediaBuffer`未使用共享内存, 此时抱怨一下, 然后从`RemoteMediaSource`的父类`BnMediaSource`所持有的`MediaBufferGroup`中分配一个共享内存的`MediaBuffer`, 然后获取解码器返回的数据, 拷贝到新分配的共享内存中
      * 返回的`MediaBuffer`使用的为共享内存, 则直接向后传递, 传递到后面, 如果是共享内存还分两种情况:
        * 共享内存形式的`MediaBuffer`中的`IMemory`是否有缓存在`BnMediaSource`的`mIndexCache`(类型为`IndexCache`)中, 如果没有, `mIndexCache.lookup()`返回的`index`就是`0`, 所以插入到缓存当中, 等待后续获取

目前在本人使用的 `Google Pixel 3 XL` 上, 对于 `H264` 和 `AAC` 两种格式, 未出现`mGroup->acquire_buffer()`的情形.

接下来通过`read()`函数, 检查`MediaBuffer`的创建(注意, 在`MediaBufferGroup::init()`时已经申请了`kInitialBuffers`(值为`2`))个`MediaBuffer`, 后问时会考虑进去这个前提:
```
// frameworks/av/media/libstagefright/RemoteMediaSource.cpp
status_t RemoteMediaSource::read(
        MediaBufferBase **buffer, const MediaSource::ReadOptions *options) {
    return mTrack->read(buffer, reinterpret_cast<const MediaSource::ReadOptions*>(options));
}

// frameworks/av/media/libstagefright/MediaTrack.cpp
status_t MediaTrackCUnwrapper::read(MediaBufferBase **buffer, const ReadOptions *options) {
    ...
    CMediaBuffer *buf = nullptr;
    media_status_t ret = wrapper->read(wrapper->data, &buf, opts, seekPosition);
    if (ret == AMEDIA_OK && buf != nullptr) {
        *buffer = (MediaBufferBase*)buf->handle;
        MetaDataBase &meta = (*buffer)->meta_data();
        AMediaFormat *format = buf->meta_data(buf->handle);
        // only convert the keys we're actually expecting, as doing
        // the full convertMessageToMetadata() for every buffer is
        // too expensive
        int64_t val64;
        if (format->mFormat->findInt64("timeUs", &val64)) {
            meta.setInt64(kKeyTime, val64);
            ...
        }
    } else {
        *buffer = nullptr;
    }

    return reverse_translate_error(ret);
}

// frameworks/av/include/media/MediaExtractorPluginHelper.h
inline CMediaTrack *wrap(MediaTrackHelper *track) {
    ...
    wrapper->read = [](void *data, CMediaBuffer **buffer,  uint32_t options, int64_t seekPosUs)
            -> media_status_t {
        MediaTrackHelper::ReadOptions opts(options, seekPosUs);
        MediaBufferHelper *buf = NULL;
        media_status_t ret = ((MediaTrackHelper*)data)->read(&buf, &opts);
        if (ret == AMEDIA_OK && buf != nullptr) {
            *buffer = buf->mBuffer;
        }
        return ret;
    };
    ...
}

// frameworks/av/media/extractors/mp4/MPEG4Extractor.cpp
media_status_t MPEG4Source::read(
        MediaBufferHelper **out, const ReadOptions *options) {
    ...
    if (mBuffer == NULL) {
        ...
        err = mBufferGroup->acquire_buffer(&mBuffer);
        ...
    }
    ...
}

// frameworks/av/include/media/MediaExtractorPluginHelper.h
class MediaBufferGroupHelper {
private:
    CMediaBufferGroup *mGroup;
    std::map<CMediaBuffer*, MediaBufferHelper*> mBufferHelpers;
public:
    media_status_t acquire_buffer(
            MediaBufferHelper **buffer, bool nonBlocking = false, size_t requestedSize = 0) {
        CMediaBuffer *buf = nullptr;
        media_status_t ret =
                mGroup->acquire_buffer(mGroup->handle, &buf, nonBlocking, requestedSize);
        if (ret == AMEDIA_OK && buf != nullptr) {
            auto helper = mBufferHelpers.find(buf);
            if (helper == mBufferHelpers.end()) {
                MediaBufferHelper* newHelper = new MediaBufferHelper(buf);
                mBufferHelpers.insert(std::make_pair(buf, newHelper));
                *buffer = newHelper;
            } else {
                *buffer = helper->second;
            }
        } else {
            *buffer = nullptr;
        }
        return ret;
    }
    ...
}

// frameworks/av/media/libstagefright/include/media/stagefright/MediaBufferGroup.h
class MediaBufferGroup : public MediaBufferObserver {
public:
    CMediaBufferGroup *wrap() {
        ...
        mWrapper->acquire_buffer = [](void *handle,
                CMediaBuffer **buf, bool nonBlocking, size_t requestedSize) -> media_status_t {
            MediaBufferBase *acquiredBuf = nullptr;
            status_t err = ((MediaBufferGroup*)handle)->acquire_buffer(
                    &acquiredBuf, nonBlocking, requestedSize);
            if (err == OK && acquiredBuf != nullptr) {
                *buf = acquiredBuf->wrap();
            } else {
                *buf = nullptr;
            }
            return translate_error(err);
        };
        ...
    }

// frameworks/av/media/libstagefright/foundation/MediaBufferGroup.cpp
status_t MediaBufferGroup::acquire_buffer(
        MediaBufferBase **out, bool nonBlocking, size_t requestedSize) {
    Mutex::Autolock autoLock(mInternal->mLock);
    for (;;) {
        ...
        auto free = mInternal->mBuffers.end();
        for (auto it = mInternal->mBuffers.begin(); it != mInternal->mBuffers.end(); ++it) {
            const size_t size = (*it)->size();
            ...
        }
        if (buffer == nullptr
                && (free != mInternal->mBuffers.end()
                    || mInternal->mBuffers.size() < mInternal->mGrowthLimit)) {
            // We alloc before we free so failure leaves group unchanged.
            const size_t allocateSize = requestedSize == 0 ? biggest :
                    requestedSize < SIZE_MAX / 3 * 2 /* NB: ordering */ ?
                    requestedSize * 3 / 2 : requestedSize;
            buffer = new MediaBuffer(allocateSize);
            ...
        }
        if (buffer != nullptr) {
            buffer->add_ref();
            buffer->reset();
            *out = buffer;
            return OK;
        }
        if (nonBlocking) {
            *out = nullptr;
            return WOULD_BLOCK;
        }
        // All buffers are in use, block until one of them is returned.
        mInternal->mCondition.wait(mInternal->mLock);
    }
    // Never gets here.
}

// frameworks/av/media/libstagefright/foundation/MediaBuffer.cpp
MediaBuffer::MediaBuffer(size_t size)
    : mObserver(NULL),
      mRefCount(0),
      mData(NULL),
      mSize(size),
      mRangeOffset(0),
      mRangeLength(size),
      mOwnsData(true),
      mMetaData(new MetaDataBase) {
#if !defined(NO_IMEMORY) && !defined(__ANDROID_APEX__)
    if (size < kSharedMemThreshold
            || std::atomic_load_explicit(&mUseSharedMemory, std::memory_order_seq_cst) == 0) {
#endif
        mData = malloc(size);
#if !defined(NO_IMEMORY) && !defined(__ANDROID_APEX__)
    } else {
        ALOGV("creating memoryDealer");
        size_t newSize = 0;
        if (!__builtin_add_overflow(size, sizeof(SharedControl), &newSize)) {
            sp<MemoryDealer> memoryDealer = new MemoryDealer(newSize, "MediaBuffer");
            mMemory = memoryDealer->allocate(newSize);
        }
        if (mMemory == NULL) {
            ALOGW("Failed to allocate shared memory, trying regular allocation!");
            mData = malloc(size);
            if (mData == NULL) {
                ALOGE("Out of memory");
            }
        } else {
            getSharedControl()->clear();
            mData = (uint8_t *)mMemory->unsecurePointer() + sizeof(SharedControl);
            ALOGV("Allocated shared mem buffer of size %zu @ %p", size, mData);
        }
    }
#endif
}
```
上述过程, `MediaBuffer`根据其`size`的要求, 自行确定了是否使用共享内存的方式创建, 创建完成后, 数据指针被保存到其自身的`mData`成员中, 创建完成后`MediaBuffer`被封装到`newHelper->mBuffer->handle`中返回给上层
在`CMediaBufferGroup::acquire_buffer()`中, `newHelper`:
`newHelper`: `MediaBufferHelper`
`newHelper->mBuffer`: `CMediaBuffer`
`newHelper->mBuffer->handle`: `MediaBufferBase` -> `MediaBuffer`  

对于上述过程的最后一个函数, 也就是`MediaBufferGroup::acquire_buffer()`中, 只有`for (auto it = mInternal->mBuffers.begin(); it != mInternal->mBuffers.end(); ++it)`没有找到合适的`buffer`, 才会申请新的`buffer`

至此, 可以知道`mediaserver`所获取到的数据结构即`MediaBufferBase`, 回到`BpMediaSource::readMultiple()`
```

class BpMediaSource : public BpInterface<IMediaSource> {
public:
    virtual status_t readMultiple(
            Vector<MediaBufferBase *> *buffers, uint32_t maxNumBuffers,
            const MediaSource::ReadOptions *options) {
        ALOGV("readMultiple");
        if (buffers == NULL || !buffers->isEmpty()) {
            return BAD_VALUE;
        }
        Parcel data, reply;
        data.writeInterfaceToken(BpMediaSource::getInterfaceDescriptor());
        data.writeUint32(maxNumBuffers);
        if (options != nullptr) {
            data.writeByteArray(sizeof(*options), (uint8_t*) options);
        }
        status_t ret = remote()->transact(READMULTIPLE, data, &reply);
        mMemoryCache.gc();
        if (ret != NO_ERROR) {
            return ret;
        }
        // wrap the returned data in a vector of MediaBuffers
        int32_t buftype;
        uint32_t bufferCount = 0;
        while ((buftype = reply.readInt32()) != NULL_BUFFER) {
            LOG_ALWAYS_FATAL_IF(bufferCount >= maxNumBuffers,
                    "Received %u+ buffers and requested %u buffers",
                    bufferCount + 1, maxNumBuffers);
            MediaBuffer *buf;
            if (buftype == SHARED_BUFFER || buftype == SHARED_BUFFER_INDEX) {
                uint64_t index = reply.readUint64();
                ALOGV("Received %s index %llu",
                        buftype == SHARED_BUFFER ? "SHARED_BUFFER" : "SHARED_BUFFER_INDEX",
                        (unsigned long long) index);
                sp<IMemory> mem;
                if (buftype == SHARED_BUFFER) {
                    sp<IBinder> binder = reply.readStrongBinder();
                    mem = interface_cast<IMemory>(binder);
                    LOG_ALWAYS_FATAL_IF(mem.get() == nullptr,
                            "Received NULL IMemory for shared buffer");
                    mMemoryCache.insert(index, mem);
                } else {
                    mem = mMemoryCache.lookup(index);
                    LOG_ALWAYS_FATAL_IF(mem.get() == nullptr,
                            "Received invalid IMemory index for shared buffer: %llu",
                            (unsigned long long)index);
                }
                size_t offset = reply.readInt32();
                size_t length = reply.readInt32();
                buf = new RemoteMediaBufferWrapper(mem);
                buf->set_range(offset, length);
                buf->meta_data().updateFromParcel(reply);
            } else { // INLINE_BUFFER
                int32_t len = reply.readInt32();
                ALOGV("INLINE_BUFFER status %d and len %d", ret, len);
                buf = new MediaBuffer(len);
                reply.read(buf->data(), len);
                buf->meta_data().updateFromParcel(reply);
            }
            buffers->push_back(buf);
            ++bufferCount;
            ++mBuffersSinceStop;
        }
        ret = reply.readInt32();
        ALOGV("readMultiple status %d, bufferCount %u, sinceStop %u",
                ret, bufferCount, mBuffersSinceStop);
        if (bufferCount && ret == WOULD_BLOCK) {
            ret = OK;
        }
        return ret;
    }
    ...
}

// frameworks/av/media/libstagefright/include/media/stagefright/MediaBuffer.h
class MediaBuffer : public MediaBufferBase {
public:
    ...
#if !defined(NO_IMEMORY) && !defined(__ANDROID_APEX__)
    MediaBuffer(const sp<IMemory> &mem) :
         // TODO: Using unsecurePointer() has some associated security pitfalls
         //       (see declaration for details).
         //       Either document why it is safe in this case or address the
         //       issue (e.g. by copying).
        MediaBuffer((uint8_t *)mem->unsecurePointer() + sizeof(SharedControl), mem->size()) {
        // delegate and override mMemory
        mMemory = mem;
    }
#endif
    ...
}

// frameworks/av/media/libstagefright/foundation/MediaBuffer.cpp
MediaBuffer::MediaBuffer(void *data, size_t size)
    : mObserver(NULL),
      mRefCount(0),
      mData(data),
      mSize(size),
      mRangeOffset(0),
      mRangeLength(size),
      mOwnsData(false),
      mMetaData(new MetaDataBase) {
}
```
显然, 构造了`RemoteMediaBufferWrapper`(其继承关系:`RemoteMediaBufferWrapper` -> `MediaBuffer` -> `MediaBufferBase`), 再次回到`NuPlayer::GenericSource::readBuffer()`:
```
void NuPlayer::GenericSource::readBuffer(
        media_track_type trackType, int64_t seekTimeUs, MediaPlayerSeekMode mode,
        int64_t *actualTimeUs, bool formatChange) { 1;
    ...
    int32_t generation = getDataGeneration(trackType);
    for (size_t numBuffers = 0; numBuffers < maxBuffers; ) {
        ...
        if (couldReadMultiple) {
            err = source->readMultiple(
                    &mediaBuffers, maxBuffers - numBuffers, &options);
        } else ...
        ...
        for (; id < count; ++id) {
            int64_t timeUs;
            MediaBufferBase *mbuf = mediaBuffers[id];
            ...
            queueDiscontinuityIfNeeded(seeking, formatChange, trackType, track);

            sp<ABuffer> buffer = mediaBufferToABuffer(mbuf, trackType);
            ...
            track->mPackets->queueAccessUnit(buffer);
            formatChange = false;
            seeking = false;
            ++numBuffers;
        }
        ...
    }
    ...
}

// frameworks/av/media/libmediaplayerservice/nuplayer/GenericSource.cpp
sp<ABuffer> NuPlayer::GenericSource::mediaBufferToABuffer(
        MediaBufferBase* mb,
        media_track_type trackType) {
    ...
    if (mIsDrmProtected)   {
        ...

    } else {
        ab = new ABuffer(outLength);
        memcpy(ab->data(),
               (const uint8_t *)mb->data() + mb->range_offset(),
               mb->range_length());
    }
    ...
    return ab;
}
```
此处`mediaBufferToABuffer()`将`MediaBufferBase`(类型为`RemoteMediaBufferWrapper`)转换为`ABuffer`, 并插入`GenericSource`的`track->mPackets`(音频/视频)