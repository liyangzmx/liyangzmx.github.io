`mediaserver`通过`IComponent::queue()`发送`C2Work`到`media.swcodec`, 因此:
```
// frameworks/av/media/codec2/hidl/1.0/utils/Component.cpp
// Methods from ::android::hardware::media::c2::V1_0::IComponent
Return<Status> Component::queue(const WorkBundle& workBundle) {
    std::list<std::unique_ptr<C2Work>> c2works;

    if (!objcpy(&c2works, workBundle)) {
        return Status::CORRUPTED;
    }

    // Register input buffers.
    for (const std::unique_ptr<C2Work>& work : c2works) {
        if (work) {
            InputBufferManager::
                    registerFrameData(mListener, work->input);
        }
    }

    return static_cast<Status>(mComponent->queue_nb(&c2works));
}
```
`objcpy`负责`WorkBundle`到`C2Work`的转换, 此处前文有述, 此处略去.
```
// frameworks/av/media/codec2/components/base/SimpleC2Component.cpp +232
c2_status_t SimpleC2Component::queue_nb(std::list<std::unique_ptr<C2Work>> * const items) {
    {
        Mutexed<ExecState>::Locked state(mExecState);
        if (state->mState != RUNNING) {
            return C2_BAD_STATE;
        }
    }
    bool queueWasEmpty = false;
    {
        Mutexed<WorkQueue>::Locked queue(mWorkQueue);
        queueWasEmpty = queue->empty();
        while (!items->empty()) {
            queue->push_back(std::move(items->front()));
            items->pop_front();
        }
    }
    if (queueWasEmpty) {
        (new AMessage(WorkHandler::kWhatProcess, mHandler))->post();
    }
    return C2_OK;
}
```
`kWhatProcess`是异步消息, 此消息在如下位置处理:
```
// frameworks/av/media/codec2/components/base/SimpleC2Component.cpp +78
void SimpleC2Component::WorkHandler::onMessageReceived(const sp<AMessage> &msg) {
    std::shared_ptr<SimpleC2Component> thiz = mThiz.lock();
    ...
    switch (msg->what()) {
        case kWhatProcess: {
            if (mRunning) {
                if (thiz->processQueue()) {
                    (new AMessage(kWhatProcess, this))->post();
                }
            } else {
                ALOGV("Ignore process message as we're not running");
            }
            break;
        }
        ...

// frameworks/av/media/codec2/components/base/SimpleC2Component.cpp +440
bool SimpleC2Component::processQueue() {
    ...
    process(work, mOutputBlockPool);
    ...
```
如果`mOutputBlockPool`为空, 则创建, 然后进行处理:
```
// frameworks/av/media/codec2/components/vpx/C2SoftVpxDec.cpp +548
void C2SoftVpxDec::process(
        const std::unique_ptr<C2Work> &work,
        const std::shared_ptr<C2BlockPool> &pool) 
    ...
    if (inSize) {
        uint8_t *bitstream = const_cast<uint8_t *>(rView.data() + inOffset);
        vpx_codec_err_t err = vpx_codec_decode(
                mCodecCtx, bitstream, inSize, &work->input.ordinal.frameIndex, 0);
        if (err != VPX_CODEC_OK) {
            ALOGE("on2 decoder failed to decode frame. err: %d", err);
            mSignalledError = true;
            work->workletsProcessed = 1u;
            work->result = C2_CORRUPTED;
            return;
        }
    }
    ...
    status_t err = outputBuffer(pool, work);
    ...
}
```
`vpx_codec_decode()`完成解码工作, 前提是输入数据长度有效, 完成解码工作后, 输出结果
```
// frameworks/av/media/codec2/components/vpx/C2SoftVpxDec.cpp +752
status_t C2SoftVpxDec::outputBuffer(
        const std::shared_ptr<C2BlockPool> &pool,
        const std::unique_ptr<C2Work> &work)
{
    ...
    vpx_codec_iter_t iter = nullptr;
    vpx_image_t *img = vpx_codec_get_frame(mCodecCtx, &iter);
    ...
    C2MemoryUsage usage = { C2MemoryUsage::CPU_READ, C2MemoryUsage::CPU_WRITE };
    c2_status_t err = pool->fetchGraphicBlock(align(mWidth, 16), mHeight, format, usage, &block);
    ...
    C2GraphicView wView = block->map().get();
    ...
    // Copy datas...
}

// frameworks/av/media/codec2/components/base/SimpleC2Component.cpp +138
class SimpleC2Component::BlockingBlockPool : public C2BlockPool {
public:
    BlockingBlockPool(const std::shared_ptr<C2BlockPool>& base): mBase{base} {}
    ...
    virtual c2_status_t fetchGraphicBlock(
            uint32_t width, uint32_t height, uint32_t format,
            C2MemoryUsage usage,
            std::shared_ptr<C2GraphicBlock>* block) {
        c2_status_t status;
        do {
            status = mBase->fetchGraphicBlock(width, height, format, usage,
                                              block);
        } while (status == C2_BLOCKING);
        return status;
    }
private:
    std::shared_ptr<C2BlockPool> mBase;
};
```
`mBase`的类型是`C2BufferQueueBlockPool::Impl`, 因此:
```
// frameworks/av/media/codec2/vndk/platform/C2BqBuffer.cpp +235
class C2BufferQueueBlockPool::Impl
        : public std::enable_shared_from_this<C2BufferQueueBlockPool::Impl> {
    ...
    c2_status_t fetchGraphicBlock(
            uint32_t width,
            uint32_t height,
            uint32_t format,
            C2MemoryUsage usage,
            std::shared_ptr<C2GraphicBlock> *block /* nonnull */,
            C2Fence *fence) {
        ...
        c2_status_t status = fetchFromIgbp_l(width, height, format, usage, block, fence);
        if (status == C2_BLOCKING) {
            lock.unlock();
            if (!fence) {
                // in order not to drain cpu from component's spinning
                ::usleep(kMaxIgbpRetryDelayUs);
            }
        }
        return status;
    }
    ...
    c2_status_t fetchFromIgbp_l(
            uint32_t width,
            uint32_t height,
            uint32_t format,
            C2MemoryUsage usage,
            std::shared_ptr<C2GraphicBlock> *block /* nonnull */,
            C2Fence *c2Fence) {
        ...
        sp<GraphicBuffer> &slotBuffer = mBuffers[slot];
        uint32_t outGeneration;
        if (bufferNeedsReallocation || !slotBuffer) {
            if (!slotBuffer) {
                slotBuffer = new GraphicBuffer();
            }
            // N.B. This assumes requestBuffer# returns an existing allocation
            // instead of a new allocation.
            Return<void> transResult = mProducer->requestBuffer(
                    slot,
                    [&status, &slotBuffer, &outGeneration](
                            HStatus hStatus,
                            HBuffer const& hBuffer,
                            uint32_t generationNumber){
                        if (h2b(hStatus, &status) &&
                                h2b(hBuffer, &slotBuffer) &&
                                slotBuffer) {
                            slotBuffer->setGenerationNumber(generationNumber);
                            outGeneration = generationNumber;
                        } else {
                            status = android::BAD_VALUE;
                        }
                    });
            ...
        }
        ...
    }
    ...
}
```
`mProducer`的类型是:`BpHwGraphicBufferProducer`, 因此:
```
// out/soong/.intermediates/hardware/interfaces/graphics/bufferqueue/2.0/android.hardware.graphics.bufferqueue@2.0_genc++/gen/android/hardware/graphics/bufferqueue/2.0/GraphicBufferProducerAll.cpp +1589
::android::hardware::Return<void> BpHwGraphicBufferProducer::requestBuffer(int32_t slot, requestBuffer_cb _hidl_cb){
    ::android::hardware::Return<void>  _hidl_out = ::android::hardware::graphics::bufferqueue::V2_0::BpHwGraphicBufferProducer::_hidl_requestBuffer(this, this, slot, _hidl_cb);

    return _hidl_out;
}

// out/soong/.intermediates/hardware/interfaces/graphics/bufferqueue/2.0/android.hardware.graphics.bufferqueue@2.0_genc++/gen/android/hardware/graphics/bufferqueue/2.0/GraphicBufferProducerAll.cpp +305
::android::hardware::Return<void> BpHwGraphicBufferProducer::_hidl_requestBuffer(::android::hardware::IInterface *_hidl_this, ::android::hardware::details::HidlInstrumentor *_hidl_this_instrumentor, int32_t slot, requestBuffer_cb _hidl_cb) {
    ...
    _hidl_transact_err = ::android::hardware::IInterface::asBinder(_hidl_this)->transact(2 /* requestBuffer */, _hidl_data, &_hidl_reply, 0 /* flags */, [&] (::android::hardware::Parcel& _hidl_reply) {
        ...
        _hidl_cb(_hidl_out_status, *_hidl_out_buffer, _hidl_out_generationNumber);
        ...
    ...
```
`_hidle_cb()`这个上文`C2BufferQueueBlockPool::Impl::fetchFromIgbp_l()`中的`lambda`:`[&status, &slotBuffer, &outGeneration](...)`:
```
// frameworks/av/media/codec2/vndk/platform/C2BqBuffer.cpp +400
...
    ...
        ...
            ...
            // N.B. This assumes requestBuffer# returns an existing allocation
            // instead of a new allocation.
            Return<void> transResult = mProducer->requestBuffer(
                    slot,
                    [&status, &slotBuffer, &outGeneration](
                            HStatus hStatus,
                            HBuffer const& hBuffer,
                            uint32_t generationNumber){
                        if (h2b(hStatus, &status) &&
                                h2b(hBuffer, &slotBuffer) &&
                                slotBuffer) {
                            slotBuffer->setGenerationNumber(generationNumber);
                            outGeneration = generationNumber;
                        } else {
                            status = android::BAD_VALUE;
                        }
                    });
```
`h2b()`是非常重要的函数, 它负责处理从`Binder`获取到的`GraphicBuffer`信息:
```
// frameworks/av/media/codec2/vndk/types.cpp +287
// The handle is cloned.
bool h2b(HardwareBuffer const& from, sp<GraphicBuffer>* to) {
    AHardwareBuffer_Desc const* desc =
            reinterpret_cast<AHardwareBuffer_Desc const*>(
            from.description.data());
    native_handle_t const* handle = from.nativeHandle;
    AHardwareBuffer* hwBuffer;
    if (AHardwareBuffer_createFromHandle(
            desc, handle, AHARDWAREBUFFER_CREATE_FROM_HANDLE_METHOD_CLONE,
            &hwBuffer) != OK) {
        return false;
    }
    *to = GraphicBuffer::fromAHardwareBuffer(hwBuffer);
    AHardwareBuffer_release(hwBuffer);
    return true;
}
```

