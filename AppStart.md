## Luancher3 启动应用
当点击`Launcher3`的图标时, `ItemClickHandler.onClick()`方法被调用:
```
// packages/apps/Launcher3/src/com/android/launcher3/touch/ItemClickHandler.java
    private static void onClick(View v) {
        ... ...
        Launcher launcher = Launcher.getLauncher(v.getContext());
        ... ...
        Object tag = v.getTag();
        if (tag instanceof WorkspaceItemInfo) {
            onClickAppShortcut(v, (WorkspaceItemInfo) tag, launcher);
        } ... ...
        ... ...
    }

    public static void onClickAppShortcut(View v, WorkspaceItemInfo shortcut, Launcher launcher) {
        ... ...
        startAppShortcutOrInfoActivity(v, shortcut, launcher);
    }

    private static void startAppShortcutOrInfoActivity(View v, ItemInfo item, Launcher launcher) {
        ... ...
        launcher.startActivitySafely(v, intent, item);
    }
```
`launcher`的类型为`Launcher`, 实现为`QuickstepLauncher`, 因此:
```
// packages/apps/Launcher3/quickstep/src/com/android/launcher3/uioverrides/QuickstepLauncher.java
    @Override
    public boolean startActivitySafely(View v, Intent intent, ItemInfo item) {
        // Only pause is taskbar controller is not present
        mHotseatPredictionController.setPauseUIUpdate(getTaskbarUIController() == null);
        return super.startActivitySafely(v, intent, item);
    }
```
``的父类为`Launcher`, 因此:
```
// packages/apps/Launcher3/src/com/android/launcher3/Launcher.java
    @Override
    public boolean startActivitySafely(View v, Intent intent, ItemInfo item) {
        ... ...
        boolean success = super.startActivitySafely(v, intent, item);
        ... ...
    }
```
`Launcher`的父类为`StatefulActivity<LauncherState>`, 而`StatefulActivity<LauncherState>`父类为`BaseDraggingActivity`, 因此:
```
// packages/apps/Launcher3/src/com/android/launcher3/BaseDraggingActivity.java
    public boolean startActivitySafely(View v, Intent intent, @Nullable ItemInfo item) {
        ... ...
        try {
            ... ...
            if (isShortcut) {
                ... ...
            } else if (user == null || user.equals(Process.myUserHandle())) {
                // Could be launching some bookkeeping activity
                startActivity(intent, optsBundle);
            } ... ...
            ... ...
        }
        ... ...
    }
```
继续调用父类`Activity`的`startActvity()`方法:
```
// frameworks/base/core/java/android/app/Activity.java
    @Override
    public void startActivity(Intent intent, @Nullable Bundle options) {
        ... ...
        if (options != null) {
            startActivityForResult(intent, -1, options);
        } else {
            // Note we want to go through this call for compatibility with
            // applications that may have overridden the method.
            startActivityForResult(intent, -1);
        }
    }

    public void startActivityForResult(@RequiresPermission Intent intent, int requestCode) {
        startActivityForResult(intent, requestCode, null);
    }
```
此时的`Activity.startActivityForResult()`调回`BaseQuickstepLauncher.startActivityForResult()`方法:
```
// packages/apps/Launcher3/quickstep/src/com/android/launcher3/BaseQuickstepLauncher.java
    @Override
    public void startActivityForResult(Intent intent, int requestCode, Bundle options) {
        if (requestCode != -1) {
            ... ...
        } else {
            super.startActivityForResult(intent, requestCode, options);
        }
    }
```
`BaseQuickstepLauncher`又调了父类的`startActivityForResult()`方法:
```
// frameworks/base/core/java/android/app/Activity.java
    public void startActivityForResult(@RequiresPermission Intent intent, int requestCode,
            @Nullable Bundle options) {
        if (mParent == null) {
            options = transferSpringboardActivityOptions(options);
            Instrumentation.ActivityResult ar =
                mInstrumentation.execStartActivity(
                    this, mMainThread.getApplicationThread(), mToken, this,
                    intent, requestCode, options);
            ... ...
        } else ... ...
        ... ...
    }
```
这个`mInstrumentation`成员的类型是``, 其对应代码:
```
// frameworks/base/core/java/android/app/Instrumentation.java
    @UnsupportedAppUsage
    public ActivityResult execStartActivity(
            Context who, IBinder contextThread, IBinder token, Activity target,
            Intent intent, int requestCode, Bundle options) {
        ... ...
        try {
            ... ...
            int result = ActivityTaskManager.getService().startActivity(whoThread,
                    who.getOpPackageName(), who.getAttributionTag(), intent,
                    intent.resolveTypeIfNeeded(who.getContentResolver()), token,
                    target != null ? target.mEmbeddedID : null, requestCode, 0, null, options);
            checkStartActivityResult(result, intent);
        }
        ... ...
    }
```
`ActivityTaskManager.getService()`返回的是`IActivityTaskManager`接口:
```
// frameworks/base/core/java/android/app/ActivityTaskManager.java
    /** @hide */
    public static IActivityTaskManager getService() {
        return IActivityTaskManagerSingleton.get();
    }
```
至此`Launcher3`通过`IActivityTaskManager.startActivity()`发送启动活动的请求给`ActivityTaskManagerService`.

