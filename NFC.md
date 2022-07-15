- [Android NFC](#android-nfc)
  - [基础](#基础)
  - [NFC的启用](#nfc的启用)
  - [NFC R/W模式监听的启用](#nfc-rw模式监听的启用)
  - [NFC R/W模式操作的底层初始化](#nfc-rw模式操作的底层初始化)
  - [NFC R/W模式对设备的发现](#nfc-rw模式对设备的发现)
  - [NFC R/W模式下对`MSG_NDEF_TAG`类型设备的处理](#nfc-rw模式下对msg_ndef_tag类型设备的处理)
  - [NFC R/W模式上行数据流程](#nfc-rw模式上行数据流程)

# Android NFC

## 基础
NFC服务`NfcService`运行于`com.android.nfc`进程之中, 其底层有很多层次结构.

NFC有多种工作方式:
* Reader/Write模式, 也就是读写模式
* Peer-to-Peer模式, 也就是点对点模式
* NFC Card Emulation模式, 也就是模拟卡模式

这里主要讨论读写模式.

## NFC的启用
应用通过`INfcAdapter`接口的`enable()`函数启用NFC, 该消息将在`NfcAdapterService`中处理, 该调用发生后`NfcAdapterService`通过异步任务`EnableDisableTask`发送`TASK_ENABLE`消息给`NativeNfcManager`, 后者通过`initialize()`响应, 并执行native方法`doInitialize()`.

`doInitialize()`本地方法定义对应`packages/apps/Nfc/nci/jni/NativeNfcManager.cpp`中的`nfcManager_doInitialize()`, 首先通过`NfcAdaptation::GetInstance()`获取`tHAL_NFC_ENTRY`, 然后通过`NFA_Init()`初始化`NFA`, 并将`tHAL_NFC_ENTRY`设置在全局的`nfc_cb.p_hal`. `NFA_Init()`其余各组建的初始化暂时略去.

`NfcAdaptation::GetInstance()`时通过`NfcAdaptation::InitializeHalDeviceContext()`完成了初始化, 并且通过`[INfcV1_1|INfcV1_2]::getService()`获取了[INfcV1_1|INfcV1_1]接口, 并保存到[mHal_1_1|mHal_1_2]中.

接着`NativeNfcManager`通过`NFA_Enable()`启用NFC, 并注册了两个回调:
* `nfaDeviceManagementCallback()`, 负责响应设备管理的消息, 例如设备发现
* `nfaConnectionCallback()`, 负责响应设备链接的消息, 然后通过`sNfaEnableEvent`等待底层处理完成NFC的启用.

以上两个回调将被封装成一个NFC消息(其消息头的事件类型被标记为`NFA_DM_API_ENABLE_EVT`), 通过消息盒子走`GKI`发送给`nfc_task`线程统一处理.

在考虑`nfc_task`处理`DeviceManager`消息之前, 关注`NFA_Init()`中`nfa_dm_init()`的调用, 该方法初始化了全局的`nfa_dm_cb`, 注册了关键的回调:`tNFA_SYS_REG nfa_dm_sys_reg`, 该回调被注册掉全局的`nfa_sys_cb.reg[id]`中(此处的`id`显然是`NFA_ID_DM`), 该回调中的`evt_hdlr`方法(也就是`nfa_dm_evt_hdlr()`)负责根据具体的消息类型(例如上文提到的:`NFA_DM_API_ENABLE_EVT`)回调`nfa_dm_action[]`中相应的方法, 处理所有`NFA_DM_API_*`类型的消息.

接着看`nfc_task`是如何响应该消息的, `nfc_task`首先通过`GKI_Wait()`等待`NFA_MBOX_EVT_MASK`类型的消息, 然后通过`GKI_read_mbox()`读取消息内容交由`nfa_sys_event`处理, `nfa_sys_event()`则调用上文的`nfa_sys_cb.reg[id]->evt_hdlr`来处理, 此处自然是`nfa_dm_evt_hdlr()`(此时的id是`NFA_ID_DM`), 在根据此前的事件`NFA_DM_API_ENABLE_EVT`调用到`nfa_dm_action[]`中的`nfa_dm_enable()`, 注意此处:
* 上文的`nfaDeviceManagementCallback()`被设置到了`nfa_dm_cb.p_dm_cback`
* 上文的`nfaConnectionCallback()`被设置到了`nfa_dm_cb.p_conn_cback`

`nfa_dm_enable()`继续调用`NFC_Enable()`启用NFC功能, 并传入`nfa_dm_nfc_response_cback()`回调, `nfa_dm_nfc_response_cback()`被保存到`nfc_cb.p_resp_cback`, 然后调用`nfc_cb.p_hal->open`打开`HAL`层, 并传入`nfc_main_hal_cback()`和`nfc_main_hal_data_cback()`两个回调.

此处的`tHAL_NFC_ENTRY`实际上是`NfcAdaptation::mHalEntryFuncs`, 该结构体已经在首次执行`NfcAdaptation::GetInstance()`时通过`NfcAdaptation::InitializeHalDeviceContext()`完成了初始化. 那此处的`open`对应的则是`HalOpen()`, 该函数将通过`[INfcV1_1|INfcV1_2]`对`HAL`层进行`open`操作, 并传入`NfcClientCallback()`(集成了接口`INfcClientCallback`)回调.

至此上文提到的`nfc_main_hal_cback()`和`nfc_main_hal_data_cback()`被分别保存在`NfcClientCallback`的`mEventCallback`和`mDataCallback`中:
* 当`HAL`曾通过`INfcClientCallback`回调`sendEvent[_1_1]()`接口时, `nfc_main_hal_cback()`被回调
* 当`HAL`曾通过`INfcClientCallback`回调`sendData()`接口时, `nfc_main_hal_data_cback()`被回调

那么什么时候通过`nfc_cb.p_resp_cback`回调`nfa_dm_nfc_response_cback()`呢? `nfc_main_hal_cback()`通过`NfcClientCallback::sendEvent[_1_1]()`被调用, 如果`nfc_main_hal_cback()`收到`HAL_NFC_OPEN_CPLT_EVT`表示打开成功的事件, 则通过`nfc_main_post_hal_evt()`发消息个`nfc_task`, 消息类型是`BT_EVT_TO_NFC_MSGS`(底层NFC消息, 掩码是`NFC_EVT_MASK`), 然后`nfc_task`调用`nfc_main_handle_hal_evt()`检查`tNFC_HAL_EVT_MSG.hal_evt`, 如果是`HAL_NFC_POST_INIT_CPLT_EVT`, 则调用`nfc_enabled()`进行部分工作后调用`nfc_main_notify_enable_status()`(参数是`NCI_STATUS_OK`)向上通知事件, 次过程将回调上文保存的`nfc_cb.p_resp_cback`(也就是`nfa_dm_nfc_response_cback()`), 并传递`NFC_ENABLE_REVT`参数. 然后`nfa_dm_nfc_response_cback()`继续回调`nfa_dm_cb.p_dm_cback`, 这里的`nfa_dm_cb.p_dm_cback`是上文的`nfaDeviceManagementCallback()`, 参数是`NFA_DM_ENABLE_EVT`, 这里可以看到通过`sNfaEnableEvent`, 通知了`nfcManager_doInitialize()`
<!-- 
HAL NFC状态
|状态|值|
|:-|:-|
|HAL_NFC_OPEN_CPLT_EVT|
|HAL_NFC_CLOSE_CPLT_EVT|
|HAL_NFC_POST_INIT_CPLT_EVT|
|HAL_NFC_PRE_DISCOVER_CPLT_EVT|
|HAL_NFC_REQUEST_CONTROL_EVT|
|HAL_NFC_RELEASE_CONTROL_EVT|
|HAL_NFC_ERROR_EVT|
|HAL_HCI_NETWORK_RESET| -->

## NFC R/W模式监听的启用
`NfcService`通过`BroadcastReceiver`监听亮屏广播`ACTION_SCREEN_ON`, 然后通过异步任务`ApplyRoutingTask`执行设备发现的启用和关闭. 这里假设亮屏, `AppleRoutingTask.doInBackground()`的参数为`true`, 进一步`NativeNfcManager.enableDiscovery()`被调用, 其调用本地方法`doEnableDiscovery()`, 对应`packages/apps/Nfc/nci/jni/NativeNfcManager.cpp`中的`nfcManager_enableDiscovery()`, 此时`tech_mask`不为空, 因此`startPolling_rfDiscoveryDisabled()`被调用, 进一步`NFA_EnablePolling()`也被调用, 此时向`nfc_task`发出`NFA_DM_API_ENABLE_POLLING_EVT`消息.

上述`NFA_DM_API_ENABLE_POLLING_EVT`消息被`nfa_dm_action[]`中的`nfa_dm_act_enable_polling()`响应, 最后`nfa_dm_start_polling()`被调用. `nfa_dm_poll_disc_cback()`被保存在`nfa_dm_cb.disc_cb.entry[xx].p_disc_cback`用于响应发现设备事件.

回到`nfcManager_enableDiscovery()`该方法最后调用了`startRfDiscovery()`, 向`nfc_task`发出了`NFA_DM_API_START_RF_DISCOVERY_EVT`消息, 该消息最终由`nfa_dm_action[]`中的`nfa_dm_act_start_rf_discovery()`处理, 该方法通过`nfa_dm_start_rf_discover()`分别调用了:
* `NFC_DiscoveryStart()`: 负责将`nfa_dm_disc_discovery_cback()`设置到了`nfc_cb.p_discv_cback`
* `NFC_SetStaticRfCback()`: 负责将`nfa_dm_disc_data_cback()`设置到了`&nfc_cb.conn_cb[NFC_RF_CONN_ID]->p_cback`

## NFC R/W模式操作的底层初始化
在开始探寻NFC设备发现之前, 我们可以先假设, NFC将链接的设备是标签设备, 关注在`NFA_Init()`中, 对`nfa_rw_init()`的调用, 注册了`NFA_ID_RW`的响应:`tNFA_SYS_REG nfa_rw_sys_reg`, 其中`nfa_rw_sys_reg`的`evb_hdlr`为`nfa_rw_handle_event()`, 其将通过`tNFA_RW_ACTION nfa_rw_action_tbl[]`处理所有的`NFA_RW_*`消息

## NFC R/W模式对设备的发现
如果有HAL通过底层驱动发现了新设备, 则上文的`nfc_main_hal_data_cback()`被调用, 此时想`nfc_task`发出`BT_EVT_TO_NFC_NCI`消息, 而`nfc_task`调用首先判定收到的消息类型为`NCI_MT_RSP`, 然后进一步判断并通过`nci_proc_rf_management_ntf()`处理`gid`为`NCI_GID_RF_MANAGE`的消息(底层发出), 进一步判断`HAL`层消息的操作码`op_code`, 如果是发现设别则为`NCI_MSG_RF_INTF_ACTIVATED`, 因此`nfc_ncif_proc_discover_ntf()`被调用, 在处理完成数据后, 调用`nfc_cb.p_discv_cback`, 也就是`nfa_dm_disc_discovery_cback()`进一步处理, 显然, 此时的消息类型是`NFC_ACTIVATE_DEVT`.

`nfa_dm_disc_discovery_cback()`收到`NFC_ACTIVATE_DEVT`后调传递发现设备消息`NFA_DM_RF_INTF_ACTIVATED_NTF`给`nfa_dm_disc_sm_execute()`, 后者检查`nfa_dm_cb.disc_cb.disc_state`的值, 此时为`NFA_DM_RFST_DISCOVERY`, 因此调用`nfa_dm_disc_sm_discovery()`, 后者根据事件类型`NFA_DM_RF_INTF_ACTIVATED_NTF`调用`nfa_dm_disc_notify_activation()`, 最终通过`nfa_dm_cb.disc_cb.entry[xx].p_disc_cback`调用到`nfa_dm_poll_disc_cback()`并继续传递事件`NFA_DM_RF_DISC_ACTIVATED_EVT`.

`nfa_dm_poll_disc_cback()`通过事件类型`NFA_DM_RF_DISC_ACTIVATED_EVT`调用`nfa_rw_proc_disc_evt()`并传递事件`NFA_DM_RF_DISC_ACTIVATED_EVT`, 最终根据`NFA_RW_ACTIVATE_NTF_EVT`通过`nfa_rw_handle_event()`调用`nfa_rw_action_tbl[]`中的`nfa_rw_activate_ntf()`方法. 这里可以注意下, 不是通过`tNFA_SYS_REG nfa_rw_sys_reg`调用过来的.

`nfa_rw_activate_ntf()`通过`RW_SetActivatedTagType()`根据协议(这里是`NFC_PROTOCOL_T2T`)执行了连个操作:
* 将`nfa_rw_cback()`设置给了`rw_cb.p_cback`
* 调用`rw_t2t_select()`, 后者通过`NFC_SetStaticRfCback()`将`p_cb->p_cback`设置成了`rw_t2t_conn_cback()`以供后续有上行数据上来时调用.
<!-- 
备注: NFC协议
|定义|说明|
|:-|:-|
|NFC_PROTOCOL_T1T|Type1Tag - NFC-A|
|NFC_PROTOCOL_T2T|Type2Tag    - NFC-A|
|NFC_PROTOCOL_T3T|Type3Tag    - NFC-F|
|NFC_PROTOCOL_T5T|Type5Tag    - NFC-V/ISO15693|
|NFC_PROTOCOL_ISO_DEP|Type 4A,4B  - NFC-A or NFC-B|
|NFC_PROTOCOL_MIFARE|
|NFC_PROTOCOL_ISO15693|
|NFC_PROTOCOL_B_PRIME|
|NFC_PROTOCOL_KOVIO| -->


`nfa_rw_activate_ntf()`处理完成后会调用`nfa_dm_notify_activation_status()`, 而后者继续调用`nfa_dm_notify_activation_status()`并传递`NFA_ACTIVATED_EVT`事件, 最终通过`nfa_dm_cb.p_conn_cback`调用到上文设置的`nfaConnectionCallback()`, 此时由于不是点对点传输方式, 因此`NfcTag::connectionEventHandler()`被调用, 事件`NFA_ACTIVATED_EVT`被继续传递, 最终通过`NfcTag::createNativeNfcTag()`完成对`NativeNfcTag`的创建, 并完成一系列信息的设置.

最终通过`gCachedNfcManagerNotifyNdefMessageListeners()`回调Java层的`NativNfcManager.notifyNdefMessageListeners()`, 此时`NativeNfcManager`调用监听者`DeviceHostListener`的`onRemoteEndpointDiscovered()`接口, 此处`DeviceHostListener`的实现是`NfcService`, 因此`NfcService.onRemoteEndpointDiscovered()`被调用. 

`NfcService`在被底层通知有新的`TagEndpoint`(实现为`NativeNfcTag`)时, 直接发出了个`NfcService.MSG_NDEF_TAG`的异步消息, 这个消息会被`NfcServiceHandler`响应, 并进行接下来的判断.

## NFC R/W模式下对`MSG_NDEF_TAG`类型设备的处理
`NfcService`首先通过`NativeNfcTag.findAndReadNdef()`读取`NDEF`信息, 对于`NativeNfcTag`后续的调用分别为`readNdef()`和`doRead()`, 其中`doRead()`是个本地方法, 对应的是`packages/apps/Nfc/nci/jni/NativeNfcTag.cpp`中的`nativeNfcTag_doRead()`方法, 其通过`NFA_RwReadNDef()`发送`NFA_RW_OP_REQUEST_EVT`消息给`nfc_task`, 操作类型为`NFA_RW_OP_READ_NDEF`. 该方法发送完消息后, 通过`sReadEvent`等待读取事务的完成.

`nfc_task`收到消息后, 首先判断其类型为: `NFA_ID_RW`, 然后在`nfa_sys_event()`中通过`nfa_sys_cb.reg[NFA_ID_RW]->evt_hdlr`调用到`nfa_rw_sys_reg`中的`nfa_rw_handle_event()`, 而后者通过之前的`NFA_RW_OP_REQUEST_EVT`消息调用到`nfa_rw_action_tbl[]`中的`nfa_rw_handle_op_req()`.

上文说过操作是`NFA_RW_OP_READ_NDEF`, 因此`nfa_rw_handle_op_req()`继续调用`nfa_rw_read_ndef()`读取`NDEF`信息, 进一步调用`nfa_rw_start_ndef_read()`, 此时需要判断设备的协议类型, 如果是`NFC_PROTOCOL_T2T`, 则调用`RW_T2tReadNDef()`, 而后者继续调用`rw_t2t_read()`发起读取操作. 该函数准备参数, 继续调用`rw_t2t_send_cmd()`执行发送, 操作码为`T2T_CMD_READ`, 发送的过程通过`NFC_SendData()`(`conn_id`为`NFC_RF_CONN_ID`)调用`nfc_ncif_send_data()`完成.

`nfc_ncif_send_data()`通过`HAL_WRITE()`(也就是`nfc_cb.p_hal->write`)完成数据的`HAL`层的写入, 这里显然是`system/nfc/src/adaptation/NfcAdaptation.cc:HalWrite()`, `NfcAdaptation`继续通过`INfcAidl::write()`接口通过`Binder`执行发送操作.

## NFC R/W模式上行数据流程
上文说过, `HAL`层有数据会回调`nfc_main_hal_data_cback()`, 该函数向`nfc_task`发出`BT_EVT_TO_NFC_NCI`消息, 而`nfc_task`通过`nfc_ncif_process_event()`响应, 如果是设备回复数据, 则消息类型为`NCI_MT_DATA`, 对应的处理函数为`nfc_ncif_proc_data()`, 读取到数据后, 进一步调用`nfc_data_event()`, 该函数通过`p_cb->p_cback`通知上层, 根据上文的内容, 此处在`rw_t2t_select()`中被`NFC_SetStaticRfCback()`设置为`rw_t2t_conn_cback()`, 该方法被调用是, 传递了事件`NFC_DATA_CEVT`, 因此`rw_t2t_proc_data()`被调用, 进一步的`rw_t2t_handle_rsp()`被调用, 然后开始检查`p_t2t->state`的值, 此情形下是`RW_T2T_STATE_READ_NDEF`, 因此调用`rw_t2t_handle_ndef_read_rsp()`, 该函数回调`rw_cb.p_cback`(此处为`nfa_rw_cback()`)并传入参数事件`RW_T2T_NDEF_READ_EVT`, `nfa_rw_cback()`在协议为`NFC_PROTOCOL_T2T`时调用`nfa_rw_handle_t2t_evt()`. 

`nfa_rw_handle_t2t_evt()`先处理`RW_T2T_NDEF_READ_EVT`消息, 然后调用`nfa_dm_act_conn_cback_notify()`通知上层, 通知的事件是`NFA_READ_CPLT_EVT`, 进一步通过`nfa_dm_conn_cback_event_notify()`回调上文讲到的`nfa_dm_cb.p_conn_cback`所指向的`nfaConnectionCallback()`, 该回调调用`nativeNfcTag_doReadCompleted()`, 后者通过`sReadEvent`发送消息给`nativeNfcTag_doRead()`方法使其返回.