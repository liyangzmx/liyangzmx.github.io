- [App向SurfaceFlinger注册回调接口](#app向surfaceflinger注册回调接口)
- [Composer产生VSync信](#composer产生vsync信)
- [Vsync到SurfaceFlinger的传递](#vsync到surfaceflinger的传递)
- [SurfaceFlinger分发事件到应用](#surfaceflinger分发事件到应用)
- [Java层界面重绘](#java层界面重绘)
  - [DecorView重绘](#decorview重绘)
  - [ThreadedRenderer.updateRootDisplayList()](#threadedrendererupdaterootdisplaylist)
  - [DecorView子对象重绘](#decorview子对象重绘)
  - [ColorDrawable重绘子View背景](#colordrawable重绘子view背景)
- [Native层Canvas提交绘制请求](#native层canvas提交绘制请求)
  - [Java层ThreadedRenderer.syncAndDrawFrame()执行绘制操作](#java层threadedrenderersyncanddrawframe执行绘制操作)
  - [Native层Skia对SkiaPipeline::renderFrame()对界面执行渲染](#native层skia对skiapipelinerenderframe对界面执行渲染)
  - [SkSurface::flushAndSubmit()](#sksurfaceflushandsubmit)
- [应用swapBuffer()提交窗口至SurfaceFlinger](#应用swapbuffer提交窗口至surfaceflinger)
- [SurfaceFlinger合成窗口](#surfaceflinger合成窗口)
- [渲染引擎合成到Composer](#渲染引擎合成到composer)

## App向SurfaceFlinger注册回调接口
`DisplayEventReceiver`创建后, 其构造函数:
```
// frameworks/native/libs/gui/DisplayEventReceiver.cpp
DisplayEventReceiver::DisplayEventReceiver(
        ISurfaceComposer::VsyncSource vsyncSource,
        ISurfaceComposer::EventRegistrationFlags eventRegistration) {
    sp<ISurfaceComposer> sf(ComposerService::getComposerService());
    if (sf != nullptr) {
        mEventConnection = sf->createDisplayEventConnection(vsyncSource, eventRegistration);
        if (mEventConnection != nullptr) {
            mDataChannel = std::make_unique<gui::BitTube>();
            mEventConnection->stealReceiveChannel(mDataChannel.get());
        }
    }
}
```
通过Binder调用到`SurfaceFlinger::createDisplayEventConnection()`:
```
// frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp
sp<IDisplayEventConnection> SurfaceFlinger::createDisplayEventConnection(
        ISurfaceComposer::VsyncSource vsyncSource,
        ISurfaceComposer::EventRegistrationFlags eventRegistration) {
    ... ...
    return mScheduler->createDisplayEventConnection(handle, eventRegistration);
}
```
显然`mScheduler`是`Scheduler`, 进一步调用``
```
// frameworks/native/services/surfaceflinger/Scheduler/Scheduler.cpp
sp<IDisplayEventConnection> Scheduler::createDisplayEventConnection(
        ConnectionHandle handle, ISurfaceComposer::EventRegistrationFlags eventRegistration) {
    ... ...
    return createConnectionInternal(mConnections[handle].thread.get(), eventRegistration);
}
sp<EventThreadConnection> Scheduler::createConnectionInternal(
        EventThread* eventThread, ISurfaceComposer::EventRegistrationFlags eventRegistration) {
    return eventThread->createEventConnection([&] { resync(); }, eventRegistration);
}
```
显然, 继续调用`EventThread::createEventConnection()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/EventThread.cpp
sp<EventThreadConnection> EventThread::createEventConnection(
        ResyncCallback resyncCallback,
        ISurfaceComposer::EventRegistrationFlags eventRegistration) const {
    return new EventThreadConnection(const_cast<EventThread*>(this),
                                     IPCThreadState::self()->getCallingUid(),
                                     std::move(resyncCallback), eventRegistration);
}
```
`SurfaceFlinger`创建`EventThreadConnection`并作为`IDisplayEventConnection`返回给应用, 然后回到函数`DisplayEventReceiver::DisplayEventReceiver()`:
```
// frameworks/native/libs/gui/DisplayEventReceiver.cpp
DisplayEventReceiver::DisplayEventReceiver(
        ISurfaceComposer::VsyncSource vsyncSource,
        ISurfaceComposer::EventRegistrationFlags eventRegistration) {
    sp<ISurfaceComposer> sf(ComposerService::getComposerService());
    if (sf != nullptr) {
        mEventConnection = sf->createDisplayEventConnection(vsyncSource, eventRegistration);
        if (mEventConnection != nullptr) {
            mDataChannel = std::make_unique<gui::BitTube>();
            mEventConnection->stealReceiveChannel(mDataChannel.get());
        }
    }
}
```
应用拿到`IDisplayEventConnection`并再次通过Binder调用到`SurfaceFlinger`中的`EventThreadConnection::stealReceiveChannel()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/EventThread.cpp
status_t EventThreadConnection::stealReceiveChannel(gui::BitTube* outChannel) {
    outChannel->setReceiveFd(mChannel.moveReceiveFd());
    outChannel->setSendFd(base::unique_fd(dup(mChannel.getSendFd())));
    return NO_ERROR;
}
```
至此, 应用和`SurfaceFlinger`之间已经通过`BitTube`建立了连接, 也就是说后续`SurfaceFlinger`有事件, 应用都会通过`DisplayEventReceiver`来进行接收.

## Composer产生VSync信
## Vsync到SurfaceFlinger的传递
`ComposerCallbackBridge`由`SurfaceFlinger`创建并持有, 该类继承`IComposerCallback`接口, 先看一下该类的注册:
```
// frameworks/native/services/surfaceflinger/DisplayHardware/HWComposer.cpp
void HWComposer::setCallback(HWC2::ComposerCallback* callback) {
    ... ...
    mComposer->registerCallback(
            sp<ComposerCallbackBridge>::make(callback, mComposer->isVsyncPeriodSwitchSupported()));
}
```
`mComposer`的实现是`Composer`,所以:
```
// frameworks/native/services/surfaceflinger/DisplayHardware/ComposerHal.cpp
void Composer::registerCallback(const sp<IComposerCallback>& callback)
{
    android::hardware::setMinSchedulerPolicy(callback, SCHED_FIFO, 2);
    auto ret = [&]() {
        if (mClient_2_4) {
            return mClient_2_4->registerCallback_2_4(callback);
        }
        return mClient->registerCallback(callback);
    }();
    ... ...
}
```
那最后就是`IComposerClient::registerCallback_2_4()`了. 所以Composer负责通过`IComposerCallback`接口调用`ComposerCallbackBridge`通知`SurfaceFlinger`由VSYNC事件. 对应的`ComposerCallbackBridge::onVsync()`被调用:
```
// frameworks/native/services/surfaceflinger/DisplayHardware/HWComposer.cpp
Return<void> onVsync_2_4(hal::HWDisplayId display, int64_t timestamp,
                          hal::VsyncPeriodNanos vsyncPeriodNanos) override {
    if (mVsyncSwitchingSupported) {
        mCallback->onComposerHalVsync(display, timestamp, vsyncPeriodNanos);
    } else {
        ALOGW("Unexpected onVsync_2_4 callback on composer <= 2.3, ignoring.");
    }
    return Void();
}
```
这里的`mCallback`类型为`HW2::ComposerCallback`, 实际上是`SurfaceFlinger`, 因为`SurfaceFlinger`的定义:
```
// frameworks/native/services/surfaceflinger/SurfaceFlinger.h
class SurfaceFlinger : public BnSurfaceComposer,
                       public PriorityDumper,
                       private IBinder::DeathRecipient,
                       private HWC2::ComposerCallback,
                       private ISchedulerCallback {
public:
...
```
所以调用到`SurfaceFlinger::onComposerHalVsync()`:
```
// frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp
void SurfaceFlinger::onComposerHalVsync(hal::HWDisplayId hwcDisplayId, int64_t timestamp,
                                        std::optional<hal::VsyncPeriodNanos> vsyncPeriod) {
    ... ...
    mScheduler->addResyncSample(timestamp, vsyncPeriod, &periodFlushed);
    if (periodFlushed) {
        modulateVsync(&VsyncModulator::onRefreshRateChangeCompleted);
    }
}
```
`mScheduler`的类型是`Scheduler`, 所以调用`Scheduler::addResyncSample()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/Scheduler.cpp
void Scheduler::addResyncSample(nsecs_t timestamp, std::optional<nsecs_t> hwcVsyncPeriod,
                                bool* periodFlushed) {
    bool needsHwVsync = false;
    *periodFlushed = false;
    { // Scope for the lock
        std::lock_guard<std::mutex> lock(mHWVsyncLock);
        if (mPrimaryHWVsyncEnabled) {
            needsHwVsync = mVsyncSchedule.controller->addHwVsyncTimestamp(timestamp, hwcVsyncPeriod,
                                                                          periodFlushed);
        }
    }
    ... ...
}
```
`Scheduer`会通过`TimerKeeper`进一步调用到`VSyncDispatch::timerCallback()`, `VSyncDispatch`的实现是`VSyncDispatchTimerQueue`, 因此最终调用到`VSyncDispatchTimerQueue::timerCallback()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/VSyncDispatchTimerQueue.cpp
void VSyncDispatchTimerQueue::timerCallback() {
    ... ...
    for (auto const& invocation : invocations) {
        invocation.callback->callback(invocation.vsyncTimestamp, invocation.wakeupTimestamp,
                                      invocation.deadlineTimestamp);
    }
}
```
`invocation.callback`其实还是从`mCallbacks`中统计过来的, `mCallbacks`的类型是`CallbackRepeater`, 因此调用到`CallbackRepeater::callback`:
```
// frameworks/native/services/surfaceflinger/Scheduler/DispSyncSource.cpp
void callback(nsecs_t vsyncTime, nsecs_t wakeupTime, nsecs_t readyTime) {
    ... ...
    mCallback(vsyncTime, wakeupTime, readyTime);
    ... ..
}
```
`mCallback`为创建`DispSyncSource`时通过`std::bind()`设置的`std::function`, 其绑定的方法为`DispSyncSource::onVsyncCallback()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/DispSyncSource.cpp
void DispSyncSource::onVsyncCallback(nsecs_t vsyncTime, nsecs_t targetWakeupTime,
                                     nsecs_t readyTime) {
    ... ...
    if (callback != nullptr) {
        callback->onVSyncEvent(targetWakeupTime, vsyncTime, readyTime);
    }
}
```
`callback`就是`mCallback`类型为`VSyncSource::Callback`, 其实现是`EventThread`, 因此回调到`EventThread::onVsyncEvent()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/EventThread.cpp
    mCondition.notify_all();
}

void EventThread::onVSyncEvent(nsecs_t timestamp, nsecs_t expectedVSyncTimestamp,
                               nsecs_t deadlineTimestamp) {
    ... ...
    mPendingEvents.push_back(makeVSync(mVSyncState->displayId, timestamp, ++mVSyncState->count,
                                       expectedVSyncTimestamp, deadlineTimestamp, vsyncId));
    mCondition.notify_all();
}
```
`mPendingEvents`记录了通过`makeVSync`生成的`Event`事件, 该事件在通过`std::condition_variable`通知到`EventThread::threadMain()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/EventThread.cpp
void EventThread::threadMain(std::unique_lock<std::mutex>& lock) {
  ... ...
    ... ...
    if (!consumers.empty()) {
        dispatchEvent(*event, consumers);
        consumers.clear();
    }
    ... ...
  ... ...
}

void EventThread::dispatchEvent(const DisplayEventReceiver::Event& event,
                                const DisplayEventConsumers& consumers) {
    for (const auto& consumer : consumers) {
        ... ...
        switch (consumer->postEvent(copy)) {
            ... ...
        }
    }
}
```
`consumers`实际上是从`mDisplayEventConnections`成员中统计的事件接收方, 调用到`EventThreadConnection::postEvent()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/EventThread.cpp
status_t EventThreadConnection::postEvent(const DisplayEventReceiver::Event& event) {
    ... ...
    auto size = DisplayEventReceiver::sendEvents(&mChannel, &event, 1);
    return toStatus(size);
}

// frameworks/native/libs/gui/DisplayEventReceiver.cpp
ssize_t DisplayEventReceiver::sendEvents(gui::BitTube* dataChannel,
        Event const* events, size_t count)
{
    return gui::BitTube::sendObjects(dataChannel, events, count);
}
```
上文我们说过, 应用会通过`BitTube`接受来自`SurfaceFlinger`的通知, 揪下来再看应用一侧的处理.

## SurfaceFlinger分发事件到应用
应用对事件的监听是从`Looper`开始的:
```
// /system/core/libutils/Looper.cpp
int Looper::pollOnce(int timeoutMillis, int* outFd, int* outEvents, void** outData) {
    int result = 0;
    for (;;) {
        ... ...
        result = pollInner(timeoutMillis);
    }
}

int Looper::pollInner(int timeoutMillis) {
    ... ...
    // Invoke all response callbacks.
    for (size_t i = 0; i < mResponses.size(); i++) {
        Response& response = mResponses.editItemAt(i);
        if (response.request.ident == POLL_CALLBACK) {
            int fd = response.request.fd;
            ... ...
            int callbackResult = response.request.callback->handleEvent(fd, events, data);
            ... ...
        }
        ... ...
    }
    ... ...
}
```
此处的`callback`是`DisplayEventDispatcher`, 所以此时调用的是`DisplayEventDispatcher::handleEvent()`:
```
// frameworks/native/libs/gui/DisplayEventDispatcher.cpp
int DisplayEventDispatcher::handleEvent(int, int events, void*) {
    if (processPendingEvents(&vsyncTimestamp, &vsyncDisplayId, &vsyncCount, &vsyncEventData)) {
        ... ...
        dispatchVsync(vsyncTimestamp, vsyncDisplayId, vsyncCount, vsyncEventData);
    }

    return 1; // keep the callback
}
```
此时`DisplayEventDispatcher`其实是`NativeDisplayEventReceiver`的子类, 因此直接看`NativeDisplayEventReceiver`:
```
// frameworks/base/core/jni/android_view_DisplayEventReceiver.cpp

void NativeDisplayEventReceiver::dispatchVsync(nsecs_t timestamp, PhysicalDisplayId displayId,
                                               uint32_t count, VsyncEventData vsyncEventData) {
    JNIEnv* env = AndroidRuntime::getJNIEnv();

    ScopedLocalRef<jobject> receiverObj(env, jniGetReferent(env, mReceiverWeakGlobal));
    if (receiverObj.get()) {
        ALOGV("receiver %p ~ Invoking vsync handler.", this);
        env->CallVoidMethod(receiverObj.get(), gDisplayEventReceiverClassInfo.dispatchVsync,
                            timestamp, displayId.value, count, vsyncEventData.id,
                            vsyncEventData.deadlineTimestamp, vsyncEventData.frameInterval);
        ALOGV("receiver %p ~ Returned from vsync handler.", this);
    }

    mMessageQueue->raiseAndClearException(env, "dispatchVsync");
}
```

`CallVoidMethod()`通过JNI调用的是`DisplayEventReceiver.dispatchVsync()`:
```
// frameworks/base/core/java/android/view/DisplayEventReceiver.java
    // Called from native code.
    @SuppressWarnings("unused")
    private void dispatchVsync(long timestampNanos, long physicalDisplayId, int frame,
            long frameTimelineVsyncId, long frameDeadline, long frameInterval) {
        onVsync(timestampNanos, physicalDisplayId, frame,
                new VsyncEventData(frameTimelineVsyncId, frameDeadline, frameInterval));
    }
```

此时的`DisplayEventReceiver`其实是`FrameDisplayEventReceiver`, 所以调用的其实是`FrameDisplayEventReceiver.onVsync()`:
```
// frameworks/base/core/java/android/view/Choreographer.java
    private final class FrameDisplayEventReceiver extends DisplayEventReceiver implements Runnable {
        @Override
        public void onVsync(long timestampNanos, long physicalDisplayId, int frame,
                VsyncEventData vsyncEventData) {
            try {
                ... ...
                Message msg = Message.obtain(mHandler, this);
                msg.setAsynchronous(true);
                mHandler.sendMessageAtTime(msg, timestampNanos / TimeUtils.NANOS_PER_MS);
            } finally {
                Trace.traceEnd(Trace.TRACE_TAG_VIEW);
            }
        }
        ... ...
    ... ...
```
此处的`mHandler`类型是`FrameHandler`, 特别的`Message`的`what`未设置, 其值为`MSG_DO_FRAME`, 这是需要特别注意的, 因此其`FrameHandler.handleMessage()`会被调用:
```
// frameworks/base/core/java/android/view/Choreographer.java
    private final class FrameHandler extends Handler {
        public FrameHandler(Looper looper) {
            super(looper);
        }

        @Override
        public void handleMessage(Message msg) {
            switch (msg.what) {
                case MSG_DO_FRAME:
                    doFrame(System.nanoTime(), 0, new DisplayEventReceiver.VsyncEventData());
                    break;
                // 此场景下该位置的消息类型不是 MSG_DO_SCHEDULE_VSYNC
                case MSG_DO_SCHEDULE_VSYNC:
                    ... ...
                ... ...
            }
        }
    }

    void doFrame(long frameTimeNanos, int frame,
            DisplayEventReceiver.VsyncEventData vsyncEventData) {
        try {
            synchronized (mLock) {
                ... ...
                doCallbacks(Choreographer.CALLBACK_TRAVERSAL, frameTimeNanos, frameIntervalNanos);
                ... ...
            }
            ... ...
        }
        ... ...
    }

    void doCallbacks(int callbackType, long frameTimeNanos, long frameIntervalNanos) {
        CallbackRecord callbacks;
        synchronized (mLock) {
            callbacks = mCallbackQueues[callbackType].extractDueCallbacksLocked(
                    now / TimeUtils.NANOS_PER_MS);
            ... ...
        }
        try {
            Trace.traceBegin(Trace.TRACE_TAG_VIEW, CALLBACK_TRACE_TITLES[callbackType]);
            for (CallbackRecord c = callbacks; c != null; c = c.next) {
                ... ...
                c.run(frameTimeNanos);
            }
        } ... ...
    }
```

## Java层界面重绘
上文`mCallbackQueues`中存储的是应用中所有等待更新的层的回调, 类型是`TraversalRunnable`, 该类是在`ViewRootImpl.scheduleTraversals()`时通过`Choreographer.postCallback()`注册过来的, 其实现是:
```
// frameworks/base/core/java/android/view/ViewRootImpl.java
public final class ViewRootImpl implements ViewParent,
        View.AttachInfo.Callbacks, ThreadedRenderer.DrawCallbacks,
        AttachedSurfaceControl {
    ... ...
    final class TraversalRunnable implements Runnable {
        @Override
        public void run() {
            doTraversal();
        }
    }
    final TraversalRunnable mTraversalRunnable = new TraversalRunnable();

    void doTraversal() {
        if (mTraversalScheduled) {
            ... ...
            performTraversals();
            ... ...
        }
    }
    private void performTraversals() {
        ... ...
        if (!cancelDraw) {
            ... ...
            performDraw();
        }
        ... ...
    }
    private void performDraw() {
        ... ...
        try {
            boolean canUseAsync = draw(fullRedrawNeeded);
            ... ...
        }
        ... ...
    }
    private boolean draw(boolean fullRedrawNeeded) {
        Surface surface = mSurface;
        if (!dirty.isEmpty() || mIsAnimating || accessibilityFocusDirty || mNextDrawUseBlastSync) {
            if (isHardwareEnabled()) {
                mAttachInfo.mThreadedRenderer.draw(mView, mAttachInfo, this);
            }
            ... ...
        }
        ... ...
    }
    ... ...
}
```
`mAttachInfo.mThreadRender`的类型显然是`ThreadedRenderer`, 此时应用开始渲染界面.

### DecorView重绘
```
// frameworks/base/core/java/android/view/ThreadedRenderer.java
public final class ThreadedRenderer extends HardwareRenderer {
    void draw(View view, AttachInfo attachInfo, DrawCallbacks callbacks) {
        attachInfo.mViewRootImpl.mViewFrameInfo.markDrawStart();

        updateRootDisplayList(view, callbacks)
        ... ...
        int syncResult = syncAndDrawFrame(frameInfo);
        ... ...
    }
```
### ThreadedRenderer.updateRootDisplayList()
对于`updateRootDisplayList()`方法:
```
// frameworks/base/core/java/android/view/ThreadedRenderer.java
    private void updateRootDisplayList(View view, DrawCallbacks callbacks) {
        Trace.traceBegin(Trace.TRACE_TAG_VIEW, "Record View#draw()");
        updateViewTreeDisplayList(view);
        ... ...
    }

    private void updateViewTreeDisplayList(View view) {
        view.mPrivateFlags |= View.PFLAG_DRAWN;
        view.mRecreateDisplayList = (view.mPrivateFlags & View.PFLAG_INVALIDATED)
                == View.PFLAG_INVALIDATED;
        view.mPrivateFlags &= ~View.PFLAG_INVALIDATED;
        view.updateDisplayListIfDirty();
        view.mRecreateDisplayList = false;
    }
```
对于`view`, 在窗口中, 其实现是:`DecorView`, 但此处调用的还是`View.updateDisplayListIfDirty`:
```
// frameworks/base/core/java/android/view/View.java
    public RenderNode updateDisplayListIfDirty() {
        final RenderNode renderNode = mRenderNode;
        ... ...
        if ((mPrivateFlags & PFLAG_DRAWING_CACHE_VALID) == 0
                || !renderNode.hasDisplayList()
                || (mRecreateDisplayList)) {
            ... ...
            try {
                if (layerType == LAYER_TYPE_SOFTWARE) {
                    ... ...
                } else {
                    ... ...
                    if ((mPrivateFlags & PFLAG_SKIP_DRAW) == PFLAG_SKIP_DRAW) {
                        ... ...
                    } else {
                        draw(canvas);
                    }
                }
            }
```
此时调用父类的方法, 即`DecorView.draw()`:
```
// frameworks/base/core/java/com/android/internal/policy/DecorView.java
    @Override
    public void draw(Canvas canvas) {
        super.draw(canvas);

        if (mMenuBackground != null) {
            mMenuBackground.draw(canvas);
        }
    }
```
又调回父类的`View.draw()`方法, 对`DecorView`进行绘制:
```
// frameworks/base/core/java/android/view/View.java
    @CallSuper
    public void draw(Canvas canvas) {
        ... ...
        if (!verticalEdges && !horizontalEdges) {
            // Step 3, draw the content
            onDraw(canvas);

            // Step 4, draw the children
            dispatchDraw(canvas);
            ... ...
```

### DecorView子对象重绘
可以看到绘制`DecorView`时, 会绘制其子控, 这里先说下继承关系:`View` -> `ViewGroup` -> `FrameLayout` -> `DecorView`, 那么此处调用的其实是`ViewGroup.dispatchDraw()`
``件:
```
// frameworks/base/core/java/android/view/ViewGroup.java
    @Override
    protected void dispatchDraw(Canvas canvas) {
        final int childrenCount = mChildrenCount;
        final View[] children = mChildren;
        int flags = mGroupFlags;
        ... ...
        for (int i = 0; i < childrenCount; i++) {
            ... ...
            if ((child.mViewFlags & VISIBILITY_MASK) == VISIBLE || child.getAnimation() != null) {
                more |= drawChild(canvas, child, drawingTime);
            }
        }
        while (transientIndex >= 0) {
            ... ...
            if ((transientChild.mViewFlags & VISIBILITY_MASK) == VISIBLE ||
                    transientChild.getAnimation() != null) {
                more |= drawChild(canvas, transientChild, drawingTime);
            }
            ... ...
        }
        if (preorderedList != null) preorderedList.clear();

        // Draw any disappearing views that have animations
        if (mDisappearingChildren != null) {
            ... ...
            for (int i = disappearingCount; i >= 0; i--) {
                final View child = disappearingChildren.get(i);
                more |= drawChild(canvas, child, drawingTime);
            }
        }
        ... ...
    }

    protected boolean drawChild(Canvas canvas, View child, long drawingTime) {
        return child.draw(canvas, this, drawingTime);
    }
```
此处`ViewGroup.drawChild()`将调用第一个子View的: `View.draw()` -> `View.drawBackground()`方法绘制背景:
```
// frameworks/base/core/java/android/view/View.java
    @CallSuper
    public void draw(Canvas canvas) {
        final int privateFlags = mPrivateFlags;
        mPrivateFlags = (privateFlags & ~PFLAG_DIRTY_MASK) | PFLAG_DRAWN;
        int saveCount;
        drawBackground(canvas);
        ... ...
    }

    @UnsupportedAppUsage
    private void drawBackground(Canvas canvas) {
        ... ...
        if (canvas.isHardwareAccelerated() && mAttachInfo != null
                && mAttachInfo.mThreadedRenderer != null) {
            mBackgroundRenderNode = getDrawableRenderNode(background, mBackgroundRenderNode);
            ... ...
        }
        ... ...
    }
```
注意, 这里`View.draw()`中的`drawBackground()`方法, 应用是不能自己调用的, 继续查看`getDrawableRenderNode()`方法:
```
// frameworks/base/core/java/android/view/View.java
    private RenderNode getDrawableRenderNode(Drawable drawable, RenderNode renderNode) {
        ... ...
        try {
            drawable.draw(canvas);
        } finally {
            renderNode.endRecording();
        }
        ... ...
    }
```

### ColorDrawable重绘子View背景
此时`renderNode`的类型为:`ColorDrawable`, 因此调用`ColorDrawable.draw()`:
```
// frameworks/base/graphics/java/android/graphics/drawable/ColorDrawable.java
    @Override
    public void draw(Canvas canvas) {
        final ColorFilter colorFilter = mPaint.getColorFilter();
        if ((mColorState.mUseColor >>> 24) != 0 || colorFilter != null
                || mBlendModeColorFilter != null) {
            if (colorFilter == null) {
                mPaint.setColorFilter(mBlendModeColorFilter);
            }

            mPaint.setColor(mColorState.mUseColor);
            canvas.drawRect(getBounds(), mPaint);

            // Restore original color filter.
            mPaint.setColorFilter(colorFilter);
        }
    }
```
此时的`canvas`为类型`Canvas`因此查看`Canvas.drawRect()`的实现:
```
// frameworks/base/graphics/java/android/graphics/Canvas.java
public class Canvas extends BaseCanvas {
    ... ...
    public void drawRect(float left, float top, float right, float bottom, @NonNull Paint paint) {
        super.drawRect(left, top, right, bottom, paint);
    }
```
到父类:
```
// frameworks/base/graphics/java/android/graphics/BaseCanvas.java
public abstract class BaseCanvas {
    ... ...
    public void drawRect(float left, float top, float right, float bottom, @NonNull Paint paint) {
        throwIfHasHwBitmapInSwMode(paint);
        nDrawRect(mNativeCanvasWrapper, left, top, right, bottom, paint.getNativeInstance());
    }
```

## Native层Canvas提交绘制请求
`nDrawRect`在Native层的实现 是`CanvasJNI::drawRect`:
```
// frameworks/base/libs/hwui/jni/android_graphics_Canvas.cpp
static void drawRect(JNIEnv* env, jobject, jlong canvasHandle, jfloat left, jfloat top,
                     jfloat right, jfloat bottom, jlong paintHandle) {
    const Paint* paint = reinterpret_cast<Paint*>(paintHandle);
    get_canvas(canvasHandle)->drawRect(left, top, right, bottom, *paint);
}
```
`get_canvas()`返回的其实是`SkiaCanvas`类型, 因此继续调用`SkiaCanvas::drawRect()`:
```
// frameworks/base/libs/hwui/SkiaCanvas.cpp
void SkiaCanvas::drawRect(float left, float top, float right, float bottom, const Paint& paint) {
    if (CC_UNLIKELY(paint.nothingToDraw())) return;
    applyLooper(&paint, [&](const SkPaint& p) {
        mCanvas->drawRect({left, top, right, bottom}, p);
    });
}

// frameworks/base/libs/hwui/SkiaCanvas.h
    template <typename Proc>
    void applyLooper(const Paint* paint, Proc proc, void (*preFilter)(SkPaint&) = nullptr) {
        ... ...
        this->onFilterPaint(skp);
        if (looper) {
            ... ...
        } else {
            proc(skp);
        }
    }
```
直接调用`mCanvas->drawRect()`, 注意, 此处虽然`mCanvas`的类型是`SkCanvas`, 但其还有子类`RecordingCanvas`因此此处调用的是`RecordingCanvas::drawRect()`:
```
// frameworks/base/libs/hwui/RecordingCanvas.cpp
void RecordingCanvas::onDrawRect(const SkRect& rect, const SkPaint& paint) {
    fDL->drawRect(rect, paint);
}
```
`fDL`的类型是`DisplayListData`, 因此此处调用:`DisplayListData::drawRect()`:
```
// frameworks/base/libs/hwui/RecordingCanvas.cpp
void DisplayListData::drawRect(const SkRect& rect, const SkPaint& paint) {
    this->push<DrawRect>(0, rect, paint);
}

template <typename T, typename... Args>
void* DisplayListData::push(size_t pod, Args&&... args) {
    size_t skip = SkAlignPtr(sizeof(T) + pod);
    SkASSERT(skip < (1 << 24));
    if (fUsed + skip > fReserved) {
        static_assert(SkIsPow2(SKLITEDL_PAGE), "This math needs updating for non-pow2.");
        // Next greater multiple of SKLITEDL_PAGE.
        fReserved = (fUsed + skip + SKLITEDL_PAGE) & ~(SKLITEDL_PAGE - 1);
        fBytes.realloc(fReserved);
        LOG_ALWAYS_FATAL_IF(fBytes.get() == nullptr, "realloc(%zd) failed", fReserved);
    }
    SkASSERT(fUsed + skip <= fReserved);
    auto op = (T*)(fBytes.get() + fUsed);
    fUsed += skip;
    new (op) T{std::forward<Args>(args)...};
    op->type = (uint32_t)T::kType;
    op->skip = skip;
    return op + 1;
}
```
此处的`this->push<DrawRect>()`直接插入了一条回调到`fBytes`中, 这些记录将在`DisplayListData::map()`执行时被调用.

### Java层ThreadedRenderer.syncAndDrawFrame()执行绘制操作
继续调用基类`HardwareRenderer`的`syncAndDrawFrame`方法:
```
// frameworks/base/graphics/java/android/graphics/HardwareRenderer.java
public class HardwareRenderer {
    @SyncAndDrawResult
    public int syncAndDrawFrame(@NonNull FrameInfo frameInfo) {
        return nSyncAndDrawFrame(mNativeProxy, frameInfo.frameInfo, frameInfo.frameInfo.length);
    }
    ... ...
}
```
`nSyncAndDrawFrame()`是个native方法:
```
// frameworks/base/libs/hwui/jni/android_graphics_HardwareRenderer.cpp
static int android_view_ThreadedRenderer_syncAndDrawFrame(JNIEnv* env, jobject clazz,
        jlong proxyPtr, jlongArray frameInfo, jint frameInfoSize) {
    ... ...
    RenderProxy* proxy = reinterpret_cast<RenderProxy*>(proxyPtr);
    env->GetLongArrayRegion(frameInfo, 0, frameInfoSize, proxy->frameInfo());
    return proxy->syncAndDrawFrame();
}
// frameworks/base/libs/hwui/renderthread/RenderProxy.cpp
int RenderProxy::syncAndDrawFrame() {
    return mDrawFrameTask.drawFrame();
}
// frameworks/base/libs/hwui/renderthread/DrawFrameTask.cpp

int DrawFrameTask::drawFrame() {
    ... ...
    postAndWait();
    return mSyncResult;
}
void DrawFrameTask::postAndWait() {
    AutoMutex _lock(mLock);
    mRenderThread->queue().post([this]() { run(); });
    mSignal.wait(mLock);
}
```
`DrawFrameTask::postAndWait()`负责提交绘图请求, 并触发`RenderThread`执行渲染, 因此`DrawFrameTask::run()`会调度到:
```
// frameworks/base/libs/hwui/renderthread/DrawFrameTask.cpp
void DrawFrameTask::run() {
    ... ...
    if (CC_LIKELY(canDrawThisFrame)) {
        dequeueBufferDuration = context->draw();
    }
    ... ...
}
```
`context`的类型是`CanvasContext`, 因此调用`CanvasContext::draw()`:
```
// frameworks/base/libs/hwui/renderthread/CanvasContext.cpp
nsecs_t CanvasContext::draw() {
    ... ...
    Frame frame = mRenderPipeline->getFrame();
    SkRect windowDirty = computeDirtyRect(frame, &dirty);

    bool drew = mRenderPipeline->draw(frame, windowDirty, dirty, mLightGeometry, &mLayerUpdateQueue,
                                      mContentDrawBounds, mOpaque, mLightInfo, mRenderNodes,
                                      &(profiler()));
    ... ...
    bool didSwap =
            mRenderPipeline->swapBuffers(frame, drew, windowDirty, mCurrentFrameInfo, &requireSwap);
    ... ...
}
```
`mRenderPipeline`的类型是`SkiaOpenGLPipeline`, 注意它的基类是`SkiaPipeline`, 先看`SkiaOpenGLPipeline::draw()`;

在`SkiaOpenGLPipeline::draw()`时:
```
// frameworks/base/libs/hwui/pipeline/skia/SkiaOpenGLPipeline.cpp
bool SkiaOpenGLPipeline::draw(const Frame& frame, const SkRect& screenDirty, const SkRect& dirty,
                              const LightGeometry& lightGeometry,
                              LayerUpdateQueue* layerUpdateQueue, const Rect& contentDrawBounds,
                              bool opaque, const LightInfo& lightInfo,
                              const std::vector<sp<RenderNode>>& renderNodes,
                              FrameInfoVisualizer* profiler) {
    ... ...
    renderFrame(*layerUpdateQueue, dirty, renderNodes, opaque, contentDrawBounds, surface,
                SkMatrix::I());
    ... ...
    {
        ATRACE_NAME("flush commands");
        surface->flushAndSubmit();
    }
    ... ...
}
```

### Native层Skia对SkiaPipeline::renderFrame()对界面执行渲染
在`SkiaPipeline::renderFrame()`中:
这里的`renderFrame()`, 其属于父类, 因此::
```
// frameworks/base/libs/hwui/pipeline/skia/SkiaPipeline.cpp
void SkiaPipeline::renderFrame(const LayerUpdateQueue& layers, const SkRect& clip,
                               const std::vector<sp<RenderNode>>& nodes, bool opaque,
                               const Rect& contentDrawBounds, sk_sp<SkSurface> surface,
                               const SkMatrix& preTransform) {
    ... ...
    renderFrameImpl(clip, nodes, opaque, contentDrawBounds, canvas, preTransform);

void SkiaPipeline::renderFrameImpl(const SkRect& clip,
                                   const std::vector<sp<RenderNode>>& nodes, bool opaque,
                                   const Rect& contentDrawBounds, SkCanvas* canvas,
                                   const SkMatrix& preTransform) {
    ... ...
    if (1 == nodes.size()) {
        if (!nodes[0]->nothingToDraw()) {
            RenderNodeDrawable root(nodes[0].get(), canvas);
            root.draw(canvas);
        }
    } else if (0 == nodes.size()) {
        // nothing to draw
    } else {
        ... ...
        RenderNodeDrawable contentNode(nodes[1].get(), canvas);
        if (!backdrop.isEmpty()) {
            ... ...
            contentNode.draw(canvas);
        } else {
            SkAutoCanvasRestore acr(canvas, true);
            contentNode.draw(canvas);
        }
        ... ...
```
这里分两种情况, 就是`nodes.size()`为`1`或者为`其它`(`0`不做任何操作), 我们先关注`contentNode.draw(canvas)`, 其中 `contentNode`是`RenderNodeDrawable`, 其`draw()`方法是父类的, 调用是会调回`RenderNodeDrawable::onDraw()`:
```
// frameworks/base/libs/hwui/pipeline/skia/RenderNodeDrawable.cpp
void RenderNodeDrawable::onDraw(SkCanvas* canvas) {
    ... ...
    if ((!mInReorderingSection) || MathUtils::isZero(mRenderNode->properties().getZ())) {
        this->forceDraw(canvas);
    }
}

void RenderNodeDrawable::forceDraw(SkCanvas* canvas) const {
    RenderNode* renderNode = mRenderNode.get();
    ... ...
    if (!properties.getProjectBackwards()) {
        drawContent(canvas);
        ... ...

void RenderNodeDrawable::drawContent(SkCanvas* canvas) const {
    RenderNode* renderNode = mRenderNode.get();
    ... ...
    if (!quickRejected) {
        SkiaDisplayList* displayList = renderNode->getDisplayList().asSkiaDl();
        const LayerProperties& layerProperties = properties.layerProperties();
        // composing a hardware layer
        if (renderNode->getLayerSurface() && mComposeLayer) {
            ...
        } else {
            if (alphaMultiplier < 1.0f) {
                // Non-layer draw for a view with getHasOverlappingRendering=false, will apply
                // the alpha to the paint of each nested draw.
                AlphaFilterCanvas alphaCanvas(canvas, alphaMultiplier);
                displayList->draw(&alphaCanvas);
            } else {
                displayList->draw(canvas);
            }
        }
    }
```
关注`displayList->draw(canvas)`的调用, 对应的是`SkiaDisplayList::draw()`:
```
// frameworks/base/libs/hwui/pipeline/skia/SkiaDisplayList.h
class SkiaDisplayList {
public:
    void draw(SkCanvas* canvas) { mDisplayList.draw(canvas); }
```
`mDisplayList`的类型为`DisplayListData`, 因此调用`DisplayListData::draw()`:
```
// frameworks/base/libs/hwui/RecordingCanvas.cpp
void DisplayListData::draw(SkCanvas* canvas) const {
    SkAutoCanvasRestore acr(canvas, false);
    this->map(draw_fns, canvas, canvas->getTotalMatrix());
}

template <typename Fn, typename... Args>
inline void DisplayListData::map(const Fn fns[], Args... args) const {
    auto end = fBytes.get() + fUsed;
    for (const uint8_t* ptr = fBytes.get(); ptr < end;) {
        auto op = (const Op*)ptr;
        auto type = op->type;
        auto skip = op->skip;
        if (auto fn = fns[type]) {  // We replace no-op functions with nullptrs
            fn(op, args...);        // to avoid the overhead of a pointless call.
        }
        ptr += skip;
    }
}
```
查看`draw_fns`的定义:
```
// All ops implement draw().
#define X(T)                                                    \
    [](const void* op, SkCanvas* c, const SkMatrix& original) { \
        ((const T*)op)->draw(c, original);                      \
    },
static const draw_fn draw_fns[] = {
#include "DisplayListOps.in"
};
#undef X
```
而在`DisplayListOps.in`中:
```
X(Flush)
X(Save)
X(Restore)
X(SaveLayer)
X(SaveBehind)
X(Concat)
X(SetMatrix)
X(Scale)
X(Translate)
X(ClipPath)
X(ClipRect)
X(ClipRRect)
X(ClipRegion)
X(DrawPaint)
X(DrawBehind)
X(DrawPath)
X(DrawRect)
X(DrawRegion)
X(DrawOval)
X(DrawArc)
X(DrawRRect)
X(DrawDRRect)
X(DrawAnnotation)
X(DrawDrawable)
X(DrawPicture)
X(DrawImage)
X(DrawImageRect)
X(DrawImageLattice)
X(DrawTextBlob)
X(DrawPatch)
X(DrawPoints)
X(DrawVertices)
X(DrawAtlas)
X(DrawShadowRec)
X(DrawVectorDrawable)
X(DrawRippleDrawable)
X(DrawWebView)
```
回顾上文的`DisplayListData::drawRect()`:
// frameworks/base/libs/hwui/RecordingCanvas.cpp
void DisplayListData::drawRect(const SkRect& rect, const SkPaint& paint) {
    this->push<DrawRect>(0, rect, paint);
}
可以看到, 这里采用的是`X(DrawRect)`, 因此, 调用的方法为:`DrawRect::draw()`:
```
// frameworks/base/libs/hwui/RecordingCanvas.cpp
struct DrawRect final : Op {
    ... ...
    void draw(SkCanvas* c, const SkMatrix&) const { c->drawRect(rect, paint); }
};
```
调用到上文的`SkCanvas::drawRect()`:
```
// external/skia/src/core/SkCanvas.cpp
void SkCanvas::drawRect(const SkRect& r, const SkPaint& paint) {
    TRACE_EVENT0("skia", TRACE_FUNC);
    // To avoid redundant logic in our culling code and various backends, we always sort rects
    // before passing them along.
    this->onDrawRect(r.makeSorted(), paint);
}

void SkCanvas::onDrawRect(const SkRect& r, const SkPaint& paint) {
    ... ...
    this->topDevice()->drawRect(r, layer.paint());
}
```
`this->topDevice()`得到的是`SkGpuDevice`, 因此此时调用的是`SkGpuDevice::drawRect()`:
```
// external/skia/src/gpu/SkGpuDevice.cpp
void SkGpuDevice::drawRect(const SkRect& rect, const SkPaint& paint) {
    ... ...
    fSurfaceDrawContext->drawRect(this->clip(), std::move(grPaint),
                                  fSurfaceDrawContext->chooseAA(paint), this->localToDevice(), rect,
                                  &style);
}
```
`fSurfaceDrawContext`的类型是`GrSurfaceDrawContext`, 故`GrSurfaceDrawContext::drawRect()`
```
void GrSurfaceDrawContext::drawRect(const GrClip* clip,
                                    GrPaint&& paint,
                                    GrAA aa,
                                    const SkMatrix& viewMatrix,
                                    const SkRect& rect,
                                    const GrStyle* style) {
    ... ...
    const SkStrokeRec& stroke = style->strokeRec();
    if (stroke.getStyle() == SkStrokeRec::kFill_Style) {
        ... ...
    } else if ((stroke.getStyle() == SkStrokeRec::kStroke_Style ||
                stroke.getStyle() == SkStrokeRec::kHairline_Style) &&
               (rect.width() && rect.height())) {
        ... ...
        GrOp::Owner op = GrStrokeRectOp::Make(
                fContext, std::move(paint), aaType, viewMatrix, rect, stroke);
        if (op) {
            this->addDrawOp(clip, std::move(op));
            return;
        }
    }
    ... ...
}

void GrSurfaceDrawContext::addDrawOp(const GrClip* clip,
                                     GrOp::Owner op,
                                     const std::function<WillAddOpFn>& willAddFn) {
    ... ...
    auto opsTask = this->getOpsTask();
    opsTask->addDrawOp(this->drawingManager(), std::move(op), fixedFunctionFlags, analysis,
                       std::move(appliedClip), dstProxyView,
                       GrTextureResolveManager(this->drawingManager()), *this->caps());
}
```
`this->getOpsTask()`得到的就是`GrOpsTask`, 因此:
```
// external/skia/src/gpu/GrOpsTask.cpp
void GrOpsTask::addDrawOp(GrDrawingManager* drawingMgr, GrOp::Owner op,
                          GrDrawOp::FixedFunctionFlags fixedFunctionFlags,
                          const GrProcessorSet::Analysis& processorAnalysis, GrAppliedClip&& clip,
                          const DstProxyView& dstProxyView,
                          GrTextureResolveManager textureResolveManager, const GrCaps& caps) {
    ... ...
    this->recordOp(std::move(op), processorAnalysis, clip.doesClip() ? &clip : nullptr,
                   &dstProxyView, caps);
}

void GrOpsTask::recordOp(
        GrOp::Owner op, GrProcessorSet::Analysis processorAnalysis, GrAppliedClip* clip,
        const DstProxyView* dstProxyView, const GrCaps& caps) {
    ... ...
    fOpChains.emplace_back(std::move(op), processorAnalysis, clip, dstProxyView);
}
```
`fOpChains`记录了所有应该绘制的操作, 这些操作会在`GrOpsTask::execute()`时执行, 相应的操作流程将在本文后续内容介绍.

### SkSurface::flushAndSubmit()
在函数末尾的`surface->flushAndSubmit()`:
`surface`的类型时`SkSurface`, 故此处调用`SkSurface::flushAndSubmit()`:
```
// external/skia/src/image/SkSurface.cpp
void SkSurface::flushAndSubmit(bool syncCpu) {
    this->flush(BackendSurfaceAccess::kNoAccess, GrFlushInfo());
}

GrSemaphoresSubmitted SkSurface::flush(BackendSurfaceAccess access, const GrFlushInfo& flushInfo) {
    return asSB(this)->onFlush(access, flushInfo, nullptr);
}
```
其实此处`SkSurface`由`SkSurface_Gpu`继承, 因此调用`SkSurface_Gpu::onDraw()`:
```
// external/skqp/src/image/SkSurface_Gpu.cpp
GrSemaphoresSubmitted SkSurface_Gpu::onFlush(BackendSurfaceAccess access, const GrFlushInfo& info,
                                             const GrBackendSurfaceMutableState* newState) {

    auto dContext = fDevice->recordingContext()->asDirectContext();
    ... ...
    GrSurfaceDrawContext* sdc = fDevice->surfaceDrawContext();
    return dContext->priv().flushSurface(sdc->asSurfaceProxy(), access, info, newState);
}
```
`dContext`的类型时`GrDirectContext`, `dContext->priv()`返回的是`GrDirectContextPriv`, 因此:
```
// external/skia/src/gpu/GrDirectContextPriv.h
class GrDirectContextPriv {
    GrSemaphoresSubmitted flushSurface(
                GrSurfaceProxy* proxy,
                SkSurface::BackendSurfaceAccess access = SkSurface::BackendSurfaceAccess::kNoAccess,
                const GrFlushInfo& info = {},
                const GrBackendSurfaceMutableState* newState = nullptr) {
        size_t size = proxy ? 1 : 0;
        return this->flushSurfaces({&proxy, size}, access, info, newState);
    }
```
实现在:
```
// external/skia/src/gpu/GrDirectContextPriv.cpp
GrSemaphoresSubmitted GrDirectContextPriv::flushSurfaces(
                                                    SkSpan<GrSurfaceProxy*> proxies,
                                                    SkSurface::BackendSurfaceAccess access,
                                                    const GrFlushInfo& info,
                                                    const GrBackendSurfaceMutableState* newState) {
    ... ...
    return fContext->drawingManager()->flushSurfaces(proxies, access, info, newState);
}
```
`fContext->drawingManager()`返回`GrDrawingManager`, 所以调用:
```
// external/skia/src/gpu/GrDrawingManager.cpp

GrSemaphoresSubmitted GrDrawingManager::flushSurfaces(
        SkSpan<GrSurfaceProxy*> proxies,
        SkSurface::BackendSurfaceAccess access,
        const GrFlushInfo& info,
        const GrBackendSurfaceMutableState* newState) {
    ... ...
    bool didFlush = this->flush(proxies, access, info, newState);
    ... ...
}

bool GrDrawingManager::flush(
        SkSpan<GrSurfaceProxy*> proxies,
        SkSurface::BackendSurfaceAccess access,
        const GrFlushInfo& info,
        const GrBackendSurfaceMutableState* newState) {
    ... ...
    bool flushed = !resourceAllocator.failedInstantiation() &&
                    this->executeRenderTasks(&flushState);
    this->removeRenderTasks();
    ... ...
}

bool GrDrawingManager::executeRenderTasks(GrOpFlushState* flushState) {
    // Execute the normal op lists.
    for (const auto& renderTask : fDAG) {
        ... ...
        if (renderTask->execute(flushState)) {
            anyRenderTasksExecuted = true;
        }
        if (++numRenderTasksExecuted >= kMaxRenderTasksBeforeFlush) {
            flushState->gpu()->submitToGpu(false);
            numRenderTasksExecuted = 0;
        }
    }
```
`renderTask`的类型是`GrRenderTask`, 其实现是`GrOpsTask`, 因此:
```
// external/skia/src/gpu/GrRenderTask.h
class GrRenderTask : public SkRefCnt {
public:
    bool execute(GrOpFlushState* flushState) { return this->onExecute(flushState); }
    
// external/skia/src/gpu/GrOpsTask.cpp
bool GrOpsTask::onExecute(GrOpFlushState* flushState) {
    ... ...
    // Draw all the generated geometry.
    for (const auto& chain : fOpChains) {
        if (!chain.shouldExecute()) {
            continue;
        }
        GrOpFlushState::OpArgs opArgs(chain.head(),
                                      dstView,
                                      fUsesMSAASurface,
                                      chain.appliedClip(),
                                      chain.dstProxyView(),
                                      fRenderPassXferBarriers,
                                      fColorLoadOp);
        flushState->setOpArgs(&opArgs);
        chain.head()->execute(flushState, chain.bounds());
        flushState->setOpArgs(nullptr);
    }
```
此处开始依次执行每个`OpChain::head()`的`execute()`方法. 本文中此处的`GrOp`为`GrStrokeRectOp::Make()`所创建的`NonAAStrokeRectOp`, 其继承关系:`GrOp` -> `GrDrawOp` -> `GrMeshDrawOp` -> `NonAAStrokeRectOp`, 那么此时:
```
// external/skia/src/gpu/ops/GrOp.h
class GrOp : private SkNoncopyable {
public:
    ... ...
    /** Issues the op's commands to GrGpu. */
    void execute(GrOpFlushState* state, const SkRect& chainBounds) {
        TRACE_EVENT0("skia.gpu", name());
        this->onExecute(state, chainBounds);
    }

// external/skia/src/gpu/ops/GrStrokeRectOp.cpp
class NonAAStrokeRectOp final : public GrMeshDrawOp {
    ... ...
    void onExecute(GrOpFlushState* flushState, const SkRect& chainBounds) override {
        ... ...
        flushState->bindPipelineAndScissorClip(*fProgramInfo, chainBounds);
        flushState->bindTextures(fProgramInfo->geomProc(), nullptr, fProgramInfo->pipeline());
        flushState->drawMesh(*fMesh);
    }
```
显然这时调用了`GrOpFlushState`的各种方法完成绘图.

## 应用swapBuffer()提交窗口至SurfaceFlinger
在`SkiaOpenGLPipeline::draw()`完成工作后, `CanvasContext::draw()`将调用`SkiaOpenGLPipeline::swapBuffers()`, 查看其实现:
```
// frameworks/base/libs/hwui/pipeline/skia/SkiaOpenGLPipeline.cpp
bool SkiaOpenGLPipeline::swapBuffers(const Frame& frame, bool drew, const SkRect& screenDirty,
                                     FrameInfo* currentFrameInfo, bool* requireSwap) {
    ... ...
    if (*requireSwap && (CC_UNLIKELY(!mEglManager.swapBuffers(frame, screenDirty)))) {
        return false;
    }
    ... ...
}
```
`mEglManager`的类型是`EglManager`, 故:
```
// frameworks/base/libs/hwui/renderthread/EglManager.cpp
bool EglManager::swapBuffers(const Frame& frame, const SkRect& screenDirty) {
    ... ...
    eglSwapBuffersWithDamageKHR(mEglDisplay, frame.mSurface, rects, screenDirty.isEmpty() ? 0 : 1);
    ... ...
}
```
`eglSwapBuffersWithDamageKHR()`属于`libEGL.so`, 没有源码, 该方法执行完成后, `libEGL.so`将回调`ANativeWindow::queueBuffer`进一步回调到`Surface::hook_queueBuffer()`, 代码:
```
// frameworks/native/libs/gui/Surface.cpp
int Surface::hook_queueBuffer(ANativeWindow* window,
        ANativeWindowBuffer* buffer, int fenceFd) {
    Surface* c = getSelf(window);
    {
        std::shared_lock<std::shared_mutex> lock(c->mInterceptorMutex);
        if (c->mQueueInterceptor != nullptr) {
            auto interceptor = c->mQueueInterceptor;
            auto data = c->mQueueInterceptorData;
            return interceptor(window, Surface::queueBufferInternal, data, buffer, fenceFd);
        }
    }
    return c->queueBuffer(buffer, fenceFd);
}

int Surface::queueBufferInternal(ANativeWindow* window, ANativeWindowBuffer* buffer, int fenceFd) {
    Surface* c = getSelf(window);
    return c->queueBuffer(buffer, fenceFd);
}


int Surface::queueBuffer(android_native_buffer_t* buffer, int fenceFd) {
    ... ...
    status_t err = mGraphicBufferProducer->queueBuffer(i, input, &output);
    ... ...
}
```
Android S以后BufferQueue改到应用侧, 因此此处`mGraphicBufferProducer`为本地得`BufferQueueProducer`, 而不再通过Binder传递`GraphicBuffer`到`SurfaceFlinger`, 因此:
```
// frameworks/native/libs/gui/BufferQueueProducer.cpp
status_t BufferQueueProducer::queueBuffer(int slot,
        const QueueBufferInput &input, QueueBufferOutput *output) {
    ... ...
    { // scope for the lock
        ... ...
        if (frameAvailableListener != nullptr) {
            frameAvailableListener->onFrameAvailable(item);
        } else if (frameReplacedListener != nullptr) {
            frameReplacedListener->onFrameReplaced(item);
        }
```
此处得`frameAvailableListener`是`BLASTBufferQueue`, 因此`BLASTBufferQueue::onFrameAvailable()`被调用:
```
// frameworks/native/libs/gui/BLASTBufferQueue.cpp
    return item.mCrop;
}

void BLASTBufferQueue::onFrameAvailable(const BufferItem& item) {
    ... ...
    processNextBufferLocked(nextTransactionSet /* useNextTransaction */);
}

void BLASTBufferQueue::processNextBufferLocked(bool useNextTransaction) {
    ... ...
    SurfaceComposerClient::Transaction* t = &localTransaction;
    ... ...
    if (applyTransaction) {
        t->setApplyToken(mApplyToken).apply();
    }
```
显然调用到`SurfaceComposerClient::Transaction::apply()`:
```
// frameworks/native/libs/gui/SurfaceComposerClient.cpp
status_t SurfaceComposerClient::Transaction::apply(bool synchronous) {
    ... ...
    sf->setTransactionState(mFrameTimelineInfo, composerStates, displayStates, flags, applyToken,
                            mInputWindowCommands, mDesiredPresentTime, mIsAutoTimestamp,
                            {} /*uncacheBuffer - only set in doUncacheBufferTransaction*/,
                            hasListenerCallbacks, listenerCallbacks, mId);
    ... ...
}
```
此时通过Binder, `SurfaceFlinger::setTransactionState()`被调用:
```
// frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp
status_t SurfaceFlinger::setTransactionState(
        const FrameTimelineInfo& frameTimelineInfo, const Vector<ComposerState>& states,
        const Vector<DisplayState>& displays, uint32_t flags, const sp<IBinder>& applyToken,
        const InputWindowCommands& inputWindowCommands, int64_t desiredPresentTime,
        bool isAutoTimestamp, const client_cache_t& uncacheBuffer, bool hasListenerCallbacks,
        const std::vector<ListenerCallbacks>& listenerCallbacks, uint64_t transactionId) {
    ... ...
    queueTransaction(state);
    ... ...

void SurfaceFlinger::queueTransaction(TransactionState& state) {
    ... ...

    setTransactionFlags(eTransactionFlushNeeded, schedule, state.applyToken);
}

uint32_t SurfaceFlinger::setTransactionFlags(uint32_t flags) {
    return setTransactionFlags(flags, TransactionSchedule::Late);
}

uint32_t SurfaceFlinger::setTransactionFlags(uint32_t flags, TransactionSchedule schedule,
                                             const sp<IBinder>& token) {
    ... ...
    if ((old & flags) == 0) signalTransaction();
    return old;
}

void SurfaceFlinger::signalTransaction() {
    mScheduler->resetIdleTimer();
    mPowerAdvisor.notifyDisplayUpdateImminent();
    mEventQueue->invalidate();
}
```
此处比较关键的操作是:`mEventQueue->invalidate()`, 对应`MessageQueue::invalidate()`:
```
// frameworks/native/services/surfaceflinger/Scheduler/MessageQueue.cpp
    mLooper->sendMessage(handler, Message());
}

void MessageQueue::invalidate() {
    ... ...
    mVsync.expectedWakeupTime =
            mVsync.registration->schedule({.workDuration = mVsync.workDuration.get().count(),
                                           .readyDuration = 0,
                                           .earliestVsync = mVsync.lastCallbackTime.count()});
}
```
尤其注意此处的`mVsync.registration->schedule()`, 该方法调度了一个`VSyncCallbackRegistration`在`Scheduler`, 而此处的`VSyncCallbackRegistration`在如下位置被注册:
```
// frameworks/native/services/surfaceflinger/Scheduler/MessageQueue.cpp
void MessageQueue::initVsync(scheduler::VSyncDispatch& dispatch,
                             frametimeline::TokenManager& tokenManager,
                             std::chrono::nanoseconds workDuration) {
    setDuration(workDuration);
    mVsync.tokenManager = &tokenManager;
    mVsync.registration = std::make_unique<
            scheduler::VSyncCallbackRegistration>(dispatch,
                                                  std::bind(&MessageQueue::vsyncCallback, this,
                                                            std::placeholders::_1,
                                                            std::placeholders::_2,
                                                            std::placeholders::_3),
                                                  "sf");
}
```
回到`VSyncDispatchTimerQueue::timerCallback()`方法中, 其通过`invocation.callback->callback()`通知App完成绘制时, 也继续调用了`MessageQueue::vsyncCallback()`方法, 因此:
```
// frameworks/native/services/surfaceflinger/Scheduler/MessageQueue.cpp
void MessageQueue::vsyncCallback(nsecs_t vsyncTime, nsecs_t targetWakeupTime, nsecs_t readyTime) {
    ... ...
    mHandler->dispatchInvalidate(mVsync.tokenManager->generateTokenForPredictions(
                                         {targetWakeupTime, readyTime, vsyncTime}),
    ... ...
}

void MessageQueue::Handler::dispatchInvalidate(int64_t vsyncId, nsecs_t expectedVSyncTimestamp) {
    if ((mEventMask.fetch_or(eventMaskInvalidate) & eventMaskInvalidate) == 0) {
        ... ....
        mQueue.mLooper->sendMessage(this, Message(MessageQueue::INVALIDATE));
    }
}
```
这里的`MessageQueue::INVALIDATE`消息会被`MessageQueue::Handler::handleMessage`响应, 因此:
```

void MessageQueue::Handler::handleMessage(const Message& message) {
    switch (message.what) {
        case INVALIDATE:
            mEventMask.fetch_and(~eventMaskInvalidate);
            mQueue.mFlinger->onMessageReceived(message.what, mVsyncId, mExpectedVSyncTime);
            break;
        case REFRESH:
            ... ...
            break;
    }
}
```

## SurfaceFlinger合成窗口
显然`SurfaceFlinger::onMessageReceived()`被调用:
```
// frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp
void SurfaceFlinger::onMessageReceived(int32_t what, int64_t vsyncId, nsecs_t expectedVSyncTime) {
    switch (what) {
        case MessageQueue::INVALIDATE: {
            onMessageInvalidate(vsyncId, expectedVSyncTime);
            break;
        }
        ... ...
    }
}

void SurfaceFlinger::onMessageInvalidate(int64_t vsyncId, nsecs_t expectedVSyncTime) {
    ... ...
    mCompositionEngine->present(refreshArgs);
    ... ...
```
`SurfaceFlinger`调用了`CompositionEngine::present()`对App发送过来的`Layer`进行合成:
```
// frameworks/native/services/surfaceflinger/CompositionEngine/src/CompositionEngine.cpp
void CompositionEngine::present(CompositionRefreshArgs& args) {
    preComposition(args);
    {
        ... ...
        LayerFESet latchedLayers;

        for (const auto& output : args.outputs) {
            output->prepare(args, latchedLayers);
        }
    }
    updateLayerStateFromFE(args);
    for (const auto& output : args.outputs) {
        output->present(args);
    }
}
```
显然有:
```
void Output::present(const compositionengine::CompositionRefreshArgs& refreshArgs) {
    ATRACE_CALL();
    ALOGV(__FUNCTION__);

    updateColorProfile(refreshArgs);
    updateCompositionState(refreshArgs);
    planComposition();
    writeCompositionState(refreshArgs);
    setColorTransform(refreshArgs);
    beginFrame();
    prepareFrame();
    devOptRepaintFlash(refreshArgs);
    finishFrame(refreshArgs);
    postFramebuffer();
    renderCachedSets(refreshArgs);
}
```
在`Output::finishFrame()`时有:
```
void Output::finishFrame(const compositionengine::CompositionRefreshArgs& refreshArgs) {
    ... ...
    // swap buffers (presentation)
    mRenderSurface->queueBuffer(std::move(*optReadyFence));
}
```
## 渲染引擎合成到Composer
`mRenderSurface->queueBuffer()`完成将合成的屏幕内容送显.
在`Output::postFramebuffer()`时有:
```
void Output::postFramebuffer() {
    ... ...
    mRenderSurface->flip();
    auto frame = presentAndGetFrameFences();
    ... ...
}

compositionengine::Output::FrameFences Output::presentAndGetFrameFences() {
    compositionengine::Output::FrameFences result;
    if (getState().usesClientComposition) {
        result.clientTargetAcquireFence = mRenderSurface->getClientTargetAcquireFence();
    }
    return result;
}
```
`mRenderSurface->flip()`完成交换动作, `presentAndGetFrameFences()`用于等待`mRenderSurface`释放交换回来的无用缓冲区.