- [`MediaPlayer`的创建与配置](#mediaplayer的创建与配置)
  - [`mMediaPlayer.setOnPreparedListener()`](#mmediaplayersetonpreparedlistener)

# `MediaPlayer`的创建与配置
`VideoView.openVideo()`

用户头一次在相册中点击视频时`MovieActivity`被创建, 因此:
```
// packages/apps/Gallery2/src/com/android/gallery3d/app/MovieActivity.java
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ... ...
        mPlayer = new MoviePlayer(rootView, this, intent.getData(), savedInstanceState,
                !mFinishOnCompletion) {
            @Override
            public void onCompletion() {
                if (mFinishOnCompletion) {
                    finish();
                }
            }
        };
```
`MoviePlayer`被构造:
```
// packages/apps/Gallery2/src/com/android/gallery3d/app/MoviePlayer.java
    public MoviePlayer(View rootView, final MovieActivity movieActivity,
            Uri videoUri, Bundle savedInstance, boolean canReplay) {
        mContext = movieActivity.getApplicationContext();
        mRootView = rootView;
        mVideoView = (VideoView) rootView.findViewById(R.id.surface_view);
        ... ...
        mVideoView.setOnErrorListener(this);
        mVideoView.setOnCompletionListener(this);
        mVideoView.setVideoURI(mUri);
        ... ...
    }
```

`mVideoView`为上文提到的`VideoView`, 通过其`setVideoURI()`设置要播放的文件路径:
```
// frameworks/base/core/java/android/widget/VideoView.java
    public void setVideoURI(Uri uri) {
        setVideoURI(uri, null);
    }
    public void setVideoURI(Uri uri, Map<String, String> headers) {
        mUri = uri;
        mHeaders = headers;
        mSeekWhenPrepared = 0;
        openVideo();
        requestLayout();
        invalidate();
    }
```

根据上文代码`openVideo()`被调用:
```
// frameworks/base/core/java/android/widget/VideoView.java
    private void openVideo() {
        ... ...
        try {
            ... ...
            mMediaPlayer = new MediaPlayer();
            ... ...
            mMediaPlayer.setOnPreparedListener(mPreparedListener);
            mMediaPlayer.setOnVideoSizeChangedListener(mSizeChangedListener);
            mMediaPlayer.setOnCompletionListener(mCompletionListener);
            mMediaPlayer.setOnErrorListener(mErrorListener);
            mMediaPlayer.setOnInfoListener(mInfoListener);
            mMediaPlayer.setOnBufferingUpdateListener(mBufferingUpdateListener);
            mCurrentBufferPercentage = 0;
            mMediaPlayer.setDataSource(mContext, mUri, mHeaders);
            mMediaPlayer.setDisplay(mSurfaceHolder);
            mMediaPlayer.setAudioAttributes(mAudioAttributes);
            mMediaPlayer.setScreenOnWhilePlaying(true);
            mMediaPlayer.prepareAsync();
            ... ...
            for (Pair<InputStream, MediaFormat> pending: mPendingSubtitleTracks) {
                try {
                    mMediaPlayer.addSubtitleSource(pending.first, pending.second);
                    ... ...
            mCurrentState = STATE_PREPARING;
            attachMediaController();
            ... ...
```

## `mMediaPlayer.setOnPreparedListener()`
```
// frameworks/base/media/java/android/media/MediaPlayer.java
    public void setOnPreparedListener(OnPreparedListener listener)
    {
        mOnPreparedListener = listener;
    }
```
应用设置了`OnPreparedListener`到`MediaPlayer`中, 改监听要等到`MediaPlayer.prepareAsync()`执行完成才会被调用, 后问会讲到.