IComposerCallback::_hidl_onVsync() ->
    ComposerCallbackBridge::onVsync() ->
        SurfaceFlinger::onComposerHalVsync() ->
            Scheduler::addResyncSample() ->
                VSyncDispatch::timerCallback() ->
                    VSyncDispatchTimerQueue::timerCallback() ->
                        CallbackRepeater::callback() ->
                            VSyncSource::Callback::onVSyncEvent() ->
                                EventThread::makeVSync() --->
                                EventThread::dispatchEvent() ->
                                    EventThreadConnection::postEvent() ->
                                        DisplayEventReceiver::sendEvents() ->
                                            -------- [SOCKET] -------->
                                            Looper::pollOnce() ->
                                                Looper::pollInner() ->
                                                    epoll_wait()
                                                    DisplayEventDispatcher::handleEvent() ->
                                                        DisplayEventDispatcher::processPendingEvents() ->
                                                            NativeDisplayEventReceiver::dispatchVsync() ->
                                                                DisplayEventReceiver.dispatchVsync() ->
                                                                    FrameDisplayEventReceiver.onVsync() ->
                                                                        FrameHandler.handleMessage() ->
                                                                            Choreographer.doFrame() ->
                                                                                Choreographer.doCallbacks(Choreographer.CALLBACK_INPUT
                                                                                Choreographer.doCallbacks(... ...
                                                                                Choreographer.doCallbacks(Choreographer.CALLBACK_TRAVERSAL
                                                                                    TraversalRunnable.run() ->
                                                                                        -------- [TRAVERSAL] -------->
                                                                                        ViewRootImpl.doTraversal() ->
                                                                                            ViewRootImpl.performTraversals() ->
                                                                                                ViewRootImpl.performDraw() ->
                                                                                                    ViewRootImpl.draw() ->
                                                                                                        ThreadRender.draw() ->
                                                                                                            HardwareRenderer.syncAndDrawFrame() ->
                                                                                                                android_view_ThreadedRenderer_syncAndDrawFrame() ->
                                                                                                                    RenderProxy::syncAndDrawFrame() ->
                                                                                                                        DrawFrameTask::drawFrame() ->
                                                                                                                            DrawFrameTask::postAndWait() ->
                                                                                                                                -------- [RENDER_THREAD] -------->
                                                                                                                                DrawFrameTask::run() ->
                                                                                                                                    CanvasContext::draw() ->
                                                                                                                                        SkiaOpenGLPipeline::draw() ->
                                                                                                                                            SkSurface::
                                                                                                                                                SkSurface::flushAndSubmit() ->
                                                                                                                                                    SkSurface::flush() ->
                                                                                                                                                        SkSurface_Gpu::onFlush() ->
                                                                                                                                                            SkGpuDevice::flushAndSignalSemaphores() ->
                                                                                                                                                                GrDirectContextPriv::flushSurfaces() ->
                                                                                                                                                                    GrDrawingManager::flushSurfaces() ->
                                                                                                                                                                        GrDrawingManager::flush() ->
                                                                                                                                                                            GrRenderTask::execute() ->
                                                                                                                                                                                -------- [GrRenderTask] -------->
                                                                                                                                                                                GrOpsTask::onExecute() ->
                                                                                                                                                                                    OpChain::execute() ->
                                                                                                                                                                                        NonAALatticeOp::onExecute() ->
                                                                                                                                                                                            GrOpFlushState::bindTextures() ->
                                                                                                                                                                                                GrGLOpsRenderPass::bindTextures
                                                                                                                                                                                                    GrGLOpsRenderPass::onBindTextures() ->
                                                                                                                                                                                                        GrGLProgram::bindTextures() ->
                                                                                                                                                                                                            GrGLGpu::bindTexture() ->
                                                                                                                                                                                                                glBindTexture()
                                                                                                                                                                                        TextureOp::onExecute() ->
                                                                                                                                                                                            glDrawArrays()
                                                                                                                                        SkiaOpenGLPipeline::swapBuffers() ->
                                                                                                                                            EglManager::swapBuffers() ->
                                                                                                                                                libEGL.so::eglSwapBuffersWithDamageKHR()
                                                                                                                                                    libEGL.so::eglSwapBuffersWithDamageKHRImpl()
                                                                                                                                                        ...
                                                                                                                                                        Surface::hook_queueBuffer() ->
                                                                                                                                                            Surface::queueBuffer() ->
                                                                                                                                                                BufferQueueProducer::queueBuffer() -> 
                                                                                                                                                                    BLASTBufferQueue::onFrameAvailable() ->
                                                                                                                                                                        Transaction::apply() ->
                                                                                                                                                                            SurfaceFlinger::setTransactionState()
                                                                                Choreographer.doCallbacks(Choreographer.CALLBACK_COMMIT

IComposerCallback::_hidl_onRefresh() ->
    ComposerCallbackBridge::onRefresh()
        SurfaceFlinger::onComposerHalRefresh() ->
            SurfaceFlinger::repaintEverythingForHWC() ->
                MessageQueue::invalidate() --->
                    MessageQueue::vsyncCallback() ->
                        MessageQueue::Handler::dispatchInvalidate() ->
                            ---- [MessageQueue::INVALIDATE] ---->
                            SurfaceFlinger::onMessageInvalidate() ->
                                SurfaceFlinger::onMessageRefresh() ->
                                    CompositionEngine::present() ->
                                        Output::present() ->
                                            Display::present()
                                            Display::finsihFrame()
                                        Output::finishFrame() ->
                                            RenderSurface::queueBuffer() ->
                                                ...
                                            HWComposer::presentAndGetReleaseFences() ->
                                                Composer::presentDisplay() ->
                                                    IComposerClient::executeCommands() ->
                                                        ... 