`AHardwareBuffer_createFromHandle()`负责从`native_handle_t`创建`AHardwareBuffer`:
```
// frameworks/native/libs/nativewindow/AHardwareBuffer.cpp +422
int AHardwareBuffer_createFromHandle(const AHardwareBuffer_Desc* desc,
                                     const native_handle_t* handle, int32_t method,
                                     AHardwareBuffer** outBuffer) {
    ...
    sp<GraphicBuffer> gbuffer(new GraphicBuffer(handle, wrapMethod, desc->width, desc->height,
                                                format, desc->layers, usage, desc->stride));
    status_t err = gbuffer->initCheck();
    if (err != 0 || gbuffer->handle == 0) return err;

    *outBuffer = AHardwareBuffer_from_GraphicBuffer(gbuffer.get());
    // Ensure the buffer doesn't get destroyed when the sp<> goes away.
    AHardwareBuffer_acquire(*outBuffer);

    return NO_ERROR;
}
```
此处的`new GraphicBuffer`是通过`native_handle_t`来创建, 因此:
```
// /frameworks/native/libs/ui/GraphicBuffer.cpp +101
GraphicBuffer::GraphicBuffer(const native_handle_t* inHandle, HandleWrapMethod method,
                             uint32_t inWidth, uint32_t inHeight, PixelFormat inFormat,
                             uint32_t inLayerCount, uint64_t inUsage, uint32_t inStride)
      : GraphicBuffer() {
    mInitCheck = initWithHandle(inHandle, method, inWidth, inHeight, inFormat, inLayerCount,
                                inUsage, inStride);
}

// /frameworks/native/libs/ui/GraphicBuffer.cpp +203
status_t GraphicBuffer::initWithHandle(const native_handle_t* inHandle, HandleWrapMethod method,
                                       uint32_t inWidth, uint32_t inHeight, PixelFormat inFormat,
                                       uint32_t inLayerCount, uint64_t inUsage, uint32_t inStride) {
    ...
    if (method == TAKE_UNREGISTERED_HANDLE || method == CLONE_HANDLE) {
        buffer_handle_t importedHandle;
        status_t err = mBufferMapper.importBuffer(inHandle, inWidth, inHeight, inLayerCount,
                                                  inFormat, inUsage, inStride, &importedHandle);
        ...

// frameworks/native/libs/ui/GraphicBufferMapper.cpp +85
status_t GraphicBufferMapper::importBuffer(buffer_handle_t rawHandle,
        uint32_t width, uint32_t height, uint32_t layerCount,
        PixelFormat format, uint64_t usage, uint32_t stride,
        buffer_handle_t* outHandle)
{
    ATRACE_CALL();

    buffer_handle_t bufferHandle;
    status_t error = mMapper->importBuffer(hardware::hidl_handle(rawHandle), &bufferHandle);
    ...
}

// frameworks/native/libs/ui/Gralloc2.cpp +155
status_t Gralloc2Mapper::importBuffer(const hardware::hidl_handle& rawHandle,
                                      buffer_handle_t* outBufferHandle) const {
    Error error;
    auto ret = mMapper->importBuffer(rawHandle,
            [&](const auto& tmpError, const auto& tmpBuffer)
            {
                error = tmpError;
                if (error != Error::NONE) {
                    return;
                }

                *outBufferHandle = static_cast<buffer_handle_t>(tmpBuffer);
            });

    return static_cast<status_t>((ret.isOk()) ? error : kTransactionError);
}
```