## 应用向`ActivityTaskManagerService`请求启动app
`ActivityTaskManagerService`负责从应用接受消息并启动`Activity`, 对应的方法是:`ActivityTaskManagerService.startActivity()`
```
// frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java
    @Override
    public final int startActivity(IApplicationThread caller, String callingPackage,
            String callingFeatureId, Intent intent, String resolvedType, IBinder resultTo,
            String resultWho, int requestCode, int startFlags, ProfilerInfo profilerInfo,
            Bundle bOptions) {
        return startActivityAsUser(caller, callingPackage, callingFeatureId, intent, resolvedType,
                resultTo, resultWho, requestCode, startFlags, profilerInfo, bOptions,
                UserHandle.getCallingUserId());
    }
    @Override
    public int startActivityAsUser(IApplicationThread caller, String callingPackage,
            String callingFeatureId, Intent intent, String resolvedType, IBinder resultTo,
            String resultWho, int requestCode, int startFlags, ProfilerInfo profilerInfo,
            Bundle bOptions, int userId) {
        return startActivityAsUser(caller, callingPackage, callingFeatureId, intent, resolvedType,
                resultTo, resultWho, requestCode, startFlags, profilerInfo, bOptions, userId,
                true /*validateIncomingUser*/);
    }
    private int startActivityAsUser(IApplicationThread caller, String callingPackage,
            @Nullable String callingFeatureId, Intent intent, String resolvedType,
            IBinder resultTo, String resultWho, int requestCode, int startFlags,
            ProfilerInfo profilerInfo, Bundle bOptions, int userId, boolean validateIncomingUser) {
        assertPackageMatchesCallingUid(callingPackage);
        enforceNotIsolatedCaller("startActivityAsUser");

        userId = getActivityStartController().checkTargetUser(userId, validateIncomingUser,
                Binder.getCallingPid(), Binder.getCallingUid(), "startActivityAsUser");

        // TODO: Switch to user app stacks here.
        return getActivityStartController().obtainStarter(intent, "startActivityAsUser")
                ... ...
                .execute();

    }
```
`getActivityStartController().obtainStarter()`返回的是
```
// frameworks/base/services/core/java/com/android/server/wm/ActivityStarter.java
    int execute() {
        try {
            ... ...
            synchronized (mService.mGlobalLock) {
                ... ...
                res = executeRequest(mRequest);
                ... ...
            }
            ... ...
        }
        ... ...
    }
    private int executeRequest(Request request) {
        ... ...
        mLastStartActivityResult = startActivityUnchecked(r, sourceRecord, voiceSession,
                request.voiceInteractor, startFlags, true /* doResume */, checkedOptions, inTask,
                restrictedBgActivity, intentGrants);
        ... ...
    }
    private int startActivityUnchecked(final ActivityRecord r, ActivityRecord sourceRecord,
                IVoiceInteractionSession voiceSession, IVoiceInteractor voiceInteractor,
                int startFlags, boolean doResume, ActivityOptions options, Task inTask,
                boolean restrictedBgActivity, NeededUriGrants intentGrants) {
        ... ...
        try {
            mService.deferWindowLayout();
            Trace.traceBegin(Trace.TRACE_TAG_WINDOW_MANAGER, "startActivityInner");
            result = startActivityInner(r, sourceRecord, voiceSession, voiceInteractor,
                    startFlags, doResume, options, inTask, restrictedBgActivity, intentGrants);
        }
        ... ...
    }
    int startActivityInner(final ActivityRecord r, ActivityRecord sourceRecord,
            IVoiceInteractionSession voiceSession, IVoiceInteractor voiceInteractor,
            int startFlags, boolean doResume, ActivityOptions options, Task inTask,
            boolean restrictedBgActivity, NeededUriGrants intentGrants) {
        ... ...
        if (mDoResume) {
            ... ...
            if (!mTargetRootTask.isTopActivityFocusable()
                    || (topTaskActivity != null && topTaskActivity.isTaskOverlay()
                    && mStartActivity != topTaskActivity)) {
                ... ....
            } else {
                ... ...
                mRootWindowContainer.resumeFocusedTasksTopActivities(
                        mTargetRootTask, mStartActivity, mOptions, mTransientLaunch);
            }
        }
        ... ...
    }
```
`mRootWindowContainer`的类型是`RootWindowContainer`, 因此:
```
// frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java
    boolean resumeFocusedTasksTopActivities(
            Task targetRootTask, ActivityRecord target, ActivityOptions targetOptions,
            boolean deferPause) {
        ... ...
        if (targetRootTask != null && (targetRootTask.isTopRootTaskInDisplayArea()
                || getTopDisplayFocusedRootTask() == targetRootTask)) {
            result = targetRootTask.resumeTopActivityUncheckedLocked(target, targetOptions,
                    deferPause);
        }
        ... ...
```
显然`targetRootTask`的类型是`Task`, 因此:
```
// frameworks/base/services/core/java/com/android/server/wm/Task.java
    boolean resumeTopActivityUncheckedLocked(ActivityRecord prev, ActivityOptions options,
            boolean deferPause) {
        ... ...
        try {
            ... ...
            if (isLeafTask()) {
                if (isFocusableAndVisible()) {
                    someActivityResumed = resumeTopActivityInnerLocked(prev, options, deferPause);
                    ... ...
                }
                ... ...
            }
            ... ...
        }
        .... ...
    }
    @GuardedBy("mService")
    private boolean resumeTopActivityInnerLocked(ActivityRecord prev, ActivityOptions options,
            boolean deferPause) {
        ... ...
        if (pausing) {
            ... ...
            if (next.attachedToProcess()) {
                ... ...
            } else if (!next.isProcessRunning()) {
                ... ....
                final boolean isTop = this == taskDisplayArea.getFocusedRootTask();
                mAtmService.startProcessAsync(next, false /* knownToBeDead */, isTop,
                        isTop ? "pre-top-activity" : "pre-activity");
            }
            ... ...
```
`mAtmService`的类型是`ActivityTaskManagerService`, 又调回`ActivityTaskManagerService`的`startProcessAsync()`方法了:
```
// frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java
    void startProcessAsync(ActivityRecord activity, boolean knownToBeDead, boolean isTop,
            String hostingType) {
        try {
            ... ...
            final Message m = PooledLambda.obtainMessage(ActivityManagerInternal::startProcess,
                    mAmInternal, activity.processName, activity.info.applicationInfo, knownToBeDead,
                    isTop, hostingType, activity.intent.getComponent());
            mH.sendMessage(m);
            ... ...
```
可以看到`ActivityManagerInternal::startProcess()`将被调用, 在`ActivityTaskManagerService.H()`(其父类`Handler`)中 :
```
// frameworks/base/core/java/android/os/Handler.java
    private static void handleCallback(Message message) {
        message.callback.run();
    }
```
`message.callback.run()`会经过一系列操作调用到`ActivityManagerInternal::startProcess()`:
```
// frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
    @VisibleForTesting
    public final class LocalService extends ActivityManagerInternal
        @Override
        public void startProcess(String processName, ApplicationInfo info, boolean knownToBeDead,
                boolean isTop, String hostingType, ComponentName hostingName) {
            try {
                ... ...
                synchronized (ActivityManagerService.this) {
                    startProcessLocked(processName, info, knownToBeDead, 0 /* intentFlags */,
                            new HostingRecord(hostingType, hostingName, isTop),
                            ZYGOTE_POLICY_FLAG_LATENCY_SENSITIVE, false /* allowWhileBooting */,
                            false /* isolated */);
                }
                .... ...
            }
            ... ...
        }
        ... ...
    }
    @GuardedBy("this")
    final ProcessRecord startProcessLocked(String processName,
            ApplicationInfo info, boolean knownToBeDead, int intentFlags,
            HostingRecord hostingRecord, int zygotePolicyFlags, boolean allowWhileBooting,
            boolean isolated) {
        return mProcessList.startProcessLocked(processName, info, knownToBeDead, intentFlags,
                hostingRecord, zygotePolicyFlags, allowWhileBooting, isolated, 0 /* isolatedUid */,
                null /* ABI override */, null /* entryPoint */,
                null /* entryPointArgs */, null /* crashHandler */);
    }
```
显然`mProcessList`的类型是`ProcessList`:
```
// frameworks/base/services/core/java/com/android/server/am/ProcessList.java
    @GuardedBy("mService")
    ProcessRecord startProcessLocked(String processName, ApplicationInfo info,
            boolean knownToBeDead, int intentFlags, HostingRecord hostingRecord,
            int zygotePolicyFlags, boolean allowWhileBooting, boolean isolated, int isolatedUid,
            String abiOverride, String entryPoint, String[] entryPointArgs, Runnable crashHandler) {
        ... ...
        final boolean success =
                startProcessLocked(app, hostingRecord, zygotePolicyFlags, abiOverride);
        checkSlow(startTime, "startProcess: done starting proc!");
        return success ? app : null;
    }
    @GuardedBy("mService")
    boolean startProcessLocked(ProcessRecord app, HostingRecord hostingRecord,
            int zygotePolicyFlags, String abiOverride) {
        return startProcessLocked(app, hostingRecord, zygotePolicyFlags,
                false /* disableHiddenApiChecks */, false /* disableTestApiChecks */,
                abiOverride);
    }
    @GuardedBy("mService")
    boolean startProcessLocked(ProcessRecord app, HostingRecord hostingRecord,
            int zygotePolicyFlags, boolean disableHiddenApiChecks, boolean disableTestApiChecks,
            String abiOverride) {
        try {
            ... ...
            return startProcessLocked(hostingRecord, entryPoint, app, uid, gids,
                    runtimeFlags, zygotePolicyFlags, mountExternal, seInfo, requiredAbi,
                    instructionSet, invokeWith, startTime);
        } ... ...
    }
    @GuardedBy("mService")
    boolean startProcessLocked(HostingRecord hostingRecord, String entryPoint, ProcessRecord app,
            int uid, int[] gids, int runtimeFlags, int zygotePolicyFlags, int mountExternal,
            String seInfo, String requiredAbi, String instructionSet, String invokeWith,
            long startTime) {
        app.setPendingStart(true);
        ... ...
        if (mService.mConstants.FLAG_PROCESS_START_ASYNC) {
            if (DEBUG_PROCESSES) Slog.i(TAG_PROCESSES,
                    "Posting procStart msg for " + app.toShortString());
            mService.mProcStartHandler.post(() -> handleProcessStart(
                    app, entryPoint, gids, runtimeFlags, zygotePolicyFlags, mountExternal,
                    requiredAbi, instructionSet, invokeWith, startSeq));
            return true;
        } ... ...
    }
    private void handleProcessStart(final ProcessRecord app, final String entryPoint,
            final int[] gids, final int runtimeFlags, int zygotePolicyFlags,
            final int mountExternal, final String requiredAbi, final String instructionSet,
            final String invokeWith, final long startSeq) {
        ... ...
        try {
            final Process.ProcessStartResult startResult = startProcess(app.getHostingRecord(),
                    entryPoint, app, app.getStartUid(), gids, runtimeFlags, zygotePolicyFlags,
                    mountExternal, app.getSeInfo(), requiredAbi, instructionSet, invokeWith,
                    app.getStartTime());
            ... ...
        }
    }
```
`mService.mProcStartHandler.post()`的执行将通过`ActivityManagerService`中的`mProcStartHandler`(类型为`Handler`)执行`handleProcessStart()`, 进一步调用`startProcess()`(注意: 和之前的`startProcess()`方法不一样):
```
// frameworks/base/services/core/java/com/android/server/am/ProcessList.java
    private Process.ProcessStartResult startProcess(HostingRecord hostingRecord, String entryPoint,
            ProcessRecord app, int uid, int[] gids, int runtimeFlags, int zygotePolicyFlags,
            int mountExternal, String seInfo, String requiredAbi, String instructionSet,
            String invokeWith, long startTime) {
        try {
            ... ...
            if (hostingRecord.usesWebviewZygote()) {
                ... ...
            } else if (hostingRecord.usesAppZygote()) {
                ... ...
            } else {
                regularZygote = true;
                startResult = Process.start(entryPoint,
                        app.processName, uid, uid, gids, runtimeFlags, mountExternal,
                        app.info.targetSdkVersion, seInfo, requiredAbi, instructionSet,
                        app.info.dataDir, invokeWith, app.info.packageName, zygotePolicyFlags,
                        isTopApp, app.getDisabledCompatChanges(), pkgDataInfoMap,
                        allowlistedAppDataInfoMap, bindMountAppsData, bindMountAppStorageDirs,
                        new String[]{PROC_START_SEQ_IDENT + app.getStartSeq()});
            }
        } ... ...
    }
```
而`Process.start()`方法:
```
// frameworks/base/core/java/android/os/Process.java
    public static ProcessStartResult start(@NonNull final String processClass,
                                           ... ...
                                           @Nullable String[] zygoteArgs) {
        return ZYGOTE_PROCESS.start(processClass, niceName, uid, gid, gids,
                    runtimeFlags, mountExternal, targetSdkVersion, seInfo,
                    abi, instructionSet, appDataDir, invokeWith, packageName,
                    zygotePolicyFlags, isTopApp, disabledCompatChanges,
                    pkgDataInfoMap, whitelistedDataInfoMap, bindMountAppsData,
                    bindMountAppStorageDirs, zygoteArgs);
    }
```
`ZYGOTE_PROCESS`为`ZygoteProcess`, 因此:
```
// frameworks/base/core/java/android/os/ZygoteProcess.java
    public final Process.ProcessStartResult start(@NonNull final String processClass,
                                                  ... ...
                                                  @Nullable String[] zygoteArgs) {
        ... ...
        try {
            return startViaZygote(processClass, niceName, uid, gid, gids,
                    runtimeFlags, mountExternal, targetSdkVersion, seInfo,
                    abi, instructionSet, appDataDir, invokeWith, /*startChildZygote=*/ false,
                    packageName, zygotePolicyFlags, isTopApp, disabledCompatChanges,
                    pkgDataInfoMap, allowlistedDataInfoList, bindMountAppsData,
                    bindMountAppStorageDirs, zygoteArgs);
        } ... ...
    }
    private Process.ProcessStartResult startViaZygote(@NonNull final String processClass,
                                                      @Nullable final String niceName,
                                                      ... ...
                                                      throws ZygoteStartFailedEx {
        ... ...
        synchronized(mLock) {
            // The USAP pool can not be used if the application will not use the systems graphics
            // driver.  If that driver is requested use the Zygote application start path.
            return zygoteSendArgsAndGetResult(openZygoteSocketIfNeeded(abi),
                                              zygotePolicyFlags,
                                              argsForZygote);
        }
    }
    private Process.ProcessStartResult zygoteSendArgsAndGetResult(
            ZygoteState zygoteState, int zygotePolicyFlags, @NonNull ArrayList<String> args)
            throws ZygoteStartFailedEx {
        ... ...
        return attemptZygoteSendArgsAndGetResult(zygoteState, msgStr);
    }
    private Process.ProcessStartResult attemptZygoteSendArgsAndGetResult(
            ZygoteState zygoteState, String msgStr) throws ZygoteStartFailedEx {
        try {
            final BufferedWriter zygoteWriter = zygoteState.mZygoteOutputWriter;
            final DataInputStream zygoteInputStream = zygoteState.mZygoteInputStream;
            zygoteWriter.write(msgStr);
            zygoteWriter.flush();
            ... ...
            Process.ProcessStartResult result = new Process.ProcessStartResult();
            result.pid = zygoteInputStream.readInt();
            result.usingWrapper = zygoteInputStream.readBoolean();
            ... ...
            return result;
        }... ...
    }
```
`zygoteWriter`的类型为`Writer`, 是`ActivityManagerService`向`zygote64`进程写消息的`Writer`:
```
// libcore/ojluni/src/main/java/java/io/Writer.java
    public void write(String str) throws IOException {
        write(str, 0, str.length());
    }
```
该`Writer`的子类实现为`BufferedWriter`:
```
// libcore/ojluni/src/main/java/java/io/BufferedWriter.java
    public void write(String s, int off, int len) throws IOException {
        synchronized (lock) {
            ensureOpen();
            int b = off, t = off + len;
            while (b < t) {
                ... ...
                if (nextChar >= nChars)
                    flushBuffer();
            }
        }
    }
    void flushBuffer() throws IOException {
        synchronized (lock) {
            ensureOpen();
            if (nextChar == 0)
                return;
            out.write(cb, 0, nextChar);
            nextChar = 0;
        }
    }
```
此处的`out`类型是也是`Writer`不过实现是`OutputStreamWriter`, 而`OutputStreamWriter`最终是通过`OutputStream`完成从SOCKET的发送, 而该`OutputStream`的实现是`SocketOutputStream`, 可以看出`ActivityManagerService`通过 **SOCKET** 向`zygote64`进程发送消息.
那么此处的 **SOCKET** 具体是哪个呢? 是: "**`zygote`**", 对应的设备节点为: **`/dev/socket/zygote`**

