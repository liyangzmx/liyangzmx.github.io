# camera 闪光灯

## SystemUI打开闪光灯
点击闪光灯控制按钮时, `QSTileViewImpl`的`onClick()`被调用, 然后通过其`click()`方法发从了一个`CLICK`的异步消息. 上述消息被`QSTileImpl.H.handleMessage()`响应该消息, 进一步调用`FlashlightTile`(`QSTileImpl`的子类)的`handleClick()`方法响应消息. 然后调用`FlashlightController`子类`FlashlightControllerImpl`的`setFlashlight()`方法进一步处理, 最终`CameraManager.setTorchMode()`被调到, 进一步`CameraManagerGlobal.setTorchMode()`就是通过`android.hardware.ICameraService.setTorchMode()`接口调用到`cameraserver`

## `cameraserver`向HAL层`ICameraDevice`请求控制闪光灯
`cameraserver`通过`CameraService::setTorchMode()`响应客户端的闪光灯控制请求, 第一个参数是相机对应的`id`, 这里测试机的后摄`id`是`"0"`, 第二个参数是模式, 这里我们打开是`true`, 关闭是`false`, 第三个参数是应用的`IBinder`, 会被保存到`CameraService`的`mTorchClientMap`中. `Cameraserver`通过`ProviderFlashControl::setTorchMode()`执行对闪光灯的控制, 此时参数只有两个. `ProviderFlashControl`通过`CameraProviderManager::setTorchMode()`继续控制.

首先通过`CameraProviderManager::findDeviceInfoLocked()`从相机的`id`得到一个`DeviceInfo`, 然后通过`DeviceInfo::mParentProvider.promote()`得到提供器:`ProviderInfo`, 该类记录了`ICameraProvider`接口, 通过`ProviderInfo::startProviderInterface()`获得, 然后保存到`CameraProviderManager`的`mTorchProviderByCameraId`, 但是最终还是调用了`DeviceInfo::setTorchMode()`来处理请求. 此时`DeviceInfo`的实现是`DeviceInfo3`.

`DeviceInfo3::setTorchMode()`调用自身的`setTorchModeForDevice()`方法进一步设置, 该过程首先需要获取`device::V3_2::ICameraDevice`接口, 通过`startDeviceInterface()`完成, 其大体流程:
* 首先检查`mSavedInterface`, 如果有值直接返回
* 如果`mSavedInterface`为空, 从`mParentProvider`(类型`ProviderInfo`)的`startDeviceInterface()`获取, 而`ProviderInfo`首先通过`startProviderInterface()`检查其`mActiveInterface`接口(类型为`ICameraProvider`), 如果空则首先获取`ICameraProvider`接口并保存, 然后返回
* 然后通过接口`ICameraProvider::getCameraDeviceInterface_V3_x()`获取`device::V3_2::ICameraDevice`接口, 然后返回

另外多说一点, 如果`"ro.camera.enableLazyHal"`为`true`则才会有上述负责的流程, 否则`DeviceInfo3`的`mSavedInterface`值不会为空, 该设置为`false`可能降低Android的启动速度.

`device::V3_2::ICameraDevice`获取后, 调用`device::V3_2::ICameraDevice::setTorchMode()`接口设置闪光灯状态.

## HAL层`ICameraDevice`通知`cameraserver`闪光灯事件
HAL层(`device::V3_2::ICameraDevice`)通过`hardware::camera::provider::V2_6::ICameraProviderCallback`通知`ProviderInfo`(继承自`ICameraProviderCallback`)事件, 接口是`torchModeStatusChange()`, 而`ameraProviderManager::ProviderInfo::torchModeStatusChange()`重写了该接口, `ProviderInfo`通知`mManager`(类型为`CameraProviderManager`)的`mListener`(类型为`CameraProviderManager::StatusListener`, 其子类为`CameraService`), 因此`CameraService::onTorchStatusChanged()`将被调用, 该方法将通知所有的监听者(接口是``), 而客户端的`CameraManagerGlobal`正是继承了此接口. 