"""Full USB descriptor dump — all interfaces and alternate settings."""
import os
import usb.core, usb.backend.libusb1 as lb1

APP = os.path.dirname(os.path.abspath(__file__))
BACKEND = lb1.get_backend(find_library=lambda x: os.path.join(APP, "libusb-1.0.dll"))

dev = usb.core.find(idVendor=0x10FD, idProduct=0x1513, backend=BACKEND)
print(f"Manufacturer : {dev.manufacturer!r}")
print(f"Product      : {dev.product!r}")
print(f"bcdDevice    : 0x{dev.bcdDevice:04X}")

XFER = {0:"CTRL", 1:"ISO", 2:"BULK", 3:"INT"}
for cfg in dev:
    print(f"\nConfig {cfg.bConfigurationValue}:")
    for intf in cfg:
        cls = intf.bInterfaceClass
        print(f"  Intf {intf.bInterfaceNumber} AlternateSetting {intf.bAlternateSetting}  "
              f"class=0x{cls:02X}  sub=0x{intf.bInterfaceSubClass:02X}  proto=0x{intf.bInterfaceProtocol:02X}  "
              f"nEP={intf.bNumEndpoints}")
        for ep in intf:
            d = "IN" if ep.bEndpointAddress & 0x80 else "OUT"
            t = XFER.get(ep.bmAttributes & 3, "?")
            print(f"    EP 0x{ep.bEndpointAddress:02X} {d} {t}  maxpkt={ep.wMaxPacketSize}")