回到`types.cpp:h2b()`中:
```
// frameworks/av/media/codec2/vndk/types.cpp +287
// The handle is cloned.
bool h2b(HardwareBuffer const& from, sp<GraphicBuffer>* to) {
    ...
    if (AHardwareBuffer_createFromHandle(
            desc, handle, AHARDWAREBUFFER_CREATE_FROM_HANDLE_METHOD_CLONE,
            &hwBuffer) != OK) {
        return false;
    }
    *to = GraphicBuffer::fromAHardwareBuffer(hwBuffer);
    AHardwareBuffer_release(hwBuffer);
    return true;
}
```
`GraphicBuffer::fromAHardwareBuffer()`负责从`AHardwareBuffer`到`GraphicBuffer`的转换, 至此`GraphicBuffer`被成功导入.
回到上文`C2BufferQueueBlockPool::Impl::fetchFromIgbp_l()`中:
```
// frameworks/av/media/codec2/vndk/platform/C2BqBuffer.cpp +235
class C2BufferQueueBlockPool::Impl
        : public std::enable_shared_from_this<C2BufferQueueBlockPool::Impl> {
private:
    ...
    c2_status_t fetchFromIgbp_l(
            uint32_t width,
            uint32_t height,
            uint32_t format,
            C2MemoryUsage usage,
            std::shared_ptr<C2GraphicBlock> *block /* nonnull */,
            C2Fence *c2Fence) {
        ...
        if (slotBuffer) {
            ALOGV("buffer wraps %llu %d", (unsigned long long)mProducerId, slot);
            C2Handle *c2Handle = android::WrapNativeCodec2GrallocHandle(
                    slotBuffer->handle,
                    slotBuffer->width,
                    slotBuffer->height,
                    slotBuffer->format,
                    slotBuffer->usage,
                    slotBuffer->stride,
                    slotBuffer->getGenerationNumber(),
                    mProducerId, slot);
            if (c2Handle) {
                std::shared_ptr<C2GraphicAllocation> alloc;
                c2_status_t err = mAllocator->priorGraphicAllocation(c2Handle, &alloc);
                if (err != C2_OK) {
                    native_handle_close(c2Handle);
                    native_handle_delete(c2Handle);
                    return err;
                }
                std::shared_ptr<C2BufferQueueBlockPoolData> poolData =
                        std::make_shared<C2BufferQueueBlockPoolData>(
                                slotBuffer->getGenerationNumber(),
                                mProducerId, slot,
                                mProducer, mSyncMem, 0);
                mPoolDatas[slot] = poolData;
                *block = _C2BlockFactory::CreateGraphicBlock(alloc, poolData);
                return C2_OK;
            }
```
首先看`android::WrapNativeCodec2GrallocHandle()`, 它从`GraphicBuffer`的`handle`(类型为`native_handle_t`)创建了`C2Handle`, 那是什么`C2Handle`呢?
```
// frameworks/av/media/codec2/vndk/C2AllocatorGralloc.cpp +239
C2Handle *WrapNativeCodec2GrallocHandle(
        const native_handle_t *const handle,
        uint32_t width, uint32_t height, uint32_t format, uint64_t usage, uint32_t stride,
        uint32_t generation, uint64_t igbp_id, uint32_t igbp_slot) {
    return C2HandleGralloc::WrapNativeHandle(handle, width, height, format, usage, stride,
                                             generation, igbp_id, igbp_slot);
}

// frameworks/av/media/codec2/vndk/C2AllocatorGralloc.cpp +87
class C2HandleGralloc : public C2Handle {
...
public:
    ...
    static C2HandleGralloc* WrapNativeHandle(
            const native_handle_t *const handle,
            uint32_t width, uint32_t height, uint32_t format, uint64_t usage,
            uint32_t stride, uint32_t generation, uint64_t igbp_id = 0, uint32_t igbp_slot = 0) {
        if (handle == nullptr) {
            return nullptr;
        }
        native_handle_t *clone = native_handle_clone(handle);
        if (clone == nullptr) {
            return nullptr;
        }
        C2HandleGralloc *res = WrapAndMoveNativeHandle(
                clone, width, height, format, usage, stride, generation, igbp_id, igbp_slot);
        if (res == nullptr) {
            native_handle_close(clone);
        }
        native_handle_delete(clone);
        return res;
    }
    ...
    static C2HandleGralloc* WrapAndMoveNativeHandle(
            const native_handle_t *const handle,
            uint32_t width, uint32_t height, uint32_t format, uint64_t usage,
            uint32_t stride, uint32_t generation, uint64_t igbp_id = 0, uint32_t igbp_slot = 0) {
        //CHECK(handle != nullptr);
        if (native_handle_is_invalid(handle) ||
            handle->numInts > int((INT_MAX - handle->version) / sizeof(int)) - NUM_INTS - handle->numFds) {
            return nullptr;
        }
        ExtraData xd = {
            width, height, format, uint32_t(usage & 0xFFFFFFFF), uint32_t(usage >> 32),
            stride, generation, uint32_t(igbp_id & 0xFFFFFFFF), uint32_t(igbp_id >> 32),
            igbp_slot, MAGIC
        };
        native_handle_t *res = native_handle_create(handle->numFds, handle->numInts + NUM_INTS);
        if (res != nullptr) {
            memcpy(&res->data, &handle->data, sizeof(int) * (handle->numFds + handle->numInts));
            *GetExtraData(res) = xd;
        }
        return reinterpret_cast<C2HandleGralloc *>(res);
    }
```
首先复制了一份`native_handle_t`, 然后构造了`ExtraData`, 设置了一些值, 保存到`native_handle_t`的尾部.
回到上文`C2BufferQueueBlockPool::Impl::fetchFromIgbp_l()`中, 继续看:
```
// frameworks/av/media/codec2/vndk/platform/C2BqBuffer.cpp +235
class C2BufferQueueBlockPool::Impl
        : public std::enable_shared_from_this<C2BufferQueueBlockPool::Impl> {
private:
    ...
    c2_status_t fetchFromIgbp_l(
            uint32_t width,
            uint32_t height,
            uint32_t format,
            C2MemoryUsage usage,
            std::shared_ptr<C2GraphicBlock> *block /* nonnull */,
            C2Fence *c2Fence) {
        ...
        if (slotBuffer) {
            ALOGV("buffer wraps %llu %d", (unsigned long long)mProducerId, slot);
            C2Handle *c2Handle = android::WrapNativeCodec2GrallocHandle(
                    slotBuffer->handle,
                    slotBuffer->width,
                    slotBuffer->height,
                    slotBuffer->format,
                    slotBuffer->usage,
                    slotBuffer->stride,
                    slotBuffer->getGenerationNumber(),
                    mProducerId, slot);
            if (c2Handle) {
                std::shared_ptr<C2GraphicAllocation> alloc;
                c2_status_t err = mAllocator->priorGraphicAllocation(c2Handle, &alloc);
                if (err != C2_OK) {
                    native_handle_close(c2Handle);
                    native_handle_delete(c2Handle);
                    return err;
                }
                std::shared_ptr<C2BufferQueueBlockPoolData> poolData =
                        std::make_shared<C2BufferQueueBlockPoolData>(
                                slotBuffer->getGenerationNumber(),
                                mProducerId, slot,
                                mProducer, mSyncMem, 0);
                mPoolDatas[slot] = poolData;
                *block = _C2BlockFactory::CreateGraphicBlock(alloc, poolData);
                return C2_OK;
            }
```
`mAllocator->priorGraphicAllocation()`实际上是`C2AllocatorGralloc::Impl::priorGraphicAllocation()`:`
```
// frameworks/av/media/codec2/vndk/C2AllocatorGralloc.cpp +899

