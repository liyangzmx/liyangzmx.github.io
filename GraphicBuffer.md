`GraphicBuffer`的生成是在第一次`IGraphicBufferProducer::dequeueBuffer()`时发生:
```
IGraphicBufferProducer::dequeueBuffer() -[Binder]->
  BnHwGraphicBufferProducer::_hidl_dequeueBuffer()
    B2HGraphicBufferProducer::dequeueBuffer()
      BufferQueueProducer::dequeueBuffer()
        GraphicBuffer::GraphicBuffer()
          GraphicBufferAllocator::get().allocate() -> GraphicBuffer::initWithSize()
            GraphicBufferAllocator::allocate()
              GraphicBufferAllocator::allocateHelper()
                mAllocator->allocate() -> Gralloc2Allocator::allocate()
```

假设解码器已经解码完成, 将返回`GraphicBuffer`, 此时创建的`GraphicBuffer`仅为描述:
```
HidlListener::onWorkDone()
  strongComponent->handleOnWorkDone(workItems) -> Codec2Client::Component::handleOnWorkDone()
    mOutputBufferQueue->holdBufferQueueBlocks(workItems) -> OutputBufferQueue::holdBufferQueueBlocks()
      forEachBlock(workList, std::bind(&OutputBufferQueue::registerBuffer, this, std::placeholders::_1))
        forEachBlock(worklet->output, process)
          process(block) ---> OutputBufferQueue::registerBuffer()
            mBuffers[oldSlot] = createGraphicBuffer(block) -> ::createGraphicBuffer()
              _UnwrapNativeCodec2GrallocMetadata()
                C2HandleGralloc::Import()
                  C2HandleGralloc::GetExtraData()
              UnwrapNativeCodec2GrallocHandle()
                C2HandleGralloc::UnwrapNativeHandle()
                  C2HandleGralloc::GetExtraData()
                  native_handle_create()
              new GraphicBuffer() -> GraphicBuffer::GraphicBuffer()
                GraphicBuffer::initWithHandle()
                  mBufferMapper.importBuffer() -> GraphicBufferMapper::importBuffer()
                    mMapper->importBuffer() -> Gralloc2Mapper::importBuffer()
                      mMapper->importBuffer() -> Gralloc2Mapper::importBuffer()
```
如流程所示`GraphicBuffer`创建完成后即刻导入到app中.

应用调用`MediaCodec.releaseOutputBuffer()`触发送显:
```
MediaCodec.releaseOutputBuffer()
  android_media_MediaCodec_releaseOutputBuffer()
    MediaCodec::renderOutputBufferAndRelease()
      [kWhatReleaseOutputBuffer] -> MediaCodec::onReleaseOutputBuffer()
        mBufferChannel->renderOutputBuffer() -> CCodecBufferChannel::renderOutputBuffer()
          mComponent->queueToOutputSurface() -> Component::queueToOutputSurface()
            mOutputBufferQueue->outputBuffer() -> OutputBufferQueue::outputBuffer()
              outputIgbp = mIgbp
              outputIgbp->queueBuffer() -> BufferQueueProducer::queueBuffer()
                frameAvailableListener = mCore->mConsumerListener
                frameAvailableListener->onFrameAvailable() -> BufferQueue::ProxyConsumerListener::onFrameAvailable()
                  mConsumerListener->onFrameAvailable() -> [SurfaceTexture]ConsumerBase::onFrameAvailable()
                    listener->onFrameAvailable() -> JNISurfaceTextureContext::onFrameAvailable()
                      env->CallStaticVoidMethod() -> SurfaceTexture.postEventFromNative()
                        TextureView.updateLayer()
                          mUpdateLayer = true;
```

