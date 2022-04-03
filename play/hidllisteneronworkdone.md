- [`objcpy()`完成`FrameData` -> `C2FrameData`转换](#objcpy完成framedata---c2framedata转换)
- [`holdBufferQueueBlocks()`完成`C2ConstGraphicBlock` -> `GraphicBuffer`的图形缓存导入](#holdbufferqueueblocks完成c2constgraphicblock---graphicbuffer的图形缓存导入)
- [`CCodec::onWorkDone()`完成`GraphicBuffer`的输出](#ccodeconworkdone完成graphicbuffer的输出)
  - [`handleOutputFormatChangeIfNeeded()`打开音频输出](#handleoutputformatchangeifneeded打开音频输出)
  - [`onOutputBufferAvailable()`](#onoutputbufferavailable)
    - [`postDrainAudioQueue_l()`回放音频数据](#postdrainaudioqueue_l回放音频数据)
      - [`AudioOutput::write()`输出音频数据](#audiooutputwrite输出音频数据)
        - [`AudioTrack::write()`回放音频](#audiotrackwrite回放音频)
    - [`postDrainVideoQueue()`回放视频数据](#postdrainvideoqueue回放视频数据)
      - [`MediaCodec::onReleaseOutputBuffer()`释放(并输出)视频帧](#mediacodeconreleaseoutputbuffer释放并输出视频帧)
        - [`Codec2Client::Component::queueToOutputSurface()`交换视频帧到应用的`BBQSurface`](#codec2clientcomponentqueuetooutputsurface交换视频帧到应用的bbqsurface)

`Codec2`组建`Component`通过`IHwComponentListener`也就是`BnHwComponentListener::_hidl_onWorkDone()`接口通知`mediaserver`:
```
// frameworks/av/media/codec2/hidl/client/client.cpp
struct Codec2Client::Component::HidlListener : public IComponentListener {
    std::weak_ptr<Component> component;
    std::weak_ptr<Listener> base;

    virtual Return<void> onWorkDone(const WorkBundle& workBundle) override {
        ... ...
        if (!objcpy(&workItems, workBundle)) {
            LOG(DEBUG) << "onWorkDone -- received corrupted WorkBundle.";
            return Void();
        }
        // release input buffers potentially held by the component from queue
        std::shared_ptr<Codec2Client::Component> strongComponent =
                component.lock();
        if (strongComponent) {
            strongComponent->handleOnWorkDone(workItems);
        }
        if (std::shared_ptr<Codec2Client::Listener> listener = base.lock()) {
            listener->onWorkDone(component, workItems);
        } else ... ...
    }
```

## `objcpy()`完成`FrameData` -> `C2FrameData`转换
`objcpy()`是个非常重要的操作:
```
// frameworks/av/media/codec2/hidl/1.0/utils/types.cpp
// WorkBundle -> std::list<std::unique_ptr<C2Work>>
bool objcpy(std::list<std::unique_ptr<C2Work>>* d, const WorkBundle& s) {
    // Convert BaseBlocks to C2BaseBlocks.
    std::vector<C2BaseBlock> dBaseBlocks(s.baseBlocks.size());
    for (size_t i = 0; i < s.baseBlocks.size(); ++i) {
        if (!objcpy(&dBaseBlocks[i], s.baseBlocks[i])) {
            LOG(ERROR) << "Invalid WorkBundle::baseBlocks["
                       << i << "].";
            return false;
        }
    }

    d->clear();
    for (const Work& sWork : s.works) {
        d->emplace_back(std::make_unique<C2Work>());
        C2Work& dWork = *d->back();

        // chain info is not in use currently.

        // input
        if (!objcpy(&dWork.input, sWork.input, dBaseBlocks)) {
            LOG(ERROR) << "Invalid Work::input.";
            return false;
        }

        // worklet(s)
        dWork.worklets.clear();
        for (const Worklet& sWorklet : sWork.worklets) {
            std::unique_ptr<C2Worklet> dWorklet = std::make_unique<C2Worklet>();
            ... ...
            // output
            if (!objcpy(&dWorklet->output, sWorklet.output, dBaseBlocks)) {
                LOG(ERROR) << "Invalid Worklet::output.";
                return false;
            }

            dWork.worklets.emplace_back(std::move(dWorklet));
        }

        // workletsProcessed
        dWork.workletsProcessed = sWork.workletsProcessed;

        // result
        dWork.result = static_cast<c2_status_t>(sWork.result);
    }

    return true;
}
```
对于`objcpy(&dBaseBlocks[i], s.baseBlocks[i])`:
```
bool objcpy(C2BaseBlock* d, const BaseBlock& s) {
    switch (s.getDiscriminator()) {
    case BaseBlock::hidl_discriminator::nativeBlock: {
            native_handle_t* sHandle =
                    native_handle_clone(s.nativeBlock());
            ... ...
            const C2Handle *sC2Handle =
                    reinterpret_cast<const C2Handle*>(sHandle);

            d->linear = _C2BlockFactory::CreateLinearBlock(sC2Handle);
            ... ...
            d->graphic = _C2BlockFactory::CreateGraphicBlock(sC2Handle);
            ... ...
        }
        ... ...
```
对于`_C2BlockFactory::CreateGraphicBlock()`:
```
// frameworks/av/media/codec2/vndk/platform/C2BqBuffer.cpp
std::shared_ptr<C2GraphicBlock> _C2BlockFactory::CreateGraphicBlock(
        const C2Handle *handle) {
    // TODO: get proper allocator? and mutex?
    static std::unique_ptr<C2AllocatorGralloc> sAllocator = std::make_unique<C2AllocatorGralloc>(0);

    std::shared_ptr<C2GraphicAllocation> alloc;
    if (C2AllocatorGralloc::CheckHandle(handle)) {
        ... ...
        android::_UnwrapNativeCodec2GrallocMetadata(
                handle, &width, &height, &format, &usage, &stride, &generation, &bqId, &bqSlot);
        c2_status_t err = sAllocator->priorGraphicAllocation(handle, &alloc);
        if (err == C2_OK) {
            std::shared_ptr<C2GraphicBlock> block;
            if (bqId || bqSlot) {
                // BQBBP
                std::shared_ptr<C2BufferQueueBlockPoolData> poolData =
                        std::make_shared<C2BufferQueueBlockPoolData>(generation,
                                                                     bqId,
                                                                     (int32_t)bqSlot,
                                                                     nullptr,
                                                                     nullptr);
                block = _C2BlockFactory::CreateGraphicBlock(alloc, poolData);
            } else ... ...
            return block;
        }
    }
    return nullptr;
}

// frameworks/av/media/codec2/vndk/C2Buffer.cpp
std::shared_ptr<C2GraphicBlock> _C2BlockFactory::CreateGraphicBlock(
        const std::shared_ptr<C2GraphicAllocation> &alloc,
        const std::shared_ptr<_C2BlockPoolData> &data, const C2Rect &allottedCrop) {
    std::shared_ptr<C2Block2D::Impl> impl =
        std::make_shared<C2Block2D::Impl>(alloc, data, allottedCrop);
    return std::shared_ptr<C2GraphicBlock>(new C2GraphicBlock(impl, *impl));
}
```
此时`C2GraphicBlock`被创建, 并配置给了`dBaseBlocks[i]`(类型为`C2BaseBlock`)的`graphic`成员.
回到`bool objcpy(std::list<std::unique_ptr<C2Work>>* d, const WorkBundle& s)`, 对于`objcpy(&dWorklet->output, sWorklet.output, dBaseBlocks)`:
```
// frameworks/av/media/codec2/hidl/1.0/utils/types.cpp
// FrameData -> C2FrameData
bool objcpy(C2FrameData* d, const FrameData& s,
        const std::vector<C2BaseBlock>& baseBlocks) {
    ... ...
    if (!objcpy(&d->ordinal, s.ordinal)) {
        LOG(ERROR) << "Invalid FrameData::ordinal.";
        return false;
    }
    d->buffers.clear();
    d->buffers.reserve(s.buffers.size());
    for (const Buffer& sBuffer : s.buffers) {
        std::shared_ptr<C2Buffer> dBuffer;
        if (!objcpy(&dBuffer, sBuffer, baseBlocks)) {
            LOG(ERROR) << "Invalid FrameData::buffers.";
            return false;
        }
        d->buffers.emplace_back(dBuffer);
    }
    ... ...
```
对于`objcpy(&d->ordinal, s.ordinal)`:
```
// frameworks/av/media/codec2/hidl/1.0/utils/types.cpp
bool objcpy(C2WorkOrdinalStruct *d, const WorkOrdinal &s) {
    d->frameIndex = c2_cntr64_t(s.frameIndex);
    d->timestamp = c2_cntr64_t(s.timestampUs);
    d->customOrdinal = c2_cntr64_t(s.customOrdinal);
    return true;
}
```

而对于`objcpy(&dBuffer, sBuffer, baseBlocks)`:
```
// frameworks/av/media/codec2/hidl/1.0/utils/types.cpp
// Buffer -> C2Buffer
// Note: The native handles will be cloned.
bool objcpy(std::shared_ptr<C2Buffer>* d, const Buffer& s,
        const std::vector<C2BaseBlock>& baseBlocks) {
    *d = nullptr;
    ... ...
    // Construct a block.
    switch (baseBlock.type) {
    case C2BaseBlock::LINEAR:
        ... ...
    case C2BaseBlock::GRAPHIC:
        if (!createGraphicBuffer(d, baseBlock.graphic, sBlockMeta, dFence)) {
            LOG(ERROR) << "Invalid C2BaseBlock::graphic.";
            return false;
        }
        break;
    ... ...
    }
    ... ...
    for (C2Param* param : params) {
        ... ...
        c2_status_t status =
                (*d)->setInfo(std::static_pointer_cast<C2Info>(c2param));
        ... ...
    }

    return true;
}
```
综上`objcopy()`完成以下几项工作:
* 将`WorkBundle`转化为`C2GraphicBlock`
* 根据`C2GraphicBlock`, 完成`FrameData` -> `C2FrameData`
  * 循环完成`Buffer` -> `C2Buffer`的转换

至此`C2FrameData`构造完成并置换至`C2Work::worklets::output`中.

## `holdBufferQueueBlocks()`完成`C2ConstGraphicBlock` -> `GraphicBuffer`的图形缓存导入
回到`HidlListener::onWorkDone()`的`strongComponent->handleOnWorkDone()`:
```
// frameworks/av/media/codec2/hidl/client/client.cpp
void Codec2Client::Component::handleOnWorkDone(
        const std::list<std::unique_ptr<C2Work>> &workItems) {
    // Output bufferqueue-based blocks' lifetime management
    mOutputBufferQueue->holdBufferQueueBlocks(workItems);
}
```
`mOutputBufferQueue`类型为`OutputBufferQueue`, 故:
```
// frameworks/av/media/codec2/hidl/client/output.cpp
void OutputBufferQueue::holdBufferQueueBlocks(
        const std::list<std::unique_ptr<C2Work>>& workList) {
    forEachBlock(workList,
                 std::bind(&OutputBufferQueue::registerBuffer,
                           this, std::placeholders::_1));
}
```
对于`forEachBlock()`:
```
// frameworks/av/media/codec2/hidl/1.0/utils/types.cpp
void forEachBlock(const std::list<std::unique_ptr<C2Work>>& workList,
                  BlockProcessor process,
                  bool processInput, bool processOutput) {
    for (const std::unique_ptr<C2Work>& work : workList) {
        if (!work) {
            continue;
        }
        if (processInput) {
            forEachBlock(work->input, process);
        }
        if (processOutput) {
            for (const std::unique_ptr<C2Worklet>& worklet : work->worklets) {
                if (worklet) {
                    forEachBlock(worklet->output,
                                 process);
                }
            }
        }
    }
}

template <typename BlockProcessor>
void forEachBlock(C2FrameData& frameData,
                  BlockProcessor process) {
    for (const std::shared_ptr<C2Buffer>& buffer : frameData.buffers) {
        if (buffer) {
            for (const C2ConstGraphicBlock& block :
                    buffer->data().graphicBlocks()) {
                process(block);
            }
        }
    }
}
```
`process`正是上文代码中的`std::bind(&OutputBufferQueue::registerBuffer, this, std::placeholders::_1));`, 这相当与`OutputBufferQueue::registerBuffer()`:
```
// frameworks/av/media/codec2/hidl/client/output.cpp
bool OutputBufferQueue::registerBuffer(const C2ConstGraphicBlock& block) {
    std::shared_ptr<_C2BlockPoolData> data =
            _C2BlockFactory::GetGraphicBlockPoolData(block);
    ... ...
    // If the block is not bufferqueue-based, do nothing.
    if (!_C2BlockFactory::GetBufferQueueData(
            data, &oldGeneration, &oldId, &oldSlot) || (oldId == 0)) {
        return false;
    }
    ... ...
    // If the block's bqId is the same as the desired bqId, just hold.
    if ((oldId == mBqId) && (oldGeneration == mGeneration)) {
        ... ...
        _C2BlockFactory::HoldBlockFromBufferQueue(data, mOwner, getHgbp(mIgbp), mSyncMem);
        mPoolDatas[oldSlot] = data;
        mBuffers[oldSlot] = createGraphicBuffer(block);
        mBuffers[oldSlot]->setGenerationNumber(mGeneration);
        return true;
    }
    ... ...
}

// Create a GraphicBuffer object from a graphic block.
sp<GraphicBuffer> createGraphicBuffer(const C2ConstGraphicBlock& block) {
    ... ....
    _UnwrapNativeCodec2GrallocMetadata(
            block.handle(), &width, &height, &format, &usage,
            &stride, &generation, &bqId, reinterpret_cast<uint32_t*>(&bqSlot));
    native_handle_t *grallocHandle =
            UnwrapNativeCodec2GrallocHandle(block.handle());
    sp<GraphicBuffer> graphicBuffer =
            new GraphicBuffer(grallocHandle,
                              GraphicBuffer::CLONE_HANDLE,
                              width, height, format,
                              1, usage, stride);
    native_handle_delete(grallocHandle);
    return graphicBuffer;
}
```
`createGraphicBuffer()`负责从`C2ConstGraphicBlock`到`GraphicBuffer`的转化(导入), 并保存到`OutputBufferQueue`的`mBuffers[oldSlot]`. 而`C2ConstGraphicBlock`来子上文转化后的`C2FrameData::buffers(C2Buffer)::mImpl(C2Buffer::Impl)::mData(BufferDataBuddy)::mImpl(C2BufferData::Impl)::mGraphicBlocks(C2ConstGraphicBlock)`
至此, `GraphicBuffer`已经完成从`IComponent`到`mediaserver`的传递.

## `CCodec::onWorkDone()`完成`GraphicBuffer`的输出
回到`HidlListener::onWorkDone()`的`listener->onWorkDone()`, 其`listener`类型是`Codec2Client::Listener`, 其实现是`CCodec::ClientListener`
```
// frameworks/av/media/codec2/sfplugin/CCodec.cpp
struct CCodec::ClientListener : public Codec2Client::Listener {
    explicit ClientListener(const wp<CCodec> &codec) : mCodec(codec) {}
    virtual void onWorkDone(
            const std::weak_ptr<Codec2Client::Component>& component,
            std::list<std::unique_ptr<C2Work>>& workItems) override {
        (void)component;
        sp<CCodec> codec(mCodec.promote());
        if (!codec) {
            return;
        }
        codec->onWorkDone(workItems);
    }
```
显然`codec`类型为`CCodec`:
```
// frameworks/av/media/codec2/sfplugin/CCodec.cpp
void CCodec::onWorkDone(std::list<std::unique_ptr<C2Work>> &workItems) {
    ... ...
    (new AMessage(kWhatWorkDone, this))->post();
}

void CCodec::onMessageReceived(const sp<AMessage> &msg) {
    ... ...
    switch (msg->what()) {
        case kWhatAllocate:
        ... ...
        case kWhatWorkDone: {
            ... ...
            mChannel->onWorkDone(
                    std::move(work), outputFormat, initData ? initData.get() : nullptr);
            break;
        }
        ... ...
    }
}
```
`mChannel`的类型为`CCodecBufferChannel`:
```
void CCodecBufferChannel::onWorkDone(
        std::unique_ptr<C2Work> work, const sp<AMessage> &outputFormat,
        const C2StreamInitDataInfo::output *initData) {
    if (handleWork(std::move(work), outputFormat, initData)) {
        feedInputBufferIfAvailable();
    }
}

bool CCodecBufferChannel::handleWork(
        std::unique_ptr<C2Work> work,
        const sp<AMessage> &outputFormat,
        const C2StreamInitDataInfo::output *initData) {
    ... ...
    sendOutputBuffers();
    return true;
}

void CCodecBufferChannel::sendOutputBuffers() {
    ... ...
    while (true) {
        ... ...
        switch (action) {
        case OutputBuffers::SKIP:
        ... ...
        case OutputBuffers::NOTIFY_CLIENT:
            output.unlock();
            mCallback->onOutputBufferAvailable(index, outBuffer);
            break;
        ... ...
        }
    }
}
```
`mCallback`的类型为`MediaCodec::BufferCallback`, 所以:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
void BufferCallback::onOutputBufferAvailable(
        size_t index, const sp<MediaCodecBuffer> &buffer) {
    sp<AMessage> notify(mNotify->dup());
    notify->setInt32("what", kWhatDrainThisBuffer);
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
                ... ...
                case kWhatDrainThisBuffer:
                {
                    ... ...
                    if (mFlags & kFlagIsAsync) {
                        sp<RefBase> obj;
                        CHECK(msg->findObject("buffer", &obj));
                        sp<MediaCodecBuffer> buffer = static_cast<MediaCodecBuffer *>(obj.get());

                        // In asynchronous mode, output format change is processed immediately.
                        handleOutputFormatChangeIfNeeded(buffer);
                        onOutputBufferAvailable();
                    } else ... ...
                    break;
                }
                ... ...
```

### `handleOutputFormatChangeIfNeeded()`打开音频输出
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
void MediaCodec::handleOutputFormatChangeIfNeeded(const sp<MediaCodecBuffer> &buffer) {
    ... ...
    if (mFlags & kFlagIsAsync) {
        onOutputFormatChanged();
    } else ... ...
    ... ...
}

void MediaCodec::onOutputFormatChanged() {
    if (mCallback != NULL) {
        sp<AMessage> msg = mCallback->dup();
        msg->setInt32("callbackID", CB_OUTPUT_FORMAT_CHANGED);
        msg->setMessage("format", mOutputFormat);
        msg->post();
    }
}
```
`CB_OUTPUT_FORMAT_CHANGED`被发送到`NuPlayer::Decoder::onMessageReceived()`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoder.cpp
void NuPlayer::Decoder::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        {
            ... ...
            switch (cbID) {
                case MediaCodec::CB_INPUT_AVAILABLE:
                ... ...
                case MediaCodec::CB_OUTPUT_FORMAT_CHANGED:
                {
                    ... ...
                    handleOutputFormatChange(format);
                    break;
                }
                ... ...

void NuPlayer::Decoder::handleOutputFormatChange(const sp<AMessage> &format) {
    if (!mIsAudio) {
        ... ...
    } else if (mRenderer != NULL) {
        ... ...
        sp<AMessage> reply = new AMessage(kWhatAudioOutputFormatChanged, this);
        reply->setInt32("generation", mBufferGeneration);
        mRenderer->changeAudioFormat(
                format, false /* offloadOnly */, hasVideo,
                flags, mSource->isStreaming(), reply);
    }
}
```
`mRenderer->changeAudioFormat()`即`NuPlayer::Renderer::changeAudioFormat()`
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerRenderer.cpp
void NuPlayer::Renderer::changeAudioFormat(
        const sp<AMessage> &format,
        bool offloadOnly,
        bool hasVideo,
        uint32_t flags,
        bool isStreaming,
        const sp<AMessage> &notify) {
    sp<AMessage> meta = new AMessage;
   ... ...
    sp<AMessage> msg = new AMessage(kWhatChangeAudioFormat, this);
    ... ...
    msg->post();
}

void NuPlayer::Renderer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatOpenAudioSink:
        ... ...
        case kWhatChangeAudioFormat:
        {
            ... ...
            if (queueGeneration != getQueueGeneration(true /* audio */)
                    || mAudioQueue.empty()) {
                onChangeAudioFormat(meta, notify);
                break;
            }
            ... ...
            break;
        }
        ... ...

void NuPlayer::Renderer::onChangeAudioFormat(
        const sp<AMessage> &meta, const sp<AMessage> &notify) {
    ... ...
    status_t err = onOpenAudioSink(format, offloadOnly, hasVideo, flags, isStreaming);
    ... ...
    notify->post();
}

status_t NuPlayer::Renderer::onOpenAudioSink(
        const sp<AMessage> &format,
        bool offloadOnly,
        bool hasVideo,
        uint32_t flags,
        bool isStreaming) {
    ... ...
    if (!offloadOnly && !offloadingAudio()) {
        ... ...
        status_t err = mAudioSink->open(
                    sampleRate,
                    numChannels,
                    (audio_channel_mask_t)channelMask,
                    audioFormat,
                    0 /* bufferCount - unused */,
                    mUseAudioCallback ? &NuPlayer::Renderer::AudioSinkCallback : NULL,
                    mUseAudioCallback ? this : NULL,
                    (audio_output_flags_t)pcmFlags,
                    NULL,
                    doNotReconnect,
                    frameCount);
        ... ...
    }
    if (audioSinkChanged) {
        onAudioSinkChanged();
    }
    mAudioTornDown = false;
    return OK;
}
```
而`AudioOutput::open()`:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
status_t MediaPlayerService::AudioOutput::open(
        uint32_t sampleRate, int channelCount, audio_channel_mask_t channelMask,
        audio_format_t format, int bufferCount,
        AudioCallback cb, void *cookie,
        audio_output_flags_t flags,
        const audio_offload_info_t *offloadInfo,
        bool doNotReconnect,
        uint32_t suggestedFrameCount)
{
    ... ...
    if (!(reuse && bothOffloaded)) {
        ALOGV("creating new AudioTrack");

        if (mCallback != NULL) {
            newcbd = new CallbackData(this);
            t = new AudioTrack(
                    mStreamType,
                    sampleRate,
                    format,
                    channelMask,
                    frameCount,
                    flags,
                    CallbackWrapper,
                    newcbd,
                    0,  // notification frames
                    mSessionId,
                    AudioTrack::TRANSFER_CALLBACK,
                    offloadInfo,
                    mAttributionSource,
                    mAttributes,
                    doNotReconnect,
                    1.0f,  // default value for maxRequiredSpeed
                    mSelectedDeviceId);
        } else ...
    }
    ... ...
    mTrack = t;
    return updateTrack();
}
```

### `onOutputBufferAvailable()`
```
void MediaCodec::onOutputBufferAvailable() {
    ... ...
    while ((index = dequeuePortBuffer(kPortIndexOutput)) >= 0) {
        ... ...
        msg->setInt32("callbackID", CB_OUTPUT_AVAILABLE);
        ... ...
        statsBufferReceived(timeUs, buffer);
        msg->post();
    }
}
```
`msg->post()`的消息讲由上层的`NuPlayer::Decoder::onMessageReceived()`处理:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoder.cpp
void NuPlayer::Decoder::onMessageReceived(const sp<AMessage> &msg) {
    ... ...
    switch (msg->what()) {
        case kWhatCodecNotify:
        {
            ... ...
            int32_t cbID;
            CHECK(msg->findInt32("callbackID", &cbID));
            ... ...
            switch (cbID) {
                ... ...
                case MediaCodec::CB_OUTPUT_AVAILABLE:
                {
                    ... ...
                    handleAnOutputBuffer(index, offset, size, timeUs, flags);
                    break;
                }
                ... ....

bool NuPlayer::Decoder::handleAnOutputBuffer(
        size_t index,
        size_t offset,
        size_t size,
        int64_t timeUs,
        int32_t flags) {
    ... ...
    notifyResumeCompleteIfNecessary();
    if (mRenderer != NULL) {
        // send the buffer to renderer.
        mRenderer->queueBuffer(mIsAudio, buffer, reply);
        if (eos && !isDiscontinuityPending()) {
            mRenderer->queueEOS(mIsAudio, ERROR_END_OF_STREAM);
        }
    }
    return true;
}
```
对于音频输出, `mRenderer`是成立的, 类型为`NuPlayer::Renderer`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerRenderer.cpp
void NuPlayer::Renderer::queueBuffer(
        bool audio,
        const sp<MediaCodecBuffer> &buffer,
        const sp<AMessage> &notifyConsumed) {
    sp<AMessage> msg = new AMessage(kWhatQueueBuffer, this);
    ... ...
    msg->post();
}

void NuPlayer::Renderer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatOpenAudioSink:
        ... ...
        case kWhatQueueBuffer:
        {
            onQueueBuffer(msg);
            break;
        }
        ... ...

void NuPlayer::Renderer::onQueueBuffer(const sp<AMessage> &msg) {
    ... ...
    sp<RefBase> obj;
    CHECK(msg->findObject("buffer", &obj));
    sp<MediaCodecBuffer> buffer = static_cast<MediaCodecBuffer *>(obj.get())
    ... ...
    QueueEntry entry;
    entry.mBuffer = buffer;
    ... ...
    if (audio) {
        Mutex::Autolock autoLock(mLock);
        mAudioQueue.push_back(entry);
        postDrainAudioQueue_l();
    } else {
        mVideoQueue.push_back(entry);
        postDrainVideoQueue();
    }
    ... ...
    syncQueuesDone_l();
}
```
#### `postDrainAudioQueue_l()`回放音频数据
```
void NuPlayer::Renderer::postDrainAudioQueue_l(int64_t delayUs) {
    ... ...
    sp<AMessage> msg = new AMessage(kWhatDrainAudioQueue, this);
    msg->setInt32("drainGeneration", mAudioDrainGeneration);
    msg->post(delayUs);
}
```
##### `AudioOutput::write()`输出音频数据
```
void NuPlayer::Renderer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatOpenAudioSink:
        ... ...

        case kWhatDrainAudioQueue:
        {
            ... ...
            int32_t generation;
            CHECK(msg->findInt32("drainGeneration", &generation));
            ... ...
            if (onDrainAudioQueue()) {
                ... ...
                postDrainAudioQueue_l(delayUs);
            }
            break;
        }
        ... ...

bool NuPlayer::Renderer::onDrainAudioQueue() {
    ... ...
    while (!mAudioQueue.empty()) 
        ... ...
        ssize_t written = mAudioSink->write(entry->mBuffer->data() + entry->mOffset,
                                            copy, false /* blocking */);
        ... ...
        }
    }
    ... ...
    return reschedule;
}
```

###### `AudioTrack::write()`回放音频
`NuPlayer::Render`的`mAudioSink`为创建时由`NuPlayer`传递的, 因此`AudioOutput::write()`被调用:
```
// frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp
ssize_t MediaPlayerService::AudioOutput::write(const void* buffer, size_t size, bool blocking)
{
    Mutex::Autolock lock(mLock);
    LOG_ALWAYS_FATAL_IF(mCallback != NULL, "Don't call write if supplying a callback.");

    //ALOGV("write(%p, %u)", buffer, size);
    if (mTrack != 0) {
        return mTrack->write(buffer, size, blocking);
    }
    return NO_INIT;
}
```
`mTrack`正式`AudioOutput::open()`时打开的`AudioTrack`.

#### `postDrainVideoQueue()`回放视频数据
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerRenderer.cpp
void NuPlayer::Renderer::postDrainVideoQueue() {
    ... ...
    QueueEntry &entry = *mVideoQueue.begin();

    sp<AMessage> msg = new AMessage(kWhatDrainVideoQueue, this);
    msg->setInt32("drainGeneration", getDrainGeneration(false /* audio */));
    ... ...
    if (!mVideoSampleReceived || mediaTimeUs < mAudioFirstAnchorTimeMediaUs) {
        msg->post();
    } else {
        int64_t twoVsyncsUs = 2 * (mVideoScheduler->getVsyncPeriod() / 1000);

        // post 2 display refreshes before rendering is due
        mMediaClock->addTimer(msg, mediaTimeUs, -twoVsyncsUs);
    }
    mDrainVideoQueuePending = true;
}

void NuPlayer::Renderer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatOpenAudioSink:
        ... ...
        case kWhatDrainVideoQueue:
        {
            ... ...
            onDrainVideoQueue();
            postDrainVideoQueue();
            break;
        }
        ... ...

void NuPlayer::Renderer::onDrainVideoQueue() {
    ... ...
    entry->mNotifyConsumed->setInt64("timestampNs", realTimeUs * 1000LL);
    entry->mNotifyConsumed->setInt32("render", !tooLate);
    entry->mNotifyConsumed->post();
    ... ...
}
```
`entry->mNotifyConsumed`通知了`NuPlayer::Decoder`:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoder.cpp
void NuPlayer::Decoder::onMessageReceived(const sp<AMessage> &msg) {
    ALOGV("[%s] onMessage: %s", mComponentName.c_str(), msg->debugString().c_str());

    switch (msg->what()) {
        case kWhatCodecNotify:
        ... ...
        case kWhatRenderBuffer:
        {
            if (!isStaleReply(msg)) {
                onRenderBuffer(msg);
            }
            break;
        }
        ... ...

void NuPlayer::Decoder::onRenderBuffer(const sp<AMessage> &msg) {
    ... ...
    if (mCodec == NULL) {
        err = NO_INIT;
    } else if (msg->findInt32("render", &render) && render) {
        int64_t timestampNs;
        CHECK(msg->findInt64("timestampNs", &timestampNs));
        err = mCodec->renderOutputBufferAndRelease(bufferIx, timestampNs);
    } else {
        if (!msg->findInt32("eos", &eos) || !eos ||
                !msg->findSize("size", &size) || size) {
            mNumOutputFramesDropped += !mIsAudio;
        }
        err = mCodec->releaseOutputBuffer(bufferIx);
    }
    ... ...
}
```
此场景下`renderOutputBufferAndRelease()`被调用:
```
// frameworks/av/media/libstagefright/MediaCodec.cpp

status_t MediaCodec::renderOutputBufferAndRelease(size_t index, int64_t timestampNs) {
    sp<AMessage> msg = new AMessage(kWhatReleaseOutputBuffer, this);
    msg->setSize("index", index);
    msg->setInt32("render", true);
    msg->setInt64("timestampNs", timestampNs);

    sp<AMessage> response;
    return PostAndAwaitResponse(msg, &response);
}

status_t MediaCodec::PostAndAwaitResponse(
        const sp<AMessage> &msg, sp<AMessage> *response) {
    status_t err = msg->postAndAwaitResponse(response);
    ... ...
    return err;
}
```

##### `MediaCodec::onReleaseOutputBuffer()`释放(并输出)视频帧
`kWhatReleaseOutputBuffer`消息由`MediaCodec::onMessageReceived()`处理:
```
void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        ... ...
        case kWhatReleaseOutputBuffer:
        {
            ... ...
            status_t err = onReleaseOutputBuffer(msg);
            PostReplyWithError(replyID, err);
            break;
        }
        ... ...

status_t MediaCodec::onReleaseOutputBuffer(const sp<AMessage> &msg) {
    ... ...
    if (render && buffer->size() != 0) {
        ... ...
        status_t err = mBufferChannel->renderOutputBuffer(buffer, renderTimeNs);
        ... ...
```

###### `Codec2Client::Component::queueToOutputSurface()`交换视频帧到应用的`BBQSurface`
显然`mBufferChannel`的类型是`CCodecBufferChannel`, 因此:
```
// frameworks/av/media/codec2/sfplugin/CCodecBufferChannel.cpp
status_t CCodecBufferChannel::renderOutputBuffer(
    ... ...
    status_t result = mComponent->queueToOutputSurface(block, qbi, &qbo);
    ... ...
    mCCodecCallback->onOutputFramesRendered(mediaTimeUs, timestampNs);
    return OK;
}
```
`mComponent`的类型是`Codec2Client::Component`, 因此:
```
// frameworks/av/media/codec2/hidl/client/client.cpp
status_t Codec2Client::Component::queueToOutputSurface(
        const C2ConstGraphicBlock& block,
        const QueueBufferInput& input,
        QueueBufferOutput* output) {
    return mOutputBufferQueue->outputBuffer(block, input, output);
}
```
`mOutputBufferQueue`的类型是`mOutputBufferQueue`, 因此:
```
// frameworks/av/media/codec2/hidl/client/output.cpp
status_t OutputBufferQueue::outputBuffer(
        const C2ConstGraphicBlock& block,
        const BnGraphicBufferProducer::QueueBufferInput& input,
        BnGraphicBufferProducer::QueueBufferOutput* output) {
    ... ...
    if (!getBufferQueueAssignment(block, &generation, &bqId, &bqSlot) ||
        bqId == 0) {
        ... ...
    }
    auto syncVar = syncMem ? syncMem->mem() : nullptr;
    status_t status = OK;
    if (syncVar) {
        ... ...
    } else {
        status = outputIgbp->queueBuffer(static_cast<int>(bqSlot),
                                                  input, output);
    }
    ... ...
}

bool getBufferQueueAssignment(const C2ConstGraphicBlock& block,
                              uint32_t* generation,
                              uint64_t* bqId,
                              int32_t* bqSlot) {
    return _C2BlockFactory::GetBufferQueueData(
            _C2BlockFactory::GetGraphicBlockPoolData(block),
            generation, bqId, bqSlot);
}
```

关于Buffer的处理:
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp
std::shared_ptr<_C2BlockPoolData> _C2BlockFactory::GetGraphicBlockPoolData(
        const C2Block2D &block) {
    if (block.mImpl) {
        return block.mImpl->poolData();
    }
    return nullptr;
}
```
`block`(类型: `C2Block2D`)的`mImpl`成员类型为: `_C2MappingBlock2DImpl`, 其实现为`C2Block2D::Impl`, 其`poolData()`返回`C2Block2D::Impl`的`mPoolData`成员, 其类型为`_C2BlockPoolData`, 其实现为`C2BufferQueueBlockPoolData`, 继续`_C2BlockFactory::GetBufferQueueData()`
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp
bool _C2BlockFactory::GetBufferQueueData(
        const std::shared_ptr<const _C2BlockPoolData>& data,
        uint32_t* generation, uint64_t* bqId, int32_t* bqSlot) {
    if (data && data->getType() == _C2BlockPoolData::TYPE_BUFFERQUEUE) {
        const std::shared_ptr<const C2BufferQueueBlockPoolData> poolData =
                std::static_pointer_cast<const C2BufferQueueBlockPoolData>(data);
        poolData->getBufferQueueData(generation, bqId, bqSlot);
        return true;
    }
    return false;
}

void C2BufferQueueBlockPoolData::getBufferQueueData(
        uint32_t* generation, uint64_t* bqId, int32_t* bqSlot) const {
    if (generation) {
        std::scoped_lock<std::mutex> lock(mLock);
        *generation = mGeneration;
        if (bqId) {
            *bqId = mBqId;
        }
        if (bqSlot) {
            *bqSlot = mBqSlot;
        }
    }
}
```

```
经过`getBufferQueueAssignment()`将得到`bqId`和`bqSlot`

回到`OutputBufferQueue::outputBuffer()`, `outputIgbp->queueBuffer()`将索引为`bqSlot`的`GraphicBuffer`, 发送给应用. 此时`mIgbp`的类型是`IGraphicBufferProducer`, 其实现是`BpGraphicBufferProducer`, Binder对端是应用此前所持有的`BBQSurface`中的`BBQBufferQueueProducer`, 继承关系为:`IGraphicBufferProducer` -> `BnGraphicBufferProducer` -> `BufferQueueProducer` -> `BBQBufferQueueProducer`