c2_status_t C2AllocatorGralloc::Impl::priorGraphicAllocation(
        const C2Handle *handle,
        std::shared_ptr<C2GraphicAllocation> *allocation) {
    ...
    allocation->reset(new C2AllocationGralloc(
            width, height, format, layerCount,
            grallocUsage, stride, hidlHandle, grallocHandle, mTraits->id));
    return C2_OK;
}

// frameworks/av/media/codec2/vndk/C2AllocatorGralloc.cpp +296
C2AllocationGralloc::C2AllocationGralloc(
          uint32_t width, uint32_t height,
          uint32_t format, uint32_t layerCount,
          uint64_t grallocUsage, uint32_t stride,
          hidl_handle &hidlHandle,
          const C2HandleGralloc *const handle,
          C2Allocator::id_t allocatorId)
    : C2GraphicAllocation(width, height),
      mWidth(width),
      mHeight(height),
      mFormat(format),
      mLayerCount(layerCount),
      mGrallocUsage(grallocUsage),
      mStride(stride),
      mHidlHandle(std::move(hidlHandle)),
      mHandle(handle),
      mBuffer(nullptr),
      mLockedHandle(nullptr),
      mLocked(false),
      mAllocatorId(allocatorId) {
}
```
回到上文`C2BufferQueueBlockPool::Impl::fetchFromIgbp_l()`中, `C2BufferQueueBlockPoolData`被创建, 主要保存`GraphicBuffer`的信息.
`_C2BlockFactory::CreateGraphicBlock()`则负责创建`C2GraphicBlock`, 上文的创建的`C2GraphicAllocation`(子类`C2AllocationGralloc`)和`C2BufferQueueBlockPoolData`(类型为`_C2BlockPoolData`)保存到`C2GraphicBlock`的父类`C2Block2D`的`mImpl`(类型为`C2Block2D::Impl`)中.

回到上文的:
```
// frameworks/av/media/codec2/components/vpx/C2SoftVpxDec.cpp +752
status_t C2SoftVpxDec::outputBuffer(
        const std::shared_ptr<C2BlockPool> &pool,
        const std::unique_ptr<C2Work> &work)
{
    ...
    std::shared_ptr<C2GraphicBlock> block;
    ...
    c2_status_t err = pool->fetchGraphicBlock(align(mWidth, 16), mHeight, format, usage, &block);
    ...
    C2GraphicView wView = block->map().get();
    ...
    // Copy datas...
}
```
为了向`GraphicBuffer`中写入软解后的数据, 必须对其进行映射, 因此执行`block->map().get()`, 先看`C2GraphicBlock::map()`:
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp +1073
C2Acquirable<C2GraphicView> C2GraphicBlock::map() {
    C2Fence fence;
    std::shared_ptr<_C2MappingBlock2DImpl::Mapped> mapping =
        mImpl->map(true /* writable */, &fence);
    std::shared_ptr<GraphicViewBuddy::Impl> gvi =
        std::shared_ptr<GraphicViewBuddy::Impl>(new GraphicViewBuddy::Impl(*mImpl, mapping));
    return AcquirableGraphicViewBuddy(
            mapping->error(), fence, GraphicViewBuddy(gvi, C2PlanarSection(*mImpl, crop())));
}
```
`mImpl`的类型是`C2Block2D::Impl`, 也就是`_C2MappingBlock2DImpl`因此:
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp +849
class C2_HIDE _C2MappingBlock2DImpl
    : public _C2Block2DImpl, public std::enable_shared_from_this<_C2MappingBlock2DImpl> {
public:
    ...
    /**
     * Maps the allotted region.
     *
     * If already mapped and it is currently in use, returns the existing mapping.
     * If fence is provided, an acquire fence is stored there.
     */
    std::shared_ptr<Mapped> map(bool writable, C2Fence *fence) {
        std::lock_guard<std::mutex> lock(mMappedLock);
        std::shared_ptr<Mapped> existing = mMapped.lock();
        if (!existing) {
            existing = std::shared_ptr<Mapped>(new Mapped(shared_from_this(), writable, fence));
            mMapped = existing;
        } else {
            // if we mapped the region read-only, we cannot remap it read-write
            if (writable && !existing->writable()) {
                existing = std::shared_ptr<Mapped>(new Mapped(C2_CANNOT_DO));
            }
            if (fence != nullptr) {
                *fence = C2Fence();
            }
        }
        return existing;
    }
```
`Mapped`在此时被构造:
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp +859
    struct Mapped {
    private:
        friend class _C2MappingBlock2DImpl;

        Mapped(const std::shared_ptr<_C2Block2DImpl> &impl, bool writable, C2Fence *fence __unused)
            : mImpl(impl), mWritable(writable) {
            memset(mData, 0, sizeof(mData));
            const C2Rect crop = mImpl->crop();
            // gralloc requires mapping the whole region of interest as we cannot
            // map multiple regions
            mError = mImpl->getAllocation()->map(
                    crop,
                    { C2MemoryUsage::CPU_READ, writable ? C2MemoryUsage::CPU_WRITE : 0 },
                    nullptr,
                    &mLayout,
                    mData);
            ...
        }
```
`mImpl->getAllocation()`返回的正式上文保存的`C2AllocationGralloc`, 因此:`
```
// frameworks/av/media/codec2/vndk/C2AllocatorGralloc.cpp +341
c2_status_t C2AllocationGralloc::map(
        C2Rect c2Rect, C2MemoryUsage usage, C2Fence *fence,
        C2PlanarLayout *layout /* nonnull */, uint8_t **addr /* nonnull */) {
    ...
    if (!mBuffer) {
        status_t err = GraphicBufferMapper::get().importBuffer(
                            mHidlHandle.getNativeHandle(), mWidth, mHeight, mLayerCount,
                            mFormat, mGrallocUsage, mStride, &mBuffer);
        ...
    ...

// frameworks/native/libs/ui/GraphicBufferMapper.cpp +85
status_t GraphicBufferMapper::importBuffer(buffer_handle_t rawHandle,
        uint32_t width, uint32_t height, uint32_t layerCount,
        PixelFormat format, uint64_t usage, uint32_t stride,
        buffer_handle_t* outHandle)
{
    ATRACE_CALL();

    buffer_handle_t bufferHandle;
    status_t error = mMapper->importBuffer(hardware::hidl_handle(rawHandle), &bufferHandle);
    ...
}
```
在此处再次对`GraphicBuffer`进行导入, 回到`C2AllocationGralloc::map()`中:
```
// frameworks/av/media/codec2/vndk/C2AllocatorGralloc.cpp +341
c2_status_t C2AllocationGralloc::map(
        C2Rect c2Rect, C2MemoryUsage usage, C2Fence *fence,
        C2PlanarLayout *layout /* nonnull */, uint8_t **addr /* nonnull */) {
    ...
    if (!mBuffer) {
        status_t err = GraphicBufferMapper::get().importBuffer(
                            mHidlHandle.getNativeHandle(), mWidth, mHeight, mLayerCount,
                            mFormat, mGrallocUsage, mStride, &mBuffer);
        ...
    }
    ...
    switch (mFormat) {
        ...
        case static_cast<uint32_t>(PixelFormat4::YV12): {
            android_ycbcr ycbcrLayout;
            status_t err = GraphicBufferMapper::get().lockYCbCr(
                    const_cast<native_handle_t*>(mBuffer), grallocUsage, rect, &ycbcrLayout);
```
一般通过相机录制的视频, 其像素格式都是`PixelFormat4::YV12`, 因此:
```
// frameworks/native/libs/ui/GraphicBufferMapper.cpp +133
status_t GraphicBufferMapper::lockYCbCr(buffer_handle_t handle, uint32_t usage,
        const Rect& bounds, android_ycbcr *ycbcr)
{
    return lockAsyncYCbCr(handle, usage, bounds, ycbcr, -1);
}

// frameworks/native/libs/ui/GraphicBufferMapper.cpp +169
status_t GraphicBufferMapper::lockAsyncYCbCr(buffer_handle_t handle,
        uint32_t usage, const Rect& bounds, android_ycbcr *ycbcr, int fenceFd)
{
    ATRACE_CALL();

    return mMapper->lock(handle, usage, bounds, fenceFd, ycbcr);
}

// frameworks/native/libs/ui/Gralloc2.cpp +275
status_t Gralloc2Mapper::lock(buffer_handle_t bufferHandle, uint64_t usage, const Rect& bounds,
            int acquireFence, android_ycbcr* ycbcr) const {
    ...
    auto ret = mMapper->lockYCbCr(buffer, usage, accessRegion,
            acquireFenceHandle,
            [&](const auto& tmpError, const auto& tmpLayout)
            {
                error = tmpError;
                if (error != Error::NONE) {
                    return;
                }

                layout = tmpLayout;
            });
```
`mMapper->lockYCbCr()`将获取`PixelFormat4::YV12`格式的`GraphicBuffer`中各数据分量的布局地址信息.
回到`Mapped`的构造函数:
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp +859
    struct Mapped {
    private:
        friend class _C2MappingBlock2DImpl;

        Mapped(const std::shared_ptr<_C2Block2DImpl> &impl, bool writable, C2Fence *fence __unused)
            : mImpl(impl), mWritable(writable) {
            ...
            mError = mImpl->getAllocation()->map(
                    crop,
                    { C2MemoryUsage::CPU_READ, writable ? C2MemoryUsage::CPU_WRITE : 0 },
                    nullptr,
                    &mLayout,
                    mData);
            if (mError != C2_OK) {
                ...
            } else {
                // TODO: validate plane layout and
                // adjust data pointers to the crop region's top left corner.
                // fail if it is not on a subsampling boundary
                for (size_t planeIx = 0; planeIx < mLayout.numPlanes; ++planeIx) {
                    // 这里将各数据分量的地址指针设置在 mOffsetData 中
                    mOffsetData[planeIx] =
                        mData[planeIx] + (ssize_t)crop.left * mLayout.planes[planeIx].colInc
                                + (ssize_t)crop.top * mLayout.planes[planeIx].rowInc;
                }
            }
        }
```
`mOffsetData`的值后面会通过`_C2MappingBlock2DImpl::Mapped::data()`
最后`C2GraphicBlock::map()`返回的是`C2Acquirable<C2GraphicView>`, 而`C2Acquirable<>`返回的又是`C2GraphicView`, `C2GraphicView::data()`:
```
// frameworks/av/media/codec2/vndk/C2Buffer.cpp +1021
const uint8_t *const *C2GraphicView::data() const {
    return mImpl->mapping()->data();
}
```
`mImpl->mapping()`是`_C2MappedBlock2DImpl::mapping()`, 返回的是其`Mapped`结构提, 因此`return mImpl->mapping()->data()`即是`_C2MappingBlock2DImpl::Mapped::data()`, 为上文保存的各数据分量的地址.

最后回到`C2SoftVpxDec::outputBuffer()`中, 函数在末尾通过`copyOutputBufferToYuvPlanarFrame()`完成解码后数据到`GraphicBuffer`的拷贝.

拷贝完成后调用`finishWork()`返回`GraphicBuffer`:
```
// frameworks/av/media/codec2/components/vpx/C2SoftVpxDec.cpp +510
void C2SoftVpxDec::finishWork(uint64_t index, const std::unique_ptr<C2Work> &work,
                           const std::shared_ptr<C2GraphicBlock> &block) {
    std::shared_ptr<C2Buffer> buffer = createGraphicBuffer(block,
                                                           C2Rect(mWidth, mHeight));
    auto fillWork = [buffer, index, intf = this->mIntf](
            const std::unique_ptr<C2Work> &work) {
        ...
    };
    if (work && c2_cntr64_t(index) == work->input.ordinal.frameIndex) {
        fillWork(work);
    } else {
        finish(index, fillWork);
    }
}
```
`createGraphicBuffer()`负责从填充过的包含`GraphicBuffer`的`C2GraphicBlock`包装为`C2Buffer`, 然后通过`fillWork`代码块将`C2Buffer`打包到`C2Work`中, 等待返回.