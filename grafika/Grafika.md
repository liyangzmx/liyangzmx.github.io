# PlayMovieActivity
## `onCreate()`
`onCreate()`:
```
// src/main/java/com/android/grafika/PlayMovieActivity.java
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_play_movie);
        mTextureView = (TextureView) findViewById(R.id.movie_texture_view);
        mTextureView.setSurfaceTextureListener(this);
        ... ...
        updateControls();
    }

    private void updateControls() {
        Button play = (Button) findViewById(R.id.play_stop_button);
        if (mShowStopLabel) {
            play.setText(R.string.stop_button_text);
        } else {
            play.setText(R.string.play_button_text);
        }
        play.setEnabled(mSurfaceTextureReady);
        .. ...
    }
```
`setSurfaceTextureListener()`向`TextureView`注册了回调`TextureView.SurfaceTextureListener`, 即`PlayMovieActivity`自己. `updateControls()`更新了播放按钮的状态, 此时`TextureView`未准备好.

## `onSurfaceTextureAvailable()`
`TextureView`准备好时会回调`PlayMovieActivity`的`onSurfaceTextureAvailable()`:
```
// src/main/java/com/android/grafika/PlayMovieActivity.java
    @Override
    public void onSurfaceTextureAvailable(SurfaceTexture st, int width, int height) {
        ... ...
        mSurfaceTextureReady = true;
        updateControls();
    }
```
`mSurfaceTextureReady`的值设置为`true`, 因此在`updateControls()`中, 播放按钮有效, 并设置其`text`属性为"Play":

## `clickPlayStop()`
在文件`src/main/res/layout/activity_play_movie.xml`中, 对于播放按钮:
```
// src/main/res/layout/activity_play_movie.xml
    <Button
        android:id="@+id/play_stop_button"
        style="?android:attr/buttonStyleSmall"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_alignParentTop="true"
        android:text="@string/play_button_text"
        android:onClick="clickPlayStop" />
```
播放按钮点击时对应`PlayMovieActivity`的`clickPlayStop()`方法:
```
// src/main/java/com/android/grafika/PlayMovieActivity.java
    public void clickPlayStop(@SuppressWarnings("unused") View unused) {
        if (mShowStopLabel) {
            ... ...
        } else {
            ... ...
            SurfaceTexture st = mTextureView.getSurfaceTexture();
            Surface surface = new Surface(st);
            ... ...
            try {
                 player = new MoviePlayer(
                        new File(getFilesDir(), mMovieFiles[mSelectedMovie]), surface, callback);
            }
            adjustAspectRatio(player.getVideoWidth(), player.getVideoHeight());
            ... ...
            mPlayTask = new MoviePlayer.PlayTask(player, this);
            ... ...
            updateControls();
            mPlayTask.execute();
```
从`TextureView`获取`SurfaceTexture`, 使用`SurfaceTexture`创建一个`Surface`. 构造`MoviePlayer`并将刚才的`Surface`设置给`MoviePlayer`, `MoviePlayer`构造时会创建`MediaExtractor`, 并进行配置和访问, 这是因为`PlayMovieActivity`执行`adjustAspectRatio()`时, 可以在未开始播放前, 提前得知回放内容的宽高, 以便于设置好`TextureView`的`Transform(Matrix)`. 最后创建`MoviePlayer.PlayTask`, 调用`updateControls()`更新按钮状态后`mPlayTask.execute()`启动回放线程.

## `PlayTask.execute()`
`PlayTask`的`execute()`启动内部线程`Thread`, `Thread`将调用`PlayTask`(类型为`Runnable`)的`run()`方法:
```
// src/main/java/com/android/grafika/MoviePlayer.java
public class MoviePlayer {
    public static class PlayTask implements Runnable {
        ... ...
        @Override
        public void run() {
            try {
                mPlayer.play();
            } ... ...
        }

    public void play() throws IOException {
        try {
            extractor = new MediaExtractor();
            extractor.setDataSource(mSourceFile.toString());
            int trackIndex = selectTrack(extractor);
            ... ...
            extractor.selectTrack(trackIndex);
            MediaFormat format = extractor.getTrackFormat(trackIndex);
            String mime = format.getString(MediaFormat.KEY_MIME);
            decoder = MediaCodec.createDecoderByType(mime);
            decoder.configure(format, mOutputSurface, null, 0);
            decoder.start();
            doExtract(extractor, trackIndex, decoder, mFrameCallback);
        }
        ... ...
    }
```
再次创建`MediaExtractor`, 和此前的目的不一样. `setDataSource`后, 获取`MediaExtractor`中的`MediaFormat`, 提取`video`的`KEY_MIME`信息, 用于后续`MediaCodec`的创建. 调用`MediaCodec.createDecoderByType()`创建`MediaCodec`, 对`MediaCodec`进行`configure()`, 将上文通过`SurfaceTexture`创建的`Surface`配置给`MediaCodec`, 然后启动`MediaCodec`.

## `doExtract()`
`doExtract()`主要负责从`MediaExtractor`中获取数据, 并写入给`MediaCodec`:
```
// src/main/java/com/android/grafika/MoviePlayer.java
    private void doExtract(MediaExtractor extractor, int trackIndex, MediaCodec decoder,
            FrameCallback frameCallback) {
        ... ...
        ByteBuffer[] decoderInputBuffers = decoder.getInputBuffers();
        ... ...
        while (!outputDone) {
            ... ...
            if (!inputDone) {
```