## Zygote64 中接收`ActivityManagerService`的消息

Zygote64启动是会构造`ZygoteServer`, 其构造方法中:
```
// frameworks/base/core/java/com/android/internal/os/ZygoteServer.java
    ZygoteServer(boolean isPrimaryZygote) {
        mUsapPoolEventFD = Zygote.getUsapPoolEventFD();

        if (isPrimaryZygote) {
            mZygoteSocket = Zygote.createManagedSocketFromInitSocket(Zygote.PRIMARY_SOCKET_NAME);
            mUsapPoolSocket =
                    Zygote.createManagedSocketFromInitSocket(
                            Zygote.USAP_POOL_PRIMARY_SOCKET_NAME);
        } else ...
        ... ...
    }
```
`PRIMARY_SOCKET_NAME`正式名为 **`zygote`** 的 **SOCKET**.

在如下代码:
```
// frameworks/base/core/java/com/android/internal/os/ZygoteServer.java
    Runnable runSelectLoop(String abiList) {
        ... ...
        socketFDs.add(mZygoteSocket.getFileDescriptor());
        peers.add(null);
        ... ...
        while (true) {
            ... ...
            if (pollReturnValue == 0) {
                ... ...
            } else {
                boolean usapPoolFDRead = false;

                while (--pollIndex >= 0) {
                    if ((pollFDs[pollIndex].revents & POLLIN) == 0) {
                        continue;
                    }

                    if (pollIndex == 0) {
                        // Zygote server socket
                        ZygoteConnection newPeer = acceptCommandPeer(abiList);
                        peers.add(newPeer);
                        socketFDs.add(newPeer.getFileDescriptor());
                    } else if (pollIndex < usapPoolEventFDIndex) {
                        // Session socket accepted from the Zygote server socket

                        try {
                            ZygoteConnection connection = peers.get(pollIndex);
                            boolean multipleForksOK = !isUsapPoolEnabled()
                                    && ZygoteHooks.isIndefiniteThreadSuspensionSafe();
                            final Runnable command =
                                    connection.processCommand(this, multipleForksOK);
                            ... ...
                        }
                        ... ...
                    } else ... ...
                    ... ...
                }
            }
        }
    }
```
`acceptCommandPeer()`负责接受从`ActivityManagerService`的连接, 并创建`ZygoteConnection`, 然后分别对每个`ZygoteConnection`进行处理, 其处理函数:
```
// frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java
    Runnable processCommand(ZygoteServer zygoteServer, boolean multipleOK) {
        ZygoteArguments parsedArgs;

        try (ZygoteCommandBuffer argBuffer = new ZygoteCommandBuffer(mSocket)) {
            while (true) {
                ... ...
                if (parsedArgs.mInvokeWith != null || parsedArgs.mStartChildZygote
                        || !multipleOK || peer.getUid() != Process.SYSTEM_UID) {
                    ... ...
                } else {
                    ZygoteHooks.preFork();
                    Runnable result = Zygote.forkSimpleApps(argBuffer,
                            zygoteServer.getZygoteSocketFileDescriptor(),
                            peer.getUid(), Zygote.minChildUid(peer), parsedArgs.mNiceName);
                    ... ...
                }
            }
        }
        ... ...
    }
```
而对于`Zygote.forkSimpleApps()`方法:
```
// frameworks/base/core/java/com/android/internal/os/Zygote.java
    static @Nullable Runnable forkSimpleApps(@NonNull ZygoteCommandBuffer argBuffer,
                                             @NonNull FileDescriptor zygoteSocket,
                                             int expectedUid,
                                             int minUid,
                                             @Nullable String firstNiceName) {
        boolean in_child =
                argBuffer.forkRepeatedly(zygoteSocket, expectedUid, minUid, firstNiceName);
        if (in_child) {
            return childMain(argBuffer, /*usapPoolSocket=*/null, /*writePipe=*/null);
        } else {
            return null;
        }
    }
```
`argBuffer.forkRepeatedly()`完成`fork()`操作, 根据其返回结果判定要执行的操作, 如果是子进程则继续执行`childMain()`, 否则则返回. 查看`argBuffer.forkRepeatedly()`源码:
```
// frameworks/base/core/java/com/android/internal/os/ZygoteCommandBuffer.java
    boolean forkRepeatedly(FileDescriptor zygoteSocket, int expectedUid, int minUid,
                       String firstNiceName) {
        try {
            return nativeForkRepeatedly(mNativeBuffer, zygoteSocket.getInt$(),
                    expectedUid, minUid, firstNiceName);
        }... ...
    }
```
`nativeForkRepeatedly()`是个Native方法, 其定义:
```
// frameworks/base/core/jni/com_android_internal_os_ZygoteCommandBuffer.cpp
jboolean com_android_internal_os_ZygoteCommandBuffer_nativeForkRepeatedly(
            JNIEnv* env,
            jclass,
            jlong j_buffer,
            jint zygote_socket_fd,
            jint expected_uid,
            jint minUid,
            jstring managed_nice_name) {
    do {
        if (credentials.uid != expected_uid) {
        return JNI_FALSE;
    }
    n_buffer->readAllLines(first_time ? fail_fn_1 : fail_fn_n);
    n_buffer->reset();
    int pid = zygote::forkApp(env, /* no pipe FDs */ -1, -1, session_socket_fds,
                              /*args_known=*/ true, /*is_priority_fork=*/ true,
                              /*purge=*/ first_time);
    ... ...
}
```
而`zygote::forkApp()`代码为:
```
// frameworks/base/core/jni/com_android_internal_os_Zygote.cpp
int zygote::forkApp(JNIEnv* env,
                    int read_pipe_fd,
                    int write_pipe_fd,
                    const std::vector<int>& session_socket_fds,
                    bool args_known,
                    bool is_priority_fork,
                    bool purge) {
    ... ...
    return zygote::ForkCommon(env, /* is_system_server= */ false, fds_to_close,
                            fds_to_ignore, is_priority_fork == JNI_TRUE, purge);
}

// Utility routine to fork a process from the zygote.
pid_t zygote::ForkCommon(JNIEnv* env, bool is_system_server,
                         const std::vector<int>& fds_to_close,
                         const std::vector<int>& fds_to_ignore,
                         bool is_priority_fork,
                         bool purge) {
    ... ...
    pid_t pid = fork();
    if (pid == 0) {
        if (is_priority_fork) {
            setpriority(PRIO_PROCESS, 0, PROCESS_PRIORITY_MAX);
        } else {
            setpriority(PRIO_PROCESS, 0, PROCESS_PRIORITY_MIN);
        }
        // The child process.
        PreApplicationInit();
        // Clean up any descriptors which must be closed immediately
        DetachDescriptors(env, fds_to_close, fail_fn);
        // Invalidate the entries in the USAP table.
        ClearUsapTable();
        // Re-open all remaining open file descriptors so that they aren't shared
        // with the zygote across a fork.
        gOpenFdTable->ReopenOrDetach(fail_fn);
        // Turn fdsan back on.
        android_fdsan_set_error_level(fdsan_error_level);
        // Reset the fd to the unsolicited zygote socket
        gSystemServerSocketFd = -1;
    } else {
        ALOGD("Forked child process %d", pid);
    }
    ... ...
}
```

