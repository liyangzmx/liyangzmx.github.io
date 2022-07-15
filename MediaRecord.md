## 相机的初始化
```
android::BnMediaRecorder::onTransact()
    android::MediaRecorderClient::start()
        android::StagefrightRecorder::start()
            android::StagefrightRecorder::prepareInternal()
                android::StagefrightRecorder::setupMPEG4orWEBMRecording()
                    android::StagefrightRecorder::setupVideoEncoder()
                        android::MediaCodecSource::Create()
                            android::MediaCodecSource::MediaCodecSource()
                                MediaCodecSource::Puller::Puller()
                            android::MediaCodecSource::init()
                                android::MediaCodecSource::initEncoder()
                                    mEncoder = android::MediaCodec::CreateByComponentName()
                                        android::MediaCodec::MediaCodec()
                                    mEncoderActivityNotify = new AMessage(kWhatEncoderActivity, mReflector)
                                    mEncoder->setCallback(mEncoderActivityNotify)
                    android::MPEG4Writer::MPEG4Writer()
                    setupMediaSource(&mediaSource)
                    MPEG4Writer::addSource()
                        MPEG4Writer::Track::Track()
                            mSource = <MediaCodecSource>
            android::MPEG4Writer::start()
                android::MPEG4Writer::startTracks()
                    android::MPEG4Writer::Track::start()
                        android::MediaCodecSource::start() -->
                            [kWhatStart]android::MediaCodecSource::Puller::onMessageReceived()
                                android::CameraSource::start()
                                    android::CameraSource::startCameraRecording()
                                        android::CameraSource::initBufferQueue()
                                            sp<IGraphicBufferProducer> producer
                                            BufferQueue::createBufferQueue(&producer, &consumer)
                                            mVideoBufferConsumer = new BufferItemConsumer(consumer, usage, bufferCount)
                                            mVideoBufferProducer = producer
                                            mCamera->setVideoTarget(mVideoBufferProducer)
                                                android::Camera::setVideoTarget()
                                                    android::hardware::BpCamera::setVideoTarget()
                                            BufferQueueListener(mVideoBufferConsumer, this)
                                            mBufferQueueListener->run()
```

<- GraphicBufferProducer ->

## 相机返回数据
```
android::BnGraphicBufferProducer::onTransact()
    android::BufferQueueProducer::queueBuffer()
        android::BufferQueue::ProxyConsumerListener::onFrameAvailable()
            android::ConsumerBase::onFrameAvailable()
                android::CameraSource::BufferQueueListener::onFrameAvailable()
                    android::CameraSource::BufferQueueListener::onFrameAvailable()
                        mFrameAvailableSignal.signal()
```

<- mFrameAvailableSignal ->

## 数据的提取
```
CameraSource::BufferQueueListener::threadLoop()
    while (!mFrameAvailable)
        mFrameAvailableSignal.waitRelative()
    while (mConsumer->acquireBuffer(&buffer, 0)
        mCameraSource->processBufferQueueFrame(buffer)
            CameraSource::processBufferQueueFrame()
                ...
                mFrameAvailableCondition.signal()
```

<- mFrameAvailableCondition ->

## 数据的读取
```
android::MediaCodecSource::Puller::onMessageReceived()
    android::MediaCodecSource::Puller::schedulePull() -->
        [kWhatPull]android::MediaCodecSource::Puller::onMessageReceived()
            android::CameraSource::read()
                while (mStarted && !mEos && mFramesReceived.empty())
                    mFrameAvailableCondition.waitRelative()
            queue->pushBuffer()
                android::MediaCodecSource::Puller::Queue::pushBuffer()
                    mReadBuffers.push_back(mbuf)
            AMessage::post(kWhatPullerNotify) -->
                android::MediaCodecSource::onMessageReceived()
                    android::MediaCodecSource::feedEncoderInputBuffers()
                        while (!mAvailEncoderInputIndices.empty() && mPuller->readBuffer(&mbuf))
                            android::MediaCodecSource::Puller::readBuffer()
                                queue->readBuffer(mbuf)
                                    android::MediaCodecSource::Puller::Queue::readBuffer()
                                        *mbuf = *mReadBuffers.begin()
                                        mReadBuffers.erase(mReadBuffers.begin())
                            mEncoder->getInputBuffer(bufferIndex, &inbuf)
                                [kWhatQueueInputBuffer]android::MediaCodec::onMessageReceived()
                                    android::MediaCodec::onQueueInputBuffer()
                                        android::CCodecBufferChannel::queueInputBuffer()
                                            android::CCodecBufferChannel::queueInputBufferInternal()
                                                android::Codec2Client::Component::queue()
                                                    android::hardware::media::c2::V1_2::BpHwComponent::queue()
                            mEncoder->queueInputBuffer()
            AMessage::post(kWhatPull)
```

<- Component ->

## 编码后的回调
```
android::hardware::media::c2::V1_0::BnHwComponentListener::_hidl_onWorkDone()
    android::Codec2Client::Component::HidlListener::onWorkDone()
        android::CCodec::ClientListener::onWorkDone()
            android::CCodec::onWorkDone()
                [kWhatWorkDone]android::CCodec::onMessageReceived()
                    android::CCodecBufferChannel::onWorkDone()
                        android::CCodecBufferChannel::handleWork()
                            ::BufferCallback::onOutputBufferAvailable()
                                [kWhatDrainThisBuffer]android::MediaCodec::onMessageReceived()
                                    android::MediaCodec::onOutputBufferAvailable()
                                        [kWhatEncoderActivity]MediaCodecSource::onMessageReceived()
                                            output->mCond.signal()
```

<- mCond ->

## 编码后数据的存储
```
android::MPEG4Writer::Track::threadEntry()
    android::MediaCodecSource::read()
        while (output->mBufferQueue.size() == 0 && !output->mEncoderReachedEOS)
            output.waitForCondition(output->mCond)
        *buffer = *output->mBufferQueue.begin()
        output->mBufferQueue.erase(output->mBufferQueue.begin())
```