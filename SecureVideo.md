# `MediaPlayer.prepareDrm()`
```
// frameworks/base/media/java/android/media/MediaPlayer.java
    public void prepareDrm(@NonNull UUID uuid)
            throws UnsupportedSchemeException, ResourceBusyException,
                   ProvisioningNetworkErrorException, ProvisioningServerErrorException
    {
        ...
        synchronized (mDrmLock) {
            mDrmConfigAllowed = false;
            boolean earlyExit = false;

            try {
                prepareDrm_openSessionStep(uuid);
                ...

    private void prepareDrm_openSessionStep(@NonNull UUID uuid)
            throws NotProvisionedException, ResourceBusyException {
        try {
            mDrmSessionId = mDrmObj.openSession();
            ...
            _prepareDrm(getByteArrayFromUUID(uuid), mDrmSessionId);
            ...

    private native void _prepareDrm(@NonNull byte[] uuid, @NonNull byte[] drmSessionId);

// frameworks/base/media/jni/android_media_MediaPlayer.cpp
static void android_media_MediaPlayer_prepareDrm(JNIEnv *env, jobject thiz,
                    jbyteArray uuidObj, jbyteArray drmSessionIdObj)
{
    ...
    status_t err = mp->prepareDrm(uuid.array(), drmSessionId);
    ...

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDriver.cpp
status_t NuPlayerDriver::prepareDrm(const uint8_t uuid[16], const Vector<uint8_t> &drmSessionId)
{
    ...
    status_t ret = mPlayer->prepareDrm(uuid, drmSessionId);
    ...
}

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
status_t NuPlayer::prepareDrm(const uint8_t uuid[16], const Vector<uint8_t> &drmSessionId)
{
    ...
    sp<AMessage> msg = new AMessage(kWhatPrepareDrm, this);
    ...

void NuPlayer::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        ...
        case kWhatPrepareDrm:
        {
            status_t status = onPrepareDrm(msg);
            sp<AMessage> response = new AMessage;
            response->setInt32("status", status);
            sp<AReplyToken> replyID;
            CHECK(msg->senderAwaitsResponse(&replyID));
            response->postReply(replyID);
            break;
        }
        ...

status_t NuPlayer::onPrepareDrm(const sp<AMessage> &msg)
{
    ...
    mCrypto = crypto;
    mIsDrmProtected = true;
```