至此Zygote64完成`fork()`, 回到函数`Zygote.forkSimpleApps()`:
```
// frameworks/base/core/java/com/android/internal/os/Zygote.java
    static @Nullable Runnable forkSimpleApps(@NonNull ZygoteCommandBuffer argBuffer,
                                             @NonNull FileDescriptor zygoteSocket,
                                             int expectedUid,
                                             int minUid,
                                             @Nullable String firstNiceName) {
        boolean in_child =
                argBuffer.forkRepeatedly(zygoteSocket, expectedUid, minUid, firstNiceName);
        if (in_child) {
            return childMain(argBuffer, /*usapPoolSocket=*/null, /*writePipe=*/null);
        } else {
            return null;
        }
    }

    private static Runnable childMain(@Nullable ZygoteCommandBuffer argBuffer,
                                      @Nullable LocalServerSocket usapPoolSocket,
                                      FileDescriptor writePipe) {
        ... ...
        try {
            ... ...
            specializeAppProcess(args.mUid, args.mGid, args.mGids,
                                 args.mRuntimeFlags, rlimits, args.mMountExternal,
                                 args.mSeInfo, args.mNiceName, args.mStartChildZygote,
                                 args.mInstructionSet, args.mAppDataDir, args.mIsTopApp,
                                 args.mPkgDataInfoList, args.mAllowlistedDataInfoList,
                                 args.mBindMountAppDataDirs, args.mBindMountAppStorageDirs);
            ... ...
            return ZygoteInit.zygoteInit(args.mTargetSdkVersion,
                                         args.mDisabledCompatChanges,
                                         args.mRemainingArgs,
                                         null /* classLoader */);
        } ... ...
    }
```
对于`childMain()`方法, 其通过`ZygoteInit.zygoteInit()`初始化App的运行时:
```
// frameworks/base/core/java/com/android/internal/os/ZygoteInit.java
    public static Runnable zygoteInit(int targetSdkVersion, long[] disabledCompatChanges,
            String[] argv, ClassLoader classLoader) {
        ... ...
        RuntimeInit.redirectLogStreams();
        RuntimeInit.commonInit();
        ZygoteInit.nativeZygoteInit();
        return RuntimeInit.applicationInit(targetSdkVersion, disabledCompatChanges, argv,
                classLoader);
    }

    protected static Runnable applicationInit(int targetSdkVersion, long[] disabledCompatChanges,
            String[] argv, ClassLoader classLoader) {
        // If the application calls System.exit(), terminate the process
        // immediately without running any shutdown hooks.  It is not possible to
        // shutdown an Android application gracefully.  Among other things, the
        // Android runtime shutdown hooks close the Binder driver, which can cause
        // leftover running threads to crash before the process actually exits.
        ... ...
        // Remaining arguments are passed to the start class's static main
        return findStaticMain(args.startClass, args.startArgs, classLoader);
    }
```

App自身的启动后续再分析...