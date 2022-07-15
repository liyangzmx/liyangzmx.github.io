- [Camera在拍照模式和视频模式使用的API差异](#camera在拍照模式和视频模式使用的api差异)
  - [拍照模式下同够`API2`打开`Camera`](#拍照模式下同够api2打开camera)
  - [视频模式通过`API1`打开`Camera`](#视频模式通过api1打开camera)

# Camera在拍照模式和视频模式使用的API差异
## 拍照模式下同够`API2`打开`Camera`

在模式列表中选择Video模式时, 如下方法被调用:
```
// packages/apps/Camera2/src/com/android/camera/ui/ModeListView.java
    private void onModeSelected(int modeIndex) {
        if (mModeSwitchListener != null) {
            mModeSwitchListener.onModeSelected(modeIndex);
        }
    }
```
此处`ModeListView.ModeSwitchListener`的实现是`CameraAppUI`, 因此:
```
// packages/apps/Camera2/src/com/android/camera/app/CameraAppUI.java
    @Override
    public void onModeSelected(int modeIndex) {
        ...
        mController.onModeSelected(modeIndex);
        ...
```
`mController`的类型是`AppController`, 其实现是`CameraActivity`, 因此:
```
// packages/apps/Camera2/src/com/android/camera/CameraActivity.java
    @Override
    public void onModeSelected(int modeIndex) {
        ...
        mCameraAppUI.resetBottomControls(mCurrentModule, modeIndex);
        mCameraAppUI.addShutterListener(mCurrentModule);
        openModule(mCurrentModule);
        // Store the module index so we can use it the next time the Camera
        // starts up.
        mSettingsManager.set(SettingsManager.SCOPE_GLOBAL,
                             Keys.KEY_STARTUP_MODULE_INDEX, modeIndex);
    }

    private void openModule(CameraModule module) {
        module.init(this, isSecureCamera(), isCaptureIntent());
        module.hardResetSettings(mSettingsManager);
        // Hide accessibility zoom UI by default. Modules will enable it themselves if required.
        getCameraAppUI().hideAccessibilityZoomUI();
        if (!mPaused) {
            module.resume();
            ...
        }
    }
```
此处的`module`显然是`CaptureModule`(继承自`CameraModule`), 由于测试时是切出切回的, `init()`略过:
```
// packages/apps/Camera2/src/com/android/camera/CaptureModule.java
    @Override
    public void resume() {
        ...
        if (texture != null) {
            initSurfaceTextureConsumer();
        }
        ...
    }

    private void initSurfaceTextureConsumer() {
        ...
        reopenCamera();
    }

    private void reopenCamera() {
        ...
        AsyncTask.THREAD_POOL_EXECUTOR.execute(new Runnable() {
            @Override
            public void run() {
                closeCamera();
                if(!mAppController.isPaused()) {
                    openCameraAndStartPreview();
                }
            }
        });
    }

    private void openCameraAndStartPreview() {
        ...
        mOneCameraOpener.open(cameraId, captureSetting, mCameraHandler, mainThread,
              imageRotationCalculator, mBurstController, mSoundPlayer,
              new OpenCallback() {
                  ...
              }, mAppController.getFatalErrorHandler());
        guard.stop("mOneCameraOpener.open()");
    }

// packages/apps/Camera2/src/com/android/camera/one/v2/Camera2OneCameraOpenerImpl.java
    @Override
    public void open(
            final CameraId cameraKey,
            final OneCameraCaptureSetting captureSetting,
            ... ...
            final OpenCallback openCallback,
            final FatalErrorHandler fatalErrorHandler) {
        try {
            ...
            mCameraManager.openCamera(cameraKey.getValue(), new CameraDevice.StateCallback() {
                ...
            }, handler);
            ...
        }
        ...
    }
```
`mCameraManager`的类型是`CameraManager`:
```
// frameworks/base/core/java/android/hardware/camera2/CameraManager.java
    @RequiresPermission(android.Manifest.permission.CAMERA)
    public void openCamera(@NonNull String cameraId,
            @NonNull final CameraDevice.StateCallback callback, @Nullable Handler handler)
            throws CameraAccessException {

        openCameraForUid(cameraId, callback, CameraDeviceImpl.checkAndWrapHandler(handler),
                USE_CALLING_UID);
    }

    public void openCameraForUid(@NonNull String cameraId,
            @NonNull final CameraDevice.StateCallback callback, @NonNull Executor executor,
            int clientUid) throws CameraAccessException {
            openCameraForUid(cameraId, callback, executor, clientUid, /*oomScoreOffset*/0);
    }

    public void openCameraForUid(@NonNull String cameraId,
            @NonNull final CameraDevice.StateCallback callback, @NonNull Executor executor,
            int clientUid, int oomScoreOffset) throws CameraAccessException {
        ...
        openCameraDeviceUserAsync(cameraId, callback, executor, clientUid, oomScoreOffset);
    }

    private CameraDevice openCameraDeviceUserAsync(String cameraId,
            CameraDevice.StateCallback callback, Executor executor, final int uid,
            final int oomScoreOffset) throws CameraAccessException {
        ...
        synchronized (mLock) {
            ICameraDeviceUser cameraUser = null;
            android.hardware.camera2.impl.CameraDeviceImpl deviceImpl =
                    new android.hardware.camera2.impl.CameraDeviceImpl(
                        cameraId,
                        callback,
                        ...
                        mContext.getApplicationInfo().targetSdkVersion,
                        mContext);
            ICameraDeviceCallbacks callbacks = deviceImpl.getCallbacks();
            try {
                ICameraService cameraService = CameraManagerGlobal.get().getCameraService();
                ...
                cameraUser = cameraService.connectDevice(callbacks, cameraId,
                    mContext.getOpPackageName(),  mContext.getAttributionTag(), uid,
                    oomScoreOffset, mContext.getApplicationInfo().targetSdkVersion);
            }
            ...
        }
        return device;
    }
```
`cameraService`的类型是`ICameraService`, 因此`cameraService.connectDevice()`将通过`Binder`调用到`cameraserver`的`CameraService::connectDevice()`:
```
// frameworks/av/services/camera/libcameraservice/CameraService.cpp
Status CameraService::connectDevice(
        const sp<hardware::camera2::ICameraDeviceCallbacks>& cameraCb,
        const String16& cameraId,
        const String16& clientPackageName,
        const std::optional<String16>& clientFeatureId,
        int clientUid, int oomScoreOffset, int targetSdkVersion,
        /*out*/
        sp<hardware::camera2::ICameraDeviceUser>* device) {
    ...
    ret = connectHelper<hardware::camera2::ICameraDeviceCallbacks,CameraDeviceClient>(cameraCb, id,
            /*api1CameraId*/-1, clientPackageNameAdj, clientFeatureId,
            clientUid, USE_CALLING_PID, API_2, /*shimUpdateOnly*/ false, oomScoreOffset,
            targetSdkVersion, /*out*/client);
    ...
```
显然, 接下来将创建`CameraDeviceClient`了:
```
template<class CALLBACK, class CLIENT>
Status CameraService::connectHelper(const sp<CALLBACK>& cameraCb, const String8& cameraId,
        int api1CameraId, const String16& clientPackageName,
        const std::optional<String16>& clientFeatureId, int clientUid, int clientPid,
        apiLevel effectiveApiLevel, bool shimUpdateOnly, int oomScoreOffset, int targetSdkVersion,
        /*out*/sp<CLIENT>& device) {
    ...
    {
        ...
        sp<BasicClient> tmp = nullptr;
        bool overrideForPerfClass = SessionConfigurationUtils::targetPerfClassPrimaryCamera(
                mPerfClassPrimaryCameraIds, cameraId.string(), targetSdkVersion);
        if(!(ret = makeClient(this, cameraCb, clientPackageName, clientFeatureId,
                cameraId, api1CameraId, facing, orientation,
                clientPid, clientUid, getpid(),
                deviceVersion, effectiveApiLevel, overrideForPerfClass,
                /*out*/&tmp)).isOk()) {
            return ret;
        }

Status CameraService::makeClient(const sp<CameraService>& cameraService,
        const sp<IInterface>& cameraCb, const String16& packageName,
        const std::optional<String16>& featureId,  const String8& cameraId,
        int api1CameraId, int facing, int sensorOrientation, int clientPid, uid_t clientUid,
        int servicePid, int deviceVersion, apiLevel effectiveApiLevel, bool overrideForPerfClass,
        /*out*/sp<BasicClient>* client) {

    // Create CameraClient based on device version reported by the HAL.
    switch(deviceVersion) {
        case CAMERA_DEVICE_API_VERSION_1_0:
            ...
        case CAMERA_DEVICE_API_VERSION_3_0:
        case CAMERA_DEVICE_API_VERSION_3_1:
        case CAMERA_DEVICE_API_VERSION_3_2:
        case CAMERA_DEVICE_API_VERSION_3_3:
        case CAMERA_DEVICE_API_VERSION_3_4:
        case CAMERA_DEVICE_API_VERSION_3_5:
        case CAMERA_DEVICE_API_VERSION_3_6:
        case CAMERA_DEVICE_API_VERSION_3_7:
            if (effectiveApiLevel == API_1) { // Camera1 API route
                ...
            } else { // Camera2 API route
                sp<hardware::camera2::ICameraDeviceCallbacks> tmp =
                        static_cast<hardware::camera2::ICameraDeviceCallbacks*>(cameraCb.get());
                *client = new CameraDeviceClient(cameraService, tmp, packageName, featureId,
                        cameraId, facing, sensorOrientation, clientPid, clientUid, servicePid,
                        overrideForPerfClass);
            }
            break;
        ...
    }
    ...
}
```
本情形`effectiveApiLevel`的值是`API_2`:
```
// frameworks/av/services/camera/libcameraservice/api2/CameraDeviceClient.cpp
CameraDeviceClient::CameraDeviceClient(const sp<CameraService>& cameraService,
        const sp<hardware::camera2::ICameraDeviceCallbacks>& remoteCallback,
        ...
        bool overrideForPerfClass) :
    Camera2ClientBase(cameraService, remoteCallback, clientPackageName, clientFeatureId,
                cameraId, /*API1 camera ID*/ -1, cameraFacing, sensorOrientation,
                clientPid, clientUid, servicePid, overrideForPerfClass),
    mInputStream(),
    mStreamingRequestId(REQUEST_ID_NONE),
    mRequestIdCounter(0),
    mOverrideForPerfClass(overrideForPerfClass) {
        ...
}

// frameworks/av/services/camera/libcameraservice/common/Camera2ClientBase.cpp
Camera2ClientBase<TClientBase>::Camera2ClientBase(
        const sp<CameraService>& cameraService,
        const sp<TCamCallbacks>& remoteCallback,
        ...
        bool overrideForPerfClass):
        TClientBase(cameraService, remoteCallback, clientPackageName, clientFeatureId,
                cameraId, api1CameraId, cameraFacing, sensorOrientation, clientPid, clientUid,
                servicePid),
        mSharedCameraCallbacks(remoteCallback),
        mDeviceVersion(cameraService->getDeviceVersion(TClientBase::mCameraIdStr)),
        mDevice(new Camera3Device(cameraId, overrideForPerfClass)),
        mDeviceActive(false), mApi1CameraId(api1CameraId)
{
    ...
}
```
`TClientBase`的类型是`CameraDeviceClientBase`, 故:
```
CameraDeviceClientBase::CameraDeviceClientBase(
        const sp<CameraService>& cameraService,
        const sp<hardware::camera2::ICameraDeviceCallbacks>& remoteCallback,
        ...
        int servicePid) :
    BasicClient(cameraService,
            IInterface::asBinder(remoteCallback),
            ...
            servicePid),
    mRemoteCallback(remoteCallback) {
    ...
}

CameraService::BasicClient::BasicClient(const sp<CameraService>& cameraService,
        const sp<IBinder>& remoteCallback,
        const String16& clientPackageName, const std::optional<String16>& clientFeatureId,
        const String8& cameraIdStr, int cameraFacing, int sensorOrientation,
        int clientPid, uid_t clientUid,
        int servicePid):
        mDestructionStarted(false),
        mCameraIdStr(cameraIdStr), mCameraFacing(cameraFacing), mOrientation(sensorOrientation),
        mClientPackageName(clientPackageName), mClientFeatureId(clientFeatureId),
        mClientPid(clientPid), mClientUid(clientUid),
        mServicePid(servicePid),
        mDisconnected(false), mUidIsTrusted(false),
        mAudioRestriction(hardware::camera2::ICameraDeviceUser::AUDIO_RESTRICTION_NONE),
        mRemoteBinder(remoteCallback),
        mOpsActive(false),
        mOpsStreaming(false)
{
    ...
}
```
对于`CameraService::Client`, 其不但继承`BasicClient`还实现了`BnCameraDeviceUser`, 这意味着它将通过`ICameraDeviceUser`响应App的请求.

## 视频模式通过`API1`打开`Camera`
在模式列表中选择Video模式时, 如下方法被调用:
```
// packages/apps/Camera2/src/com/android/camera/ui/ModeListView.java
    private void onModeSelected(int modeIndex) {
        if (mModeSwitchListener != null) {
            mModeSwitchListener.onModeSelected(modeIndex);
        }
    }
```
此处`ModeListView.ModeSwitchListener`的实现是`CameraAppUI`, 因此:
```
// packages/apps/Camera2/src/com/android/camera/app/CameraAppUI.java
    @Override
    public void onModeSelected(int modeIndex) {
        ...
        mController.onModeSelected(modeIndex);
        ...
```
`mController`的类型是`AppController`, 其实现是`CameraActivity`, 因此:
```
// packages/apps/Camera2/src/com/android/camera/CameraActivity.java
    @Override
    public void onModeSelected(int modeIndex) {
        ...
        mCameraAppUI.resetBottomControls(mCurrentModule, modeIndex);
        mCameraAppUI.addShutterListener(mCurrentModule);
        openModule(mCurrentModule);
        // Store the module index so we can use it the next time the Camera
        // starts up.
        mSettingsManager.set(SettingsManager.SCOPE_GLOBAL,
                             Keys.KEY_STARTUP_MODULE_INDEX, modeIndex);
    }

    private void openModule(CameraModule module) {
        module.init(this, isSecureCamera(), isCaptureIntent());
        ...
    }
```
此处的`module`显然是`VideoModule`(继承自`CameraModule`), 故:
```
// packages/apps/Camera2/src/com/android/camera/VideoModule.java
    @Override
    public void init(CameraActivity activity, boolean isSecureCamera, boolean isCaptureIntent) {
        ...
        /*
         * To reduce startup time, we start the preview in another thread.
         * We make sure the preview is started at the end of onCreate.
         */
        requestCamera(mCameraId);
        ...
    }
    private void requestCamera(int id) {
        mActivity.getCameraProvider().requestCamera(id);
    }

    @Override
    public CameraProvider getCameraProvider() {
        return mCameraController;
    }
```
显然`mCameraController`的类型是`CameraController`, 因此:
```
// packages/apps/Camera2/src/com/android/camera/app/CameraController.java
    @Override
    public void requestCamera(int id) {
        requestCamera(id, false);
    }

    @Override
    public void requestCamera(int id, boolean useNewApi) {
        ...
        if (mCameraProxy == null) {
            // No camera yet.
            checkAndOpenCamera(cameraManager, id, mCallbackHandler, this);
        } else if (mCameraProxy.getCameraId() != id || mUsingNewApi != useNewApi) {
            ...
        }
        ...
    }

    private static void checkAndOpenCamera(CameraAgent cameraManager,
            final int cameraId, Handler handler, final CameraAgent.CameraOpenCallback cb) {
        Log.v(TAG, "checkAndOpenCamera");
        try {
            CameraUtil.throwIfCameraDisabled();
            cameraManager.openCamera(handler, cameraId, cb);
        } catch (CameraDisabledException ex) {
            ...
        }
    }
```
如参数, `cameraManager`的类型是`CameraAgent`(其实现是`AndroidCameraAgentImpl`):
```
// frameworks/ex/camera2/portability/src/com/android/ex/camera2/portability/CameraAgent.java
    public void openCamera(final Handler handler, final int cameraId,
                           final CameraOpenCallback callback) {
        try {
            getDispatchThread().runJob(new Runnable() {
                @Override
                public void run() {
                    getCameraHandler().obtainMessage(CameraActions.OPEN_CAMERA, cameraId, 0,
                            CameraOpenCallbackForward.getNewInstance(handler, callback)).sendToTarget();
                }
            });
        } catch (final RuntimeException ex) {
            ...
        }
    }
```
`CameraActions.OPEN_CAMERA`消息被`CameraAgent`的子类`AndroidCameraAgentImpl`处理:
```
// frameworks/ex/camera2/portability/src/com/android/ex/camera2/portability/AndroidCameraAgentImpl.java
        @Override
        public void handleMessage(final Message msg) {
            ...
            int cameraAction = msg.what;
            try {
                switch (cameraAction) {
                    case CameraActions.OPEN_CAMERA: {
                        ...
                        mCamera = android.hardware.Camera.open(cameraId);
                        ...

// frameworks/base/core/java/android/hardware/Camera.java
    public static Camera open(int cameraId) {
        return new Camera(cameraId);
    }

    /** used by Camera#open, Camera#open(int) */
    Camera(int cameraId) {
        int err = cameraInit(cameraId);
        ...
        initAppOps();
    }

    private int cameraInit(int cameraId) {
        ...
        return native_setup(new WeakReference<Camera>(this), cameraId,
                ActivityThread.currentOpPackageName());
    }
```
此时调用到Native:
```
// frameworks/base/core/jni/android_hardware_Camera.cpp
// connect to camera service
static jint android_hardware_Camera_native_setup(JNIEnv *env, jobject thiz,
    jobject weak_this, jint cameraId, jstring clientPackageName)
{
    ...
    sp<Camera> camera = Camera::connect(cameraId, clientName, Camera::USE_CALLING_UID,
                                        Camera::USE_CALLING_PID, targetSdkVersion);
    ...
}

// frameworks/av/camera/Camera.cpp
sp<Camera> Camera::connect(int cameraId, const String16& clientPackageName,
        int clientUid, int clientPid, int targetSdkVersion)
{
    return CameraBaseT::connect(cameraId, clientPackageName, clientUid,
            clientPid, targetSdkVersion);
}
```
`CameraBaseT`的类型是`CameraBase`:
```
// frameworks/av/camera/CameraBase.cpp
template <typename TCam, typename TCamTraits>
sp<TCam> CameraBase<TCam, TCamTraits>::connect(int cameraId,
                                               const String16& clientPackageName,
                                               int clientUid, int clientPid, int targetSdkVersion)
{
    ALOGV("%s: connect", __FUNCTION__);
    sp<TCam> c = new TCam(cameraId);
    sp<TCamCallbacks> cl = c;
    const sp<::android::hardware::ICameraService> cs = getCameraService();

    binder::Status ret;
    if (cs != nullptr) {
        TCamConnectService fnConnectService = TCamTraits::fnConnectService;
        ret = (cs.get()->*fnConnectService)(cl, cameraId, clientPackageName, clientUid,
                                               clientPid, targetSdkVersion, /*out*/ &c->mCamera);
    }
    ...
    return c;
}

```
`TCam`在该模板中是`android::Camera`:
```
// frameworks/av/camera/Camera.cpp
Camera::Camera(int cameraId)
    : CameraBase(cameraId)
{
}

// frameworks/av/camera/CameraBase.cpp
CameraBase<TCam, TCamTraits>::CameraBase(int cameraId) :
    mStatus(UNKNOWN_ERROR),
    mCameraId(cameraId)
{
}
```
回到`CameraBase::connect()`, `(cs.get()->*fnConnectService)`的结果是`ICameraService::connect()`:
```
// frameworks/av/services/camera/libcameraservice/CameraService.cpp
Status CameraService::connect(
        const sp<ICameraClient>& cameraClient,
        int api1CameraId,
        const String16& clientPackageName,
        int clientUid,
        int clientPid,
        int targetSdkVersion,
        /*out*/
        sp<ICamera>* device) {
    ...
    ret = connectHelper<ICameraClient,Client>(cameraClient, id, api1CameraId,
            clientPackageName, {}, clientUid, clientPid, API_1,
            /*shimUpdateOnly*/ false, /*oomScoreOffset*/ 0, targetSdkVersion, /*out*/client);
    ...
```
显然, 即将创建`Camera::Client`了:
```
template<class CALLBACK, class CLIENT>
Status CameraService::connectHelper(const sp<CALLBACK>& cameraCb, const String8& cameraId,
        int api1CameraId, const String16& clientPackageName,
        const std::optional<String16>& clientFeatureId, int clientUid, int clientPid,
        apiLevel effectiveApiLevel, bool shimUpdateOnly, int oomScoreOffset, int targetSdkVersion,
        /*out*/sp<CLIENT>& device) {
    ...
    {
        ...
        sp<BasicClient> tmp = nullptr;
        bool overrideForPerfClass = SessionConfigurationUtils::targetPerfClassPrimaryCamera(
                mPerfClassPrimaryCameraIds, cameraId.string(), targetSdkVersion);
        if(!(ret = makeClient(this, cameraCb, clientPackageName, clientFeatureId,
                cameraId, api1CameraId, facing, orientation,
                clientPid, clientUid, getpid(),
                deviceVersion, effectiveApiLevel, overrideForPerfClass,
                /*out*/&tmp)).isOk()) {
            return ret;
        }

Status CameraService::makeClient(const sp<CameraService>& cameraService,
        const sp<IInterface>& cameraCb, const String16& packageName,
        const std::optional<String16>& featureId,  const String8& cameraId,
        int api1CameraId, int facing, int sensorOrientation, int clientPid, uid_t clientUid,
        int servicePid, int deviceVersion, apiLevel effectiveApiLevel, bool overrideForPerfClass,
        /*out*/sp<BasicClient>* client) {

    // Create CameraClient based on device version reported by the HAL.
    switch(deviceVersion) {
        case CAMERA_DEVICE_API_VERSION_1_0:
            ...
        case CAMERA_DEVICE_API_VERSION_3_0:
        case CAMERA_DEVICE_API_VERSION_3_1:
        case CAMERA_DEVICE_API_VERSION_3_2:
        case CAMERA_DEVICE_API_VERSION_3_3:
        case CAMERA_DEVICE_API_VERSION_3_4:
        case CAMERA_DEVICE_API_VERSION_3_5:
        case CAMERA_DEVICE_API_VERSION_3_6:
        case CAMERA_DEVICE_API_VERSION_3_7:
            if (effectiveApiLevel == API_1) { // Camera1 API route
                sp<ICameraClient> tmp = static_cast<ICameraClient*>(cameraCb.get());
                *client = new Camera2Client(cameraService, tmp, packageName, featureId,
                        cameraId, api1CameraId,
                        facing, sensorOrientation, clientPid, clientUid,
                        servicePid, overrideForPerfClass);
            } else { // Camera2 API route
                ...
            }
            break;
        ...
    }
    ...
}
```
本情形`effectiveApiLevel`的值是`API_1`:
```
// frameworks/av/services/camera/libcameraservice/api1/Camera2Client.cpp
Camera2Client::Camera2Client(const sp<CameraService>& cameraService,
        const sp<hardware::ICameraClient>& cameraClient,
        ...
        Camera2ClientBase(cameraService, cameraClient, clientPackageName, clientFeatureId,
                cameraDeviceId, api1CameraId, cameraFacing, sensorOrientation,
                clientPid, clientUid, servicePid, overrideForPerfClass),
        mParameters(api1CameraId, cameraFacing)
{
    ...
}

// frameworks/av/services/camera/libcameraservice/common/Camera2ClientBase.cpp
Camera2ClientBase<TClientBase>::Camera2ClientBase(
        const sp<CameraService>& cameraService,
        const sp<TCamCallbacks>& remoteCallback,
        ...
        bool overrideForPerfClass):
        TClientBase(cameraService, remoteCallback, clientPackageName, clientFeatureId,
                cameraId, api1CameraId, cameraFacing, sensorOrientation, clientPid, clientUid,
                servicePid),
        mSharedCameraCallbacks(remoteCallback),
        mDeviceVersion(cameraService->getDeviceVersion(TClientBase::mCameraIdStr)),
        mDevice(new Camera3Device(cameraId, overrideForPerfClass)),
        mDeviceActive(false), mApi1CameraId(api1CameraId)
{
    ...
}
```
`TClientBase`的类型是`CameraService::Client`, 故:
```
// frameworks/av/services/camera/libcameraservice/CameraService.cpp
CameraService::Client::Client(const sp<CameraService>& cameraService,
        const sp<ICameraClient>& cameraClient,
        ...
        CameraService::BasicClient(cameraService,
                IInterface::asBinder(cameraClient),
                clientPackageName, clientFeatureId,
                cameraIdStr, cameraFacing, sensorOrientation,
                clientPid, clientUid,
                servicePid),
        mCameraId(api1CameraId)
{
    ...
    mRemoteCallback = cameraClient;
    ...
}

CameraService::BasicClient::BasicClient(const sp<CameraService>& cameraService,
        const sp<IBinder>& remoteCallback,
        const String16& clientPackageName, const std::optional<String16>& clientFeatureId,
        const String8& cameraIdStr, int cameraFacing, int sensorOrientation,
        int clientPid, uid_t clientUid,
        int servicePid):
        mDestructionStarted(false),
        mCameraIdStr(cameraIdStr), mCameraFacing(cameraFacing), mOrientation(sensorOrientation),
        mClientPackageName(clientPackageName), mClientFeatureId(clientFeatureId),
        mClientPid(clientPid), mClientUid(clientUid),
        mServicePid(servicePid),
        mDisconnected(false), mUidIsTrusted(false),
        mAudioRestriction(hardware::camera2::ICameraDeviceUser::AUDIO_RESTRICTION_NONE),
        mRemoteBinder(remoteCallback),
        mOpsActive(false),
        mOpsStreaming(false)
{
    ...
}
```
对于`CameraService::Client`, 其不但继承`BasicClient`还实现了`BnCamera`, 这意味着它将通过`ICamera`响应App的请求.