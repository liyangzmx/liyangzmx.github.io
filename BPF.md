# Android S下的eBPF

测试条件:
* 设备: Google Pixel 3 XL
* AOSP: android-12.0.0_r3

参考资料: 
* [使用 eBPF 扩展内核](https://source.android.com/devices/architecture/kernel/bpf)
* [eBPF 流量监控](https://source.android.com/devices/tech/datausage/ebpf-traffic-monitor)

准备路径`external/bpf_test`  
准备源码文件`external/bpf_test/bpf_test.c`:
```
#include <linux/bpf.h>
#include <stdbool.h>
#include <stdint.h>
#include <bpf_helpers.h>

DEFINE_BPF_MAP(cpu_pid_map, ARRAY, int, uint32_t, 1024);

struct switch_args {
    unsigned long long ignore;
    char prev_comm[16];
    int prev_pid;
    int prev_prio;
    long long prev_state;
    char next_comm[16];
    int next_pid;
    int next_prio;
};

// SEC("tracepoint/sched/sched_switch")
DEFINE_BPF_PROG("tracepoint/sched/sched_switch", AID_ROOT, AID_NET_ADMIN, tp_sched_switch) (struct switch_args* args) {
// int tp_sched_switch(struct switch_args* args) {
    int key;
    uint32_t val;

    key = bpf_get_smp_processor_id();
    val = args->next_pid;

    bpf_cpu_pid_map_update_elem(&key, &val, BPF_ANY);
    return 0;
}

// char _license[] SEC("license") = "GPL";
LICENSE("Apache 2.0");
```

准备客户端文件`external/bpf_test/bpf_cli.cpp`:
```
#include <android-base/macros.h>
#include <stdlib.h>
#include <unistd.h>
#include <iostream>
#include <bpf/BpfMap.h>
#include <bpf/BpfUtils.h>
#include <libbpf_android.h>

int main() {
	constexpr const char tp_prog_path[] = "/sys/fs/bpf/prog_bpf_test_tracepoint_sched_sched_switch";
	constexpr const char tp_map_path[] = "/sys/fs/bpf/map_bpf_test_cpu_pid_map";
	// Attach tracepoint and wait for 4 seconds
	int mProgFd = bpf_obj_get(tp_prog_path);
	// int mMapFd = bpf_obj_get(tp_map_path);
	bpf_attach_tracepoint(mProgFd, "sched", "sched_switch");
	sleep(1);
	android::bpf::BpfMap<int, int> myMap(tp_map_path);

	while(1) {
		usleep(40000);

		// Read the map to find the last PID that ran on CPU 0
		// android::bpf::BpfMap<int, int> myMap(mMapFd);
		printf("last PID running on CPU %d is %d\n", 0, *myMap.readValue(0));
	}

	exit(0);
}
```

准备`external/bpf_test/Android.bp`:
```
bpf {
    name: "bpf_test.o",
    srcs: ["bpf_test.c"],
    cflags: [
        "-Wall",
        "-Werror",
    ],
}

cc_binary {
    name: "bpf_cli",

    cflags: [
        "-Wall",
        "-Werror",
        "-Wthread-safety",
    ],
    clang: true,
    shared_libs: [
        "libcutils",
        "libbpf_android",
        "libbase",
        "liblog",
        "libnetdutils",
        "libbpf",
    ],
    srcs: [
        "bpf_cli.cpp",
    ],
}
```

编译执行:
```
$ source build/envsetup.sh; lunch aosp_crosshatch-userdebug
$ m bpf_test.o
$ m bpf_cli
```

推送文件到手机:
```
$ adb root
$ adb remount
$ adb push out/target/product/crosshatch/system/etc/bpf/bpf_test.o /system/etc/bpf/
$ adb shell bpfloader
$ adb out/target/product/crosshatch/system/bin/bpf_cli /data/
```

此时查看`/sys/fs/bpf/`目录:
```
$ adb shell ls /sys/fs/bpf/*bpf_test*
/sys/fs/bpf/map_bpf_test_cpu_pid_map
/sys/fs/bpf/prog_bpf_test_tracepoint_sched_sched_switch
```

然后执行BPF测试程序:
```
$ adb shell /data/bpf_cli
last PID running on CPU 0 is 4371
last PID running on CPU 0 is 4371
last PID running on CPU 0 is 4371
... ....
last PID running on CPU 0 is 4371
last PID running on CPU 0 is 1833
last PID running on CPU 0 is 0
... ...
```