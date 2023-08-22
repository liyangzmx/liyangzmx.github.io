- [前期设置](#前期设置)
  - [SSLContext.getInstance("TLS")](#sslcontextgetinstancetls)
  - [SSLContext.init()](#sslcontextinit)
  - [SSLContext.getSocketFactory()](#sslcontextgetsocketfactory)
  - [SSLSocketFactory.createSocket()](#sslsocketfactorycreatesocket)
  - [NativeSsl.newInstance()](#nativesslnewinstance)
  - [BioWrapper 的创建](#biowrapper-的创建)
  - [ConscryptEngineSocket.startHandshake()](#conscryptenginesocketstarthandshake)
- [TLS协商](#tls协商)
  - [state\_start\_connect(TLS)](#state_start_connecttls)
  - [state\_enter\_early\_data(TLS)](#state_enter_early_datatls)
  - [state\_read\_server\_hello(TLS)](#state_read_server_hellotls)
  - [state\_tls13(TLS)](#state_tls13tls)
  - [state\_read\_hello\_retry\_request(0, TLSv1.3 start)](#state_read_hello_retry_request0-tlsv13-start)
  - [state\_read\_server\_hello(2)](#state_read_server_hello2)
  - [state\_read\_encrypted\_extensions(3)](#state_read_encrypted_extensions3)
  - [state\_read\_certificate\_request(4)](#state_read_certificate_request4)
  - [state\_read\_server\_certificate(5)](#state_read_server_certificate5)
  - [state\_read\_server\_certificate\_verify(6)](#state_read_server_certificate_verify6)
  - [state\_read\_server\_finished(8)](#state_read_server_finished8)
  - [state\_send\_end\_of\_early\_data(9)](#state_send_end_of_early_data9)
  - [state\_send\_client\_encrypted\_extensions(10)](#state_send_client_encrypted_extensions10)
  - [state\_send\_client\_certificate(11)](#state_send_client_certificate11)
  - [state\_send\_client\_certificate\_verify(12)](#state_send_client_certificate_verify12)
  - [state\_complete\_second\_flight(13)](#state_complete_second_flight13)
  - [state\_done(14, TLSv1.3 end)](#state_done14-tlsv13-end)
  - [state\_finish\_client\_handshake(TLS)](#state_finish_client_handshaketls)
- [加密与解密](#加密与解密)
  - [SSLOutputStream.write() 时的加密](#ssloutputstreamwrite-时的加密)
  - [SSLInputStream.read() 时的解密](#sslinputstreamread-时的解密)


# 前期设置

## SSLContext.getInstance("TLS")

首先通过`SSLContext.getInstance("TLS")`获取`SSLContext`, 此时的`SSLContext`中的`SSLContextSpi`是`OpenSSLContextImpl`, 在`OpenSSLContextImpl`构造时, 构造了`ClientSessionContext`并记录在`OpenSSLContextImpl.clientSessionContext`. 而在`ClientSessionContext`构造时, 其父类`AbstractSessionContext`的构造函数中, 调用了底层的`NativeCrypto.SSL_CTX_new()`创建了`SSL_CTX`并记录在`OpenSSLContextImpl.super.sslCtxNativePointer`中(主要步骤):
* 调用`TLS_with_buffers_method()`获取`SSL_METHOD`:

  ```c
    static const SSL_METHOD kMethod = {
        0,
        &kTLSProtocolMethod,
        &ssl_noop_x509_method,
    };
  ```

* 通过`SSL_CTX_new()`创建`SSL_CTX`并进行一系列设置, 其中, `SSL_CTX.method`设置为`kMethod`:

  * `SSL_CTX.method`设置为`kTLSProtocolMethod`(类型为`SSL_PROTOCOL_METHOD`)

  * `SSL_CTX.x509_method`设置为`ssl_noop_x509_method`(类型为`SSL_X509_METHOD`)

  * 其中: `kTLSProtocolMethod`的定义:

    ```c
    static const SSL_PROTOCOL_METHOD kTLSProtocolMethod = {
        false /* is_dtls */,
        tls_new, // 初始化 SSL, 创建 SSL_HANDSHAKE
        tls_free,
        tls_get_message, // PEEK 一个 SSLMessage
        tls_next_message, // 读取一个 SSLMessage
        tls_has_unprocessed_handshake_data,
        tls_open_handshake,
        tls_open_change_cipher_spec,
        tls_open_app_data,
        tls_write_app_data, // 加密明文的 app 数据并写到输出
        tls_dispatch_alert,
        tls_init_message, // 初始化一个 SSLMessage
        tls_finish_message,// 销毁一个 SSLMessage
        tls_add_message, // 将 SSLMessage 添加到输出
        tls_add_change_cipher_spec,
        tls_flush_flight, // 冲刷未发送的数据到 BIO
        tls_on_handshake_complete,
        tls_set_read_state, // 设置 SSL.s3->aead_write_ctx
        tls_set_write_state, // 设置 SSL.s3->aead_read_ctx
    };
    ```

    该数据结构设计的方法将会经常出现在后文当中

* 通过`SSL_CTX_set_info_callback()`设置监听SSL连接状态对应的回调函数为: `info_callback`, 其调用的上层接口为: `ConscryptEngine.onSSLStateChange()`

* 通过`SSL_CTX_set_cert_cb()`设置证书回调为: `cert_cb`, 其调用的上层接口为: `ConscryptEngine.clientCertificateRequested() -> NativeSsl.chooseClientCertificate()`

## SSLContext.init()
上层调用`SSLContext.init() -> OpenSSLContextImpl.engineInit()`, 此时创建了`SSLParametersImpl`并记录了上层传递的`X509KeyManager`和`X509TrustManager`.

创建`SSLParametersImpl`时, 其`clientSessionContext`成员(类型是`ClientSessionContext`)

## SSLContext.getSocketFactory()
上层调用`SSLContext.getSocketFactory()`获取`SSLSocketFactory`(实际是`OpenSSLSocketFactoryImpl`), `OpenSSLSocketFactoryImpl`保存了`SSLParametersImpl`

## SSLSocketFactory.createSocket()
上层调用`SSLSocketFactory`(实际是`OpenSSLSocketFactoryImpl`)的`createSocket()`方法, 经过`Platform.createEngineSocket()`创建`Java8EngineSocket`(其父类是`ConscryptEngineSocket`), 其父类的`newEngine`方法创建`ConscryptEngine`, 此时将`SSLParametersImpl`克隆一份, 并传入. `ConscryptEngine`在构造时, 将通过`newSsl() -> NativeSsl.newInstance()`实例化`NativeSsl`, `SSLParametersImpl`将保存在`NativeSsl.parameters`, 其基本引用关系:  
`ConscryptEngineSocket.engine`: `Java8EngineSocket`
`ConscryptEngineSocket.engine.ssl`: `NativeSsl`
`ConscryptEngineSocket.engine.ssl.parameters`: `SSLParametersImpl`

## NativeSsl.newInstance()
* 通过`parameters.getSessionContext()`获取了`ClientSessionContext`结构体地址
* 调用`ClientSessionContext.newSsl()`, 传入`ClientSessionContext`, 创建`SSL`结构体, 其底层调用为`NativeCrypto.SSL_new()`, 此处底层调用到: `NativeCrypto_SSL_new()`:
    * 通过`to_SSL_CTX()`还原指针`ssl_ctx_address`为: `SSL_CTX`
    * 将`SSL_CTX`传入`SSL_new()`以创建`SSL`结构体
    * 通过`SSL_set_custom_verify()`设置SSL的回调函数为:`cert_verify_callback()`, 该方法负责完成对服务端证书的验证, 在`cert_verify_callback()`中, 回调上层的`NativeCrypto.verifyCertificateChain()`
* `SSL`结构体被传递给`NativeCrypto.SSL_new()`, 保存到`NativeSsl.ssl`, 从顶层向下:`ConscryptEngineSocket.engine.ssl.ssl`

## BioWrapper 的创建
这里注意下 `ConscryptEngine.networkBio()`, 它的类型是`BioWrapper`, 是很重要的角色, 它负责处理所有 "**加密**" 的数据, 通过`NativeSsl.newBio()`创建, 更底层的方法是:`NativeCrypto.SSL_BIO_new()`:
* 通过`BIO_new_bio_pair()`创建一对`BIO`:`internal_bio`和`network_bio`, 此时创建的`BIO.mehtod`被设置为`methods_biop`, 因此`BIO.mehtod->bread`被设置为`bio_read`, 而`BIO.mehtod->bwrite`被设置为: `bio_write`
* 通过`SSL_set_bio()`将`internal_bio`配置给了`SSL`, 保存在(`SSL.wbio`和`SSL.rbio`)
* 将`network_bio`引用在`BioWrapper.bio`  

`ConscryptEngine.networkBio.bio`非常重要, 它将在后文经常被提到.

## ConscryptEngineSocket.startHandshake()
上层调用`ConscryptEngineSocket.startHandshake()`开始执行MTLS协商:
* 创建 `SSLInputStream`并保存到`ConscryptEngineSocket.in`, 在此过程中
    * 通过`ByteBuffer.allocateDirect`分配与`NativeSsl`交互的`DirectByteBuffer`, 此处的 buffer 对于 JNI 来说是没有拷贝成本的. `DirectByteBuffer`保存到 `ConscryptEngineSocket.in.fromEngine`
    * 通过 `ByteBuffer.allocate()`分配与`SocketInputStream`进行通信的的`HeapByteBuffer`, `HeapByteBuffer`保存到 `ConscryptEngineSocket.in.fromSocket`
* 创建 `SSLOutputStream`并保存到`ConscryptEngineSocket.out`, 在此过程中:
    * 通过 `ByteBuffer.allocate()`分配与`SocketOutputStream`进行通信的的`HeapByteBuffer`, `HeapByteBuffer`保存到 `ConscryptEngineSocket.out.target`
* 调用`SSLInputStream.processDataFromSocket()`获取数据, 调用`readFromSocket()`从`SocketInputStream`读取数据, 然后调用`ConscryptEngine.unwrap()`处理读取到的数据, 细节见解密小节

# TLS协商
TLS协商的主循环:
```c++
NativeCrypto_ENGINE_SSL_read_direct() [libjavacrypto.so] ->
    ::SSL_read() [libssl.so] ->
        ssl_read_impl() ->
            ::SSL_do_handshake() ->
                bssl::ssl_run_handshake()
```
该函数是一个循环, 该循环依次调用`SSL_HANDSHAKE.ssl->do_handshake`方法, 对于客户端, 该方法为`ssl_client_handshake()`, 在该方法中, 初始状态为`state_start_connect()`

## state_start_connect(TLS)
`state_start_connect`对应的执行函数为`do_start_connect()`:
* 初始化`SSL.s3`结构体
* 调用`ssl_setup_key_shares()`初始化 keys_shares
* 调用`ssl_setup_extension_permutation()`初始化扩展
* 调用`ssl_encrypt_client_hello()`加密 client_hello
* 调用`ssl_add_client_hello()`将 client_hello 附加到消息池(`SSL.s3->write_buffer`中)
* 返回状态为: `ssl_hs_flush`
如果该状态顺利执行结束, 则向上返回给`ssl_run_handshake()`的结果是`ssl_hs_flush`, 因此`ssl_run_handshake()`继续执行`SSL_HANDSHAKE.ssl->method->flush_flight`方法, 该方法为`kTLSProtocolMethod.flush_flight`即`tls_flush_flight()`, 进一步调用`ssl_write_buffer_flush() -> tls_write_buffer_flush() -> BIO_write()`, 将`ssl.s3->write_buffer`数据写入到`SSL.wbio`的`BIO`中, 如前文所述, 该`BIO`即`internal_bio`, 其关联的对象为`network_bio`, 至此上层就可以通过`NativeCrypto.ENGINE_SSL_read_BIO_direct()`读取到数 BoringSSL 需要发送的数据了.

## state_enter_early_data(TLS)
执行`do_enter_early_data()`, 基本没有做太多事情, 判断`SSL_HANDSHAKE.early_data_offered`为空就直接切换状态到`state_read_server_hello`

## state_read_server_hello(TLS)
执行 `do_read_server_hello()`, 并读取TLS数据, 调用`ssl_parse_server_hello()`解析协议头, 获取版本号, 本文的案例显然是**MTLSv1.3**, 则切换状态到 `state_tls13`

## state_tls13(TLS)
执行`do_tls13() -> tls13_client_handshake()`, 该函数也是一个循环, 如果`SSL_HANDSHAKE.tls13_state`不为`state_done`就循环执行后续的状态切换, 初始状态为: `state_read_hello_retry_request`

## state_read_hello_retry_request(0, TLSv1.3 start)
调用`do_read_hello_retry_request()`:

* 调用`parse_server_hello_tls13()`解析消息头

* 调用`SSL_get_cipher_by_value()`获取服务器要求的算法: `SSL_CIPHER`, 本文的案例是`TLS1_3_RFC_AES_128_GCM_SHA256`, 协议 id 为 4865, 也就是:

  ```c
  static constexpr SSL_CIPHER kCiphers[] = {
      // Cipher 1301
      {
        TLS1_3_RFC_AES_128_GCM_SHA256,
        "TLS_AES_128_GCM_SHA256",
        TLS1_3_CK_AES_128_GCM_SHA256,
        SSL_kGENERIC,
        SSL_aGENERIC,
        SSL_AES128GCM,
        SSL_AEAD,
        SSL_HANDSHAKE_MAC_SHA256,
      },
      ...
  };
  ```

* 将 `SSL_CIPHER`保存到`SSL_HANDSHAKE.new_cipher`

* 切换状态到`state_read_server_hello`

## state_read_server_hello(2)
调用`do_read_server_hello()`, 该函数做了很多工作:
* 复制并保存 `server_random`
* 将`SSL_HANDSHAKE.new_cipher`保存到`SSK_HANDSHAKE.new_session->cipher`
* 调用`ssl_ext_key_share_parse_serverhello()`从`server_hello`中解析出`dhe_secret`
* 调用`tls13_advance_key_schedule()`派生秘钥并保存到`SSL_HANDSHAKE.secret_`
* 调用`tls13_derive_handshake_secrets()`派生秘钥并保存到`SSL_HANDSHAKE.client_handshake_secret_`
* 调用`tls13_set_traffic_key()`将`SSL_HANDSHAKE.client_handshake_secret_`设置到`SSL`:
  * 调用`ssl_cipher_get_evp_aead()`确定`EVP_AEAD`,  该结构体主要为了确定秘钥长度
  * 调用`ssl_session_get_digest()`获取`EVP_MD`用于秘钥派生
  * 以"key"作为`label`调用`hkdf_expand_label()`派生秘钥
  * 以"iv"作为`label`调用`hkdf_expand_label()`派生初始向量
  * 调用`SSLAEADContext::Create()`并传入`SSL`, `Cipher`, 秘钥, `iv`, 创建`SSLAEADContext`
  * 调用`SSL.method->set_read_state`即`tls_set_read_state()`设置`SSLAEADContext`到`SSL_HANDSHAKE.ssl->s3->aead_read_ctx`
  * 保存`SSL_HANDSHAKE.client_handshake_secret_`到`SSL.s3->read_traffic_secret`
  * 调用`SSL.method->set_write_state`即`tls_set_write_state()`设置`SSLAEADContext`到`SSL_HANDSHAKE.ssl->s3->aead_write_ctx`
  * 保存`SSL_HANDSHAKE.client_handshake_secret_`到`SSL.s3->write_traffic_secret`

从此刻开始, 与服务器的数据往来都使用: `SSL_HANDSHAKE.client_handshake_secret_` 加密

## state_read_encrypted_extensions(3)

## state_read_certificate_request(4)

调用`do_read_certificate_request()`

## state_read_server_certificate(5)

调用`do_read_server_certificate() -> tls13_process_certificate()`,  从服务器返回的消息解析证书信息, 将证书保存到`SSL_HANDSHAKE.new_session->certs`

## state_read_server_certificate_verify(6)
调用`do_read_server_certificate_verify() -> ssl_verify_peer_cert() -> SSL_HANDSHAKE.ssl->config->custom_verify_callback`, 根据前文, `SSL_HANDSHAKE.ssl->config->custom_verify_callback`已经被`SSL_set_custom_verify()`设置为:`cert_verify_callback()`:

* 调用`SSL_get0_peer_certificates()`获取上文刚解析到的服务器证书链:`SSL_HANDSHAKE.new_session->certs`

* 调用上层: `ConscryptEngine.verifyCertificateChain() -> Platform.checkServerTrusted() -> X509Trustmanager.checkServerTrusted()`, 其中`ConscryptEngine`继承了`NativeCrypto.SSLHandshakeCallbacks`, `X509Trustmanager.checkServerTrusted()`为用户自定义的服务器证书验证方法.

## state_read_server_finished(8)

调用`do_read_server_finished()`:

* 调用`tls13_advance_key_schedule()`更新加密算法
* 调用`tls13_derive_application_secrets() -> derive_secret("CLIENT_TRAFFIC_SECRET_0")`派生交换凭据的秘钥, 保存到`SSL_HANDSHAKE.client_traffic_secret_0_`

注意, 此时的`SSL_HANDSHAKE.client_traffic_secret_0_`并没有作为会话秘钥, 这是因为还没有发送本地的凭据(这里我们只讨论 **MTLSv1.3** )

## state_send_end_of_early_data(9)

## state_send_client_encrypted_extensions(10)

## state_send_client_certificate(11)
调用`do_send_client_certificate() -> SSL_HANDSHAKE.ssl->cert->cert_cb`, 该回调被`SSL_CTX_set_cert_cb()`设置为`external/conscrypt/common/src/jni/main/cpp/conscrypt/native_crypto.cc::cert_cb()`将在如下环节被调用:
```c++
bssl::ssl_run_handshake() ->
    bssl::ssl_client_handshake() ->
        bssl::tls13_client_handshake() ->
            bssl::do_send_client_certificate() ->
                cert_cb() [libjavacrypto.so]
```
如上文`cert_cb()`调用的上层接口为: `ConscryptEngine.clientCertificateRequested() -> NativeSsl.chooseClientCertificate()`, 其首先调用`ConscryptEngineSocket.chooseClientAlias()`选取本地的证书别名, 而`ConscryptEngineSocket.chooseClientAlias()`实际上是调用了`X509KeyManager.chooseClientAlias()`, 然后通过`setCertificate()`设置本地的证书&密钥, 参数为证书与秘钥的别名:
* 从`SSLParametersImpl`中获取`X509KeyManager`

* 从`X509KeyManager`中获取`PrivateKey`, 这是上层应用自定义的

* 从`X509KeyManager`中获取所有可用的`X509Certificate`, 即`X509Certificate[]`

* 从`PrivateKey`转换到`OpenSSLKey`, 这里调用: `OpenSSLKey.fromPrivateKeyForTLSStackOnly() -> fromECPrivateKeyForTLSStackOnly() -> OpenSSLECPrivateKey.wrapJCAPrivateKeyForTLSStackOnly()`, 首先调用`OpenSSLECGroupContext.getInstance()`从`ECParameterSpec`获取`OpenSSLECGroupContext`. 创建`OpenSSLKey`, 调用`NativeCrypto_getECPrivateKeyWrapper()`产生底层的`EVP_PKEY`结构体, 传递`OpenSSLECGroupContext`作为参数:
  * 上层传递了秘钥的 Group 信息, 通过`fromContextObject<EC_GROUP>()`转换参数`groupRef`转换到`EC_GROUP`, 
    * 通过`ensure_engine_globals() -> init_engine_globals()`初始化`g_rsa_method`和`g_ecdsa_method`:
      * 通过`ENGINE_new()`初始化`g_engine`
      * 通过`ENGINE_set_RSA_method`配置`g_rsa_method`给`g_engine`
      * 通过`ENGINE_set_ECDSA_method`配置`g_ecdsa_method`给`g_engine`
    
  * 通过`EC_KEY_new_method()`创建 `EC_KEY`结构体
  
  * 通过`EC_KEY_set_group()`配置 `EC_KEY`的 `Group`信息
  
  * 构造`KeyExData`结构体, 将上层传递的`javaKey`的 `jobject` 对象保存到刚刚创建的`KeyExData.private_key`字段
  
  * 通过`EC_KEY_set_ex_data()`配置`KeyExData`结构体到 `EC_KEY`
  
  * 通过`EVP_PKEY_new()`创建`EVP_PKEY`结构体
  
  * 通过`EVP_PKEY_assign_EC_KEY()`将`EC_KEY` 结构体分配给 `EVP_PKEY` 结构体
  
  * 创建的 `EVP_PKEY` 结构体保存到`OpenSSLKey.ctx`中, 所以后续将`OpenSSLKey`传递给底层时, 获取`ctx`即可  
    可以看到, `OpenSSLKey.ctx`即`EVP_PKEY`, 其中:
    * `EVP_PKEY.ameth`被设置为`ec_asn1_meth`
    
      ```c
      const EVP_PKEY_ASN1_METHOD ec_asn1_meth = {
          EVP_PKEY_EC,
          // 1.2.840.10045.2.1
          {0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01},
          7,
          &ec_pkey_meth,
          eckey_pub_decode, // 从 DER 中解码 EC-PublicKey
          eckey_pub_encode, // 编码 EC-PublicKey 到 DER
          eckey_pub_cmp, // 比较两个公钥是否相同
          eckey_priv_decode, // 从 DER 解码 EC-PrivateKey
          eckey_priv_encode, // 编码 EC-PrivateKey 到 DER
          eckey_set1_tls_encodedpoint,
          eckey_get1_tls_encodedpoint,
          eckey_opaque,
          int_ec_size,
          ec_bits,
          ec_missing_parameters,
          ec_copy_parameters, // 拷贝 ECC 秘钥参数
          ec_cmp_parameters,  // 比较 ECC 秘钥参数
          int_ec_free,
      };
      ```
    
      其中`ec_pkey_meth`的类型为`EVP_PKEY_METHOD`, 作为`EVP_PKEY`的操作方法, 记录在`EVP_PKEY_CTX.pmeth`
    
      ```c
      const EVP_PKEY_METHOD ec_pkey_meth = {
          EVP_PKEY_EC,
          pkey_ec_init,
          pkey_ec_copy,
          pkey_ec_cleanup,
          pkey_ec_keygen, // 生成 ECC 秘钥
          pkey_ec_sign, // 使用 EC-PrivateKey 执行签名
          pkey_ec_verify, // 使用 EC-PublicKey 验证签名
          pkey_ec_derive, // 使用 EC-PrivateKey 进行 ECDH
          pkey_ec_paramgen,
          pkey_ec_ctrl,
      };
      ```
    
    * `EVP_PKEY.pkey`被设置为`EC_KEY` ,其中:
      
      * `EC_KEY.ecdsa_meth`被设置为上文提及的: `g_ecdsa_method`, 其中:
        * `EC_KEY.ecdsa_meth->sign`为`EcdsaMethodSign()`
        * `EC_KEY.ecdsa_meth->flags`为`ECDSA_FLAG_OPAQUE`
      * `EC_KEY.ex_data.sk`被设置为上文体积的: `KeyExData`结构体
  
* 调用`NativeCrypto.setLocalCertsAndPrivateKey()`设置上文获取的`X509Certificate`(转换到`byte[][]`)和`OpenSSLKey`到底层

* 接下来看`NativeCrypto.setLocalCertsAndPrivateKey`, 改函数对应: `NativeCrypto_setLocalCertsAndPrivateKey()`:
  * 获取`SSL`结构体
  * 通过`fromContextObject()`获取上层的`EVP_PKEY`结构体(从上文提及的`OpenSSLKey.ctx`中获取)
  * 依次获取上层传递的证书数据到`CRYPTO_BUFFER`结构体
  * 通过`SSL_set_chain_and_key() -> cert_set_chain_and_key()`:
    * 通过`check_leaf_cert_and_privkey()`检查私钥与证书是否配对, 这里需要注意的是, 其中的一个检查步骤为`ssl_compare_public_and_private_key()`, 该函数中做了如下逻辑:
      ```c
        if (EVP_PKEY_is_opaque(privkey)) {
          // We cannot check an opaque private key and have to trust that it
          // matches.
          return true;
        }
      ```
      这里因为`EVP_PKEY.ameth->pkey_opaque`为`ec_asn1_meth.pkey_opaque`也就是`eckey_opaque`该函数通过`eckey_opaque()`判断`EVP_PKEY.pkey`也就是`EC_KEY`中的`ECDSA_METHOD.flags`是否设置了`ECDSA_FLAG_OPAQUE`, 上文提到`EC_KEY.ecdsa_meth.flags`已经设置了`ECDSA_FLAG_OPAQUE`, 所以这里不会报错
      * 将`std::vector<CRYPTO_BUFFER*>`的证书信息和`EVP_PKEY`的私钥信息配置给`SSL`结构体, 这里:
      * `SSL.config->cert->chain`保存数个`CRYPTO_BUFFER`
      * `SSL.config->cert->privatekey`保存`EVP_PKEY`
      * `SSL.config->cert->key_method`设置为空

## state_send_client_certificate_verify(12)
执行`do_send_client_certificate_verify() -> ssl_private_key_sign()`中:
* 执行`setup_ctx() -> EVP_DigestSignInit() -> do_sigver_init() -> EVP_PKEY_CTX_new()`, 因为`EVP_PKEY.ameth->pkey_method`为`ec_asn1_meth.pkey_method`, 即`ec_pkey_meth`, 因此创建的`EVP_PKEY_CTX.pmeth`为`ec_pkey_meth`, 创建的`EVP_MD_CTX`在`do_sigver_init()`中设置到`EVP_MD_CTX.pctx`
* 执行`EVP_DigestSign() -> EVP_DigestSignFinal() -> EVP_PKEY_sign() -> EVP_PKEY.pmeth->sign`, 即上一步骤提及的`ec_pkey_meth.sign`即`pkey_ec_sign()`, 该方法先 从`EVP_PKEY`获取`EC_KEY`, 然后调用`ECDSA_sign()`, 传入`EC_KEY`, 如果设置了`EC_KEY.ecdsa_meth->sign`方法, 则调用, 如上文, 这里调用`EcdsaMethodSign()`:
  * 通过`EcKeyGetKey() -> EC_KEY_get_ex_data`从`EC_KEY`中获取`KeyExData`结构体中的`PrivateKey`对象对应的`jobject`
  * 调用`ecSignDigestWithPrivateKey()`, 并将上一步骤获取的`PrivateKey`对象以及签名数据做为参数, 对应的上层调用为: `CryptoUpcalls.ecSignDigestWithPrivateKey() -> signDigestWithPrivateKey()`:
    * 首先通过`Signature.getInstance()`获取默认签名算法, 然后调用`Signature.initSign()`设置`PrivateKey`, 执行 `Signature.update()`更新签名数据后, 执行`Signature.sign()`进行签名. 这里的 `Signature`和上层自定义的`PrivateKey`是配套的, 这部分内容, 在后续介绍 `Security.Provider`时再介绍.

## state_complete_second_flight(13)

调用`do_complete_second_flight()`:

* 调用`tls13_add_finished()`发送协商结束消息
* 调用`tls13_set_traffic_key()`设置`SSL_HANDSHAKE.client_traffic_secret_0_`为新的会话密钥

## state_done(14, TLSv1.3 end)

## state_finish_client_handshake(TLS)

调用`do_finish_client_handshake()`, 这里将`SSL.s3->established_session`设置为`SSL.session`

# 加密与解密
## SSLOutputStream.write() 时的加密

上层调用: `SSLOutputStream.write() -> writeInternal() -> ConscryptEngine.wrap()`, `ConscryptEngine.wrap()`的语义是: 明文到加密数据的: **加密**, 分两个步骤:  
* 首先是`writePlaintextData() -> writePlaintextDataHeap() -> writePlaintextDataDirect()`将数据往`NativeSsl`写, 更底层的操作是`NativeCrypto.ENGINE_SSL_write_direct()`
* 然后是`readEncryptedData() -> readEncryptedDataDirect()`从`BioWrapper`读取数据, 更底层的操作是`NativeCrypto.ENGINE_SSL_read_BIO_direct()`

从这里也可以总结出: 对于加密数据, 统一由 `BioWrapper`传递, 对于明文数据, 统一通过`NativeSsl`直接传递, 这里的`BioWrapper`也是后续 MTLS 协商结束后的 AES 加密通道.
```c++
NativeCrypto.ENGINE_SSL_write_direct() -> 
    NativeCrypto_ENGINE_SSL_write_direct() [libjavacrypto.so] -> 
        ::SSL_write() [libssl.so]
```
此处, `SSL.method->write_app_data`为`kTLSProtocolMethod`中的`tls_write_app_data()`, 因此
```c++
    ::SSL_write() [libssl.so] -> 
        bssl::tls_write_app_data() ->
            bssl::do_tls_write()
```
此处分两个步骤:
* 首先处理数据的加密:`bssl::do_tls_write() -> bssl::tls_seal_record() -> bssl::tls_seal_scatter_record() -> bssl::do_seal_record()`, 此处`SSL.s3->aead_write_ctx`为: `SSLAEADContext`, 因此:`bssl::SSLAEADContext::SealScatter()`被调用, 这里的`ctx_`为`EVP_AEAD_CTX`, 而`EVP_AEAD_CTX.aead`为`EVP_aead_aes_256_gcm_tls13`, 因此`EVP_AEAD_CTX.aead->seal_scatter`为`aead_aes_gcm_tls13_seal_scatter() [libcrypto.so]`, 这里有硬件加速的部分, 简单列出调用的堆栈, 具体细节本文不做讨论:
```c
    EVP_AEAD_CTX_seal_scatter() [libcrypto.so] ->
        aead_aes_gcm_tls13_seal_scatter() ->
            aead_aes_gcm_seal_scatter() ->
                aead_aes_gcm_seal_scatter_impl() ->
                    CRYPTO_gcm128_encrypt()
```
* 然后处理数据的发送: `bssl::do_tls_write() -> bssl::tls_seal_record() -> bssl::tls_seal_scatter_record() -> bssl::ssl_write_buffer_flush() -> tls_write_buffer_flush() -> BIO_write()`, 将`ssl.s3->write_buffer`数据写入到`SSL.wbio`的`BIO`中, 如前文所述, 该`BIO`即`internal_bio`, 其关联的对象为`network_bio`, 至此上层就可以通过`NativeCrypto.ENGINE_SSL_read_BIO_direct()`读取到数 BoringSSL 需要发送的数据了.
```c++
NativeCrypto.ENGINE_SSL_read_BIO_direct() ->
    NativeCrypto_ENGINE_SSL_read_BIO_direct() [libjavacrypto.so] -> 
        ::BIO_read() ->
            bio_read() [external/boringssl/src/crypto/bio/pair.c]
```
这里从`network_bio`读取`internal_bio`的加密数据.

## SSLInputStream.read() 时的解密

上层调用: `SSLInputStream.read() -> readUntilDataAvailable() -> processDataFromSocket() -> ConscryptEngine.unwrap()`, `ConscryptEngine.unwrap()`的语义是: 加密数据到明文的: **解密**, ,`unwrap()`分两个步骤进行:
    * 首先是`writeEncryptedData() -> writeEncryptedDataHeap() -> writeEncryptedDataDirect()`将数据往`BioWrapper`写, 更底层的操作是`NativeCrypto.ENGINE_SSL_write_BIO_direct()`
        * 然后是`readPlaintextData() -> readPlaintextDataDirect()`从`NativeSsl`读取数据, 更底层的操作是`NativeCrypto.ENGINE_SSL_read_direct()`

```c++
NativeCrypto.ENGINE_SSL_write_BIO_direct() ->
    NativeCrypto_ENGINE_SSL_write_BIO_direct() [libjavacrypto.so] -> 
        ::BIO_write() ->
            bio_write() [external/boringssl/src/crypto/bio/pair.c]
```
这里通过`network_bio`写入加密数据到`internal_bio`

```c++
NativeCrypto.ENGINE_SSL_read_direct() ->
    NativeCrypto_ENGINE_SSL_read_direct() [libjavacrypto.so] -> 
        ::SSL_read() ->
            ::SSL_peek() ->
                ssl_read_impl()
```
这里开始分两部分:
* 首先处理数据的读取, 从`BIO`中读取上层写入的加密数据
```c
ssl_read_impl() ->
    bssl::ssl_handle_open_record() ->
        bssl::ssl_read_buffer_extend_to() ->
            tls_read_buffer_extend_to() ->
                BIO_read() [libcrypto.so] ->
                    bio_read()
```
* 然后处理数据的解密, `ssl_read_impl() -> tls_open_app_data() -> tls_open_record()`, 此处`SSL.s3->aead_read_ctx`为: `SSLAEADContext`, 因此:`bssl::SSLAEADContext::Open() -> EVP_AEAD_CTX_open() -> EVP_AEAD_CTX_open_gather()`被调用, 这里的`ctx_`为`EVP_AEAD_CTX`, 而`EVP_AEAD_CTX.aead`为`EVP_aead_aes_256_gcm_tls13`, 因此`EVP_AEAD_CTX.aead->open_gather`为`aead_aes_gcm_open_gather() [libcrypto.so]`, 这里有硬件加速的部分, 简单列出调用的堆栈, 具体细节本文不做讨论:
```c++
bssl::tls_open_record() ->
    bssl::SSLAEADContext::Open() ->
        EVP_AEAD_CTX_open() ->
            EVP_AEAD_CTX_open_gather() ->
                aead_aes_gcm_open_gather_impl() ->
                    CRYPTO_gcm128_decrypt_ctr32()
```
