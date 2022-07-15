`bootanimation`的初始化
```
BootAnimation::BootAnimation()
    SurfaceComposerClient::onFirstRef()
        sp<ISurfaceComposerClient> mClient = sf->createConnection() ->
            BpSurfaceComposer::createConnection()
```

`bootanimation`主循环:
```
Thread::_threadLoop()
    BootAnimation::readyToRun()
        session()->createSurface(String8("BootAnimation") ->
            SurfaceComposerClient::createSurface()
                SurfaceComposerClient::createSurfaceChecked()
                    BpSurfaceComposerClient::createSurface()
        SurfaceComposerClient::Transaction::apply()
            BpSurfaceComposer::setTransactionState()
        sp<Surface> s = control->getSurface() ->
            SurfaceControl::getSurface()
                SurfaceControl::generateSurfaceLocked()
                    BLASTBufferQueue::BLASTBufferQueue()
                        BLASTBufferQueue::createBufferQueue()
                            sp<IGraphicBufferProducer> producer(new BBQBufferQueueProducer(core)) ->
                                BufferQueueProducer::BufferQueueProducer()
                        SurfaceComposerClient::Transaction()....apply()
                            BpSurfaceComposer::setTransactionState()
                    mSurfaceData = mBbq->getSurface(true) ->
                        BLASTBufferQueue::getSurface()
                            new BBQSurface(mProducer, true, scHandle, this)
                return mSurfaceData
    BootAnimation::android()
        libEGL.so::eglSwapBuffers()
            libEGL.so::eglSwapBuffersWithDamageKHRImpl()
                Surface::queueBuffer()
                    BufferQueueProducer::queueBuffer()
                        BufferQueue::ProxyConsumerListener::onFrameAvailable()
                            ConsumerBase::onFrameAvailable()
                                BLASTBufferQueue::processNextBufferLocked()
                                    SurfaceComposerClient::Transaction::apply()
                                        BpSurfaceComposer::setTransactionState()
```

`SurfaceFlinger`对显示层的创建
```
BnSurfaceComposerClient::onTransact()
    Client::createSurface()
        SurfaceFlinger::createLayer()
            SurfaceFlinger::createBufferStateLayer()
                surfaceflinger::DefaultFactory::createBufferStateLayer()
                    BufferStateLayer::BufferStateLayer()
                        BufferLayer::BufferLayer()
                            Layer::Layer()
```

`SurfaceFlinger`处理`BpSurfaceComposer::setTransactionState()`:
```
SurfaceFlinger::onTransact()
    BnSurfaceComposer::onTransact()
        layer_state_t::read()
            Parcel::read()
                Parcel::FlattenableHelper<GraphicBuffer>::unflatten()
                    GraphicBuffer::unflatten()
                        GraphicBufferMapper::importBuffer()
                            Gralloc2Mapper::importBuffer()

```

SurfaceFlinger合成导入层
```
SurfaceFlinger::onMessageInvalidate()
    SurfaceFlinger::handleMessageTransaction()
        SurfaceFlinger::flushTransactionQueues()
            for (const auto& transaction : transactions)
                SurfaceFlinger::applyTransactionState()
                    SurfaceFlinger::setClientStateLocked()
                        ClientCache::add()
                            renderengine::ExternalTexture::ExternalTexture()
                                mRenderEngine.mapExternalTextureBuffer(mBuffer, usage & Usage::WRITEABLE) ->
                                    renderengine::threaded::RenderEngineThreaded::mapExternalTextureBuffer()
                        [OR] buffer = ClientCache::getInstance().get(s.cachedBuffer) ->
                            BufferStateLayer::setBuffer()
    SurfaceFlinger::handleMessageInvalidate()
        SurfaceFlinger::handlePageFlip()
            mDrawingState.traverse([&](Layer* layer) {
                const uint32_t flags = layer->doTransaction(0)
                    BufferStateLayer::updateGeometry
                if (!mLayersWithQueuedFrames.empty())
                    for (const auto& layer : mLayersWithQueuedFrames)
                        layer->latchBuffer(visibleRegions, latchTime, expectedPresentTime) ->
                            BufferLayer::latchBuffer()
                                BufferStateLayer::updateActiveBuffer()
                        BufferStateLayer::updateTexImage()
            }
        
```