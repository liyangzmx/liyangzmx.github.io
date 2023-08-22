# Android Rust AIDL Tutorial

参考资料: https://source.android.com/docs/setup/build/rust/building-rust-modules/android-rust-patterns?hl=zh-cn#rust-aidl-example

创建目录`hardware/interfaces/foo/aidl`目录

创建`aidl`文件: `hardware/interfaces/foo/aidl/android/hardware/foo/IFoo.aidl`:
```
package android.hardware.foo;
@VintfStability
interface IFoo {
    void setState(in int id, in int status);
}
```

在`hardware/interfaces/foo/aidl/`下分别创建:
* `aidl_api/android.hardware.foo/1/`
* `aidl_api/android.hardware.foo/current/`

拷贝 `hardware/interfaces/foo/aidl/android/` 到上面创建的两个目录, 最后目录结构如下:
```
├── aidl_api
│   └── android.hardware.foo
│       ├── 1
│       │   └── android
│       │       └── hardware
│       │           └── foo
│       │               └── IFoo.aidl
│       └── current
│           └── android
│               └── hardware
│                   └── foo
│                       └── IFoo.aidl
└── android
    └── hardware
        └── foo
            └── IFoo.aidl
```
创建`Android.bp`文件:
```
package {
    default_applicable_licenses: ["hardware_interfaces_license"],
}

aidl_interface {
    name: "android.hardware.foo",
    vendor_available: true,
    srcs: [
        "android/hardware/foo/*.aidl",
    ],
    stability: "vintf",
    backend: {
        cpp: {
            enabled: true,
        },
        rust: {
            // By default, the Rust backend is not enabled
            enabled: true,
        },
        ndk: {
            vndk: {
                enabled: true,
            },
        },
    },
    versions: ["1"],
}
```
此时可以执行 `m android.hardware.foo` 编译 Rust 的接口层了

在 Android 源码目录创建 `external/rust/foo-server/`, 进一步创建`external/rust/foo-server/Android.bp`文件:
```
// must under external/rust, otherwise, error: "violates neverallow"

rust_defaults {
    name: "libfoo_defaults",
    srcs: ["src/lib.rs"],
    crate_name: "foo",
    rustlibs: [
        "libbinder_rs",
        "android.hardware.foo-V1-rust",
    ],
}

rust_library {
    name: "libfoo_rs",
    defaults: ["libfoo_defaults"],
}

rust_binary {
    name: "foo_service",
    relative_install_path: "hw",
    init_rc: ["foo-default-rust.rc"],
    vintf_fragments: ["foo-default-rust.xml"],
    // vendor: true,
    rustlibs: [
        "libbinder_rs",
        "liblog_rust",
        "android.hardware.foo-V1-rust",
        "libfoo_rs",
    ],
    srcs: [
        "src/main.rs",
    ],
}
```
注意, `foo-server`必须在 `external/rust/`, 否则会有 "violates neverallow" 的报错.

在`external/rust/foo-server/`目录下创建库代码, `src/lib.rs`:
```
//! This module implements the IFoo AIDL interface
use android_hardware_foo::aidl::android::hardware::foo::{
  IFoo::{BnFoo, IFoo}
};
use android_hardware_foo::binder::{
  BinderFeatures, Interface, Result as BinderResult, Strong,
};

/// This struct is defined to implement IFoo AIDL interface.
pub struct FooService;

impl Interface for FooService {}

impl IFoo for FooService {
  fn setState(&self, _arg_id: i32, _arg_status: i32) -> binder::public_api::Result<()> {
    Ok(())
  }
}
```

在`external/rust/foo-server/`目录下创建服务代码, `src/main.rs`:
```
use foo::FooService;
use android_hardware_foo::{ 
    binder::BinderFeatures,
    aidl::android::hardware::foo::IFoo::BnFoo,
    aidl::android::hardware::foo::IFoo::BpFoo,
    aidl::android::hardware::foo::IFoo::IFoo,
};
use log::{debug, error, info};

fn main() {
    // Initialize android logging.
    android_logger::init_once(
        android_logger::Config::default()
            .with_tag("foo-hal")
            .with_min_level(log::Level::Info)
            .with_log_id(android_logger::LogId::System),
    );

    // [...]
    let foo_service = FooService;
    let foo_service_binder = BnFoo::new_binder(
        foo_service,
        BinderFeatures::default(),
    );
    let versioned_service_name = <BpFoo as IFoo>::get_descriptor();
    binder::add_service("android.hardware.foo.IFoo/default", foo_service_binder.as_binder())
        // .expect("Failed to register service?");
        .unwrap_or_else(|e| {
            panic!("Failed to register service {} because of {:?}.", "foo_service", e);
        });
    // Does not return - spawn or perform any work you mean to do before this call.
    binder::ProcessState::join_thread_pool()
}
```

在`external/rust/foo-server/`目录下创建 `rc` 配置, `foo-default-rust.rc`:
```
service vendor.foo-default-rust /vendor/bin/hw/foo-rust-service
    class hal
    user nobody
    group nobody
    shutdown critical
```
在`external/rust/foo-server/`目录下创建 `VINTF` 配置, `foo-default-rust.rc`:
```
<manifest version="1.0" type="device">
    <hal format="aidl">
        <name>android.hardware.foo</name>
	<fqname>IFoo/default</fqname>
    </hal>
</manifest>
```

推送测试(假设文件系统已经`remount`):
```
adb remount
adb push /opt/work/xr_box_rk/out/target/product/rk3588_xrbox/system/bin/hw/foo_service /system/bin/hw/
adb push /opt/work/xr_box_rk/out/target/product/rk3588_xrbox/system/lib64/libfoo_rs.dylib.so /system/lib64/
adb push /opt/work/xr_box_rk/out/target/product/rk3588_xrbox/system/lib64/libandroid_hardware_foo_V1.dylib.so /system/lib64/
adb push /opt/work/xr_box_rk/external/rust/foo-server/foo-default-rust.xml /vendor/etc/vintf/manifest/andorid.hardware.foo.xml
adb push /opt/work/xr_box_rk/out/compatibility_matrix.device.xml2 /etc/vintf/compatibility_matrix.device.xml
adb reboot
```
一个`adb shell`执行: `/system/bin/hw/foo_service`
一个`adb shell`执行: 
```
# service list | grep foo
9	android.hardware.foo.IFoo/default: [android.hardware.foo.IFoo]

# service check android.hardware.foo.IFoo/default
Service android.hardware.foo.IFoo/default: found

# service call android.hardware.foo.IFoo/default 1 i32 1 i32 1
Result: Parcel(00000000    '....')
```