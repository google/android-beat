load("//devtools/bettertogether/feature/bluetooth:bluetooth_integration_test.bzl", "bluetooth_integration_test")
load("//devtools/python/blaze:pytype.bzl", "pytype_strict_library")

pytype_strict_library(
    name = "utils",
    srcs = glob(["*_utils.py"]),
    deps = [
        "//devtools/bettertogether/feature/bluetooth/git/platforms/bluetooth:tws_device",
        "//third_party/py/mobly",
        "//third_party/py/tenacity",
    ],
)

pytype_strict_library(
    name = "base_test",
    srcs = ["base_test.py"],
    deps = [
        ":utils",
        "//devtools/bettertogether/feature/bluetooth/git/platforms/bluetooth:bluetooth_reference_device",
        "//devtools/bettertogether/feature/bluetooth/git/platforms/bluetooth:tws_device",
        "//third_party/py/mobly",
    ],
)

# blaze test --notest_loasd //devtools/bettertogether/feature/bluetooth/git:bluetooth_lea_media_streaming
bluetooth_integration_test(
    name = "bluetooth_lea_media_streaming",
    srcs = ["bluetooth_lea_media_streaming.py"],
    files = {
        "media_files": ["//devtools/bettertogether/feature/bluetooth/res:pixel_ringtone.wav"],
    },
    mh_devices = [
        (
            "AndroidRealDevice",
            {
                "uuid": "3B021FDAS000FC",
                "owner": "bluetooth",
            },
            [],
        ),
        (
            "TestbedDevice",
            {
                "uuid": "beto-cm-12-16-01-bt-tws-rpi-02",
                "owner": "bluetooth",
            },
            [],
        ),
    ],
    deps = [
        ":base_test",
        ":utils",
        "//third_party/py/mobly",
    ],
)