# 
在`NuPlayer::instantiateDecoder()`中:
```
// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayer.cpp
status_t NuPlayer::instantiateDecoder(
        bool audio, sp<DecoderBase> *decoder, bool checkAudioModeChange) {
    ...
    sp<AMessage> format = mSource->getFormat(audio);
    ...
    // Modular DRM
    if (mIsDrmProtected) {
        format->setPointer("crypto", mCrypto.get());
        ALOGV("instantiateDecoder: mCrypto: %p (%d) isSecure: %d", mCrypto.get(),
                (mCrypto != NULL ? mCrypto->getStrongCount() : 0),
                (mSourceFlags & Source::FLAG_SECURE) != 0);
    }
    (*decoder)->configure(format);
    ...

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoderBase.cpp
void NuPlayer::DecoderBase::configure(const sp<AMessage> &format) {
    sp<AMessage> msg = new AMessage(kWhatConfigure, this);
    msg->setMessage("format", format);
    msg->post();
}

void NuPlayer::DecoderBase::onMessageReceived(const sp<AMessage> &msg) {

    switch (msg->what()) {
        case kWhatConfigure:
        {
            sp<AMessage> format;
            CHECK(msg->findMessage("format", &format));
            onConfigure(format);
            break;
        }
        ...

// frameworks/av/media/libmediaplayerservice/nuplayer/NuPlayerDecoder.cpp
void NuPlayer::Decoder::onConfigure(const sp<AMessage> &format) {
    ... ...
    // Modular DRM
    void *pCrypto;
    if (!format->findPointer("crypto", &pCrypto)) {
        pCrypto = NULL;
    }
    sp<ICrypto> crypto = (ICrypto*)pCrypto;
    // non-encrypted source won't have a crypto
    mIsEncrypted = (crypto != NULL);
    // configure is called once; still using OR in case the behavior changes.
    mIsEncryptedObservedEarlier = mIsEncryptedObservedEarlier || mIsEncrypted;
    err = mCodec->configure(
            format, mSurface, crypto, 0 /* flags */);

// frameworks/av/media/libstagefright/MediaCodec.cpp
status_t MediaCodec::configure(
        const sp<AMessage> &format,
        const sp<Surface> &surface,
        const sp<ICrypto> &crypto,
        const sp<IDescrambler> &descrambler,
        uint32_t flags) {
    sp<AMessage> msg = new AMessage(kWhatConfigure, this);
    ...
    if (crypto != NULL || descrambler != NULL) {
        if (crypto != NULL) {
            msg->setPointer("crypto", crypto.get());
        } else {
            msg->setPointer("descrambler", descrambler.get());
        }
        if (mMetricsHandle != 0) {
            mediametrics_setInt32(mMetricsHandle, kCodecCrypto, 1);
        }
    } else if (mFlags & kFlagIsSecure) {
        ALOGW("Crypto or descrambler should be given for secure codec");
    }
    ...

void MediaCodec::onMessageReceived(const sp<AMessage> &msg) {
    switch (msg->what()) {
        case kWhatCodecNotify:
        ...
        case kWhatConfigure:
        {
            ...
            ALOGV("kWhatConfigure: Old mCrypto: %p (%d)",
                    mCrypto.get(), (mCrypto != NULL ? mCrypto->getStrongCount() : 0));
            mCrypto = static_cast<ICrypto *>(crypto);
            mBufferChannel->setCrypto(mCrypto);
            ALOGV("kWhatConfigure: New mCrypto: %p (%d)",
                    mCrypto.get(), (mCrypto != NULL ? mCrypto->getStrongCount() : 0));
            void *descrambler;
            if (!msg->findPointer("descrambler", &descrambler)) {
                descrambler = NULL;
            }
            mDescrambler = static_cast<IDescrambler *>(descrambler);
            mBufferChannel->setDescrambler(mDescrambler);
            ...
            mCodec->initiateConfigureComponent(format);
            break;
        }

// frameworks/av/media/codec2/sfplugin/CCodecBufferChannel.cpp
void CCodecBufferChannel::setCrypto(const sp<ICrypto> &crypto) {
    if (mCrypto != nullptr) {
        for (std::pair<wp<HidlMemory>, int32_t> entry : mHeapSeqNumMap) {
            mCrypto->unsetHeap(entry.second);
        }
        mHeapSeqNumMap.clear();
        if (mHeapSeqNum >= 0) {
            mCrypto->unsetHeap(mHeapSeqNum);
            mHeapSeqNum = -1;
        }
    }
    mCrypto = crypto;
}
```

# 
```
// frameworks/av/media/libstagefright/MediaCodec.cpp
status_t MediaCodec::onQueueInputBuffer(const sp<AMessage> &msg) {
    ...
    status_t err = OK;
    if (hasCryptoOrDescrambler() && !c2Buffer && !memory) {
        ... ...
        err = mBufferChannel->queueSecureInputBuffer(
                buffer,
                (mFlags & kFlagIsSecure),
                key,
                iv,
                mode,
                pattern,
                subSamples,
                numSubSamples,
                errorDetailMsg);
        ...
    } else ...

// frameworks/av/media/codec2/sfplugin/CCodecBufferChannel.cpp
status_t CCodecBufferChannel::queueSecureInputBuffer(
        const sp<MediaCodecBuffer> &buffer, bool secure, const uint8_t *key,
        const uint8_t *iv, CryptoPlugin::Mode mode, CryptoPlugin::Pattern pattern,
        const CryptoPlugin::SubSample *subSamples, size_t numSubSamples,
        AString *errorDetailMsg) {
    ...
    if (numSubSamples == 1
            && subSamples[0].mNumBytesOfClearData == 0
            && subSamples[0].mNumBytesOfEncryptedData == 0) {
        ...
    } else if (mCrypto != nullptr) {
        ...
        result = mCrypto->decrypt(
                key, iv, mode, pattern, source, buffer->offset(),
                subSamples, numSubSamples, destination, errorDetailMsg);
        ...
        if (destination.type == DrmBufferType::SHARED_MEMORY) {
            encryptedBuffer->copyDecryptedContent(mDecryptDestination, result);
        }
    } else ...
```