应用界面在VSync到达后, 如果检测到有层需要更新(mUpdateLayer), 则通过压入一个`Drawable`到`RenderThread`的`WorkQueue`中:
```
TextureView.draw()
  TextureView.getTextureLayer()
    if (mLayer == null)
      mLayer = mAttachInfo.mThreadedRenderer.createTextureLayer()
        ThreadedRenderer.createTextureLayer()
          ThreadedRenderer.nCreateTextureLayer()
            android_view_ThreadedRenderer_createTextureLayer()
              proxy->createTextureLayer() -> RenderProxy::createTextureLayer()
                mContext->createTextureLayer() -> CanvasContext::createTextureLayer()
                  mRenderPipeline->createTextureLayer() -> SkiaOpenGLPipeline::createTextureLayer()
                    new DeferredLayerUpdater() -> DeferredLayerUpdater::DeferredLayerUpdater()
      mLayer.setSurfaceTexture(mSurface) -> TextureLayer.setSurfaceTexture()
        TextureLayer.nSetSurfaceTexture()
          TextureLayer_setSurfaceTexture() 
            layer->updateTexImage() -> DeferredLayerUpdater::setSurfaceTexture()
  TextureView.applyUpdate()
    if (mUpdateLayer)
      mUpdateLayer = false
    else
      return
    mLayer.prepare() -> TextureLayer.prepare()
    mLayer.updateSurfaceTexture() -> TextureLayer.updateSurfaceTexture()
      TextureLayer.nUpdateSurfaceTexture()
        TextureLayer_updateSurfaceTexture()
          layer->updateTexImage() -> DeferredLayerUpdater::updateTexImage()
            mUpdateTexImage = true
  recordingCanvas.drawTextureLayer() -> RecordingCanvas.drawTextureLayer()
    RecordingCanvas.nDrawTextureLayer()
      android_view_DisplayListCanvas_drawTextureLayer()
        canvas->drawLayer(layer) -> SkiaRecordingCanvas::drawLayer()
          sk_sp<SkDrawable> drawable(new LayerDrawable(layerUpdater))
            LayerDrawable::LayerDrawable()
              mLayerUpdater(layerUpdater)
          drawDrawable(drawable.get()) -> SkiaCanvas::drawDrawable()
            mCanvas->drawDrawable(drawable) -> SkCanvas::drawDrawable()
              this->onDrawDrawable() -> RecordingCanvas::onDrawDrawable()
                fDL->drawDrawable() -> DisplayListData::drawDrawable()
                  this->push<DrawDrawable>(0, drawable, matrix) -> DisplayListData::push()

紧接着`TextureView`通过`HardwareRenderer.syncAndDrawFrame()`触发一次渲染
HardwareRenderer.syncAndDrawFrame()
  HardwareRenderer.nsyncAndDrawFrame()
    android_view_ThreadedRenderer_syncAndDrawFrame()
      RenderProxy::syncAndDrawFrame()
        mDrawFrameTask.drawFrame() -> DrawFrameTask::postAndWait()
          mRenderThread->queue().post([this]() { run(); }) -> RenderThread::queue() -> ThreadBase::queue()
```

渲染线程首先通过`ASurfaceTexture_dequeueBuffer()`从`SurfaceTexture`提取相应的`GraphicBuffer`, 然后通过`mImageSlots[slot].createIfNeeded()`得到`SkImage`并保存到`Layer`, 然后通过`LayerDrawable::onDraw()`从`Layer`中提取保存的`SkImage`:
```
RenderThread::threadLoop()
  RenderThread::processQueue()
    mQueue.process() -> WorkQueue::process()
      DrawFrameTask::run()
        DrawFrameTask::syncFrameState()
          mLayers[i]->apply() -> DeferredLayerUpdater::apply()
            if (mUpdateTexImage) {
              ASurfaceTexture_dequeueBuffer(mSurfaceTexture, ...)
                st->consumer->dequeueBuffer() -> SurfaceTexture::dequeueBuffer()
                  mImageConsumer.dequeueBuffer() -> ImageConsumer::dequeueBuffer()
                    SurfaceTexture::acquireBufferLocked()
              sk_sp<SkImage> layerImage = mImageSlots[slot].createIfNeeded(hardwareBuffer, dataspace, newContent,mRenderState.getRenderThread().getGrContext());
              updateLayer(forceFilter, textureTransform, layerImage)
                mLayer->setImage() -> Layer::setImage()
                  this->layerImage = image
        CanvasContext* context = mContext
        context->draw() -> CanvasContext::draw()
          mRenderPipeline->draw() -> SkiaOpenGLPipeline::draw()
            SkiaPipeline::renderFrame()
              SkiaPipeline::renderFrameImpl()
                RenderNodeDrawable root(nodes[0].get(), canvas)
                root.draw(canvas) -> SkDrawable::draw()
                  this->onDraw() -> RenderNodeDrawable::onDraw()
                    this->forceDraw(canvas) -> RenderNodeDrawable::forceDraw()
                      RenderNodeDrawable::drawContent()
                        SkiaDisplayList* displayList = mRenderNode->getDisplayList().asSkiaDl()
                        displayList->draw(canvas) -> SkiaDisplayList::draw()
                          mDisplayList.draw(canvas) -> DisplayListData::draw()
                            this->map() -> DisplayListData::map()
                              fn(op, args...)
                                DrawDrawable::draw()
                                  SkDrawable::draw()
                                    this->onDraw() -> LayerDrawable::onDraw()
                                      Layer* layer = mLayerUpdater->backingLayer()
                                      LayerDrawable::DrawLayer()
                                        sk_sp<SkImage> layerImage = layer->getImage()
```