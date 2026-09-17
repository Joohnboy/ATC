"""
Probe the RTL2832U I2C bus via raw USB control transfers.
Tells us exactly what tuner chip is present and at what address.
"""
import usb.core
import usb.backend.libusb1 as lb1
import os, sys, ctypes, time

APP = os.path.dirname(os.path.abspath(__file__))
os.add_dll_directory(APP)

BACKEND = lb1.get_backend(find_library=lambda x: os.path.join(APP, "libusb-1.0.dll"))

VID, PID = 0x10FD, 0x1513
CTRL_TIMEOUT = 300
CTRL_IN  = 0xC0   # vendor | device-to-host
CTRL_OUT = 0x40   # vendor | host-to-device

def ctrl(dev, write, request, value, index, data_or_len):
    if write:
        return dev.ctrl_transfer(CTRL_OUT, request, value, index, data_or_len, CTRL_TIMEOUT)
    else:
        return dev.ctrl_transfer(CTRL_IN,  request, value, index, data_or_len, CTRL_TIMEOUT)

def write_reg(dev, block, addr, val, length=1):
    index = (block << 8) | 0x10
    buf = [(val >> 8) & 0xFF, val & 0xFF] if length == 2 else [val & 0xFF]
    ctrl(dev, True, 0, addr, index, buf)

def read_reg(dev, block, addr, length=1):
    index = block << 8
    return ctrl(dev, False, 0, addr, index, length)

def i2c_write(dev, i2c_addr, data):
    """Write bytes to I2C device."""
    index = i2c_addr
    try:
        ctrl(dev, True, 0, 0, index, list(data))
        return True
    except Exception:
        return False

def i2c_read(dev, i2c_addr, reg, length=1):
    """Read register from I2C device."""
    # First write the register address
    try:
        ctrl(dev, True, 0, reg, i2c_addr, [])
    except Exception:
        pass
    try:
        result = ctrl(dev, False, 0, 0, i2c_addr, length)
        return bytes(result)
    except Exception:
        return None

def init_rtl2832u(dev):
    """Minimal initialisation to enable I2C master."""
    # USB suspend fix
    write_reg(dev, 0, 0x0100, 0x01, 1)  # SYS_DEMOD_CTL = RESETPLL
    # Enable I2C repeater (gate between RTL and tuner)
    write_reg(dev, 1, 0x01, 0x18, 1)

def main():
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=BACKEND)
    if dev is None:
        print("Device not found")
        return

    print(f"Found: {dev.manufacturer or '?'} / {dev.product or '?'}")
    print(f"USB speed class: {dev.speed if hasattr(dev,'speed') else 'unknown'}")

    try:
        dev.set_configuration()
    except Exception as e:
        print(f"set_configuration: {e}")

    try:
        dev.detach_kernel_driver(0)
    except Exception:
        pass

    print("\nInitialising RTL2832U demodulator...")
    try:
        init_rtl2832u(dev)
    except Exception as e:
        print(f"  init error (may be benign): {e}")

    # Known tuner I2C addresses (7-bit)
    KNOWN = {
        0x10: "E4000 @ 0x10",
        0x1a: "R820T/R820T2 @ 0x1A",
        0x1c: "R828D @ 0x1C",
        0x60: "FC0012 @ 0x60",
        0x61: "FC0012 @ 0x61",
        0xac: "FC0013 @ 0xAC",
        0xad: "FC0013 @ 0xAD",
        0x56: "FC2580 @ 0x56",
        0x58: "MXL5005S @ 0x58",
        0x60: "MT2063 @ 0x60",
    }

    print("\nScanning I2C bus (0x00 – 0x7F)...")
    responding = []
    for addr in range(0x00, 0x80):
        try:
            # Try a 1-byte read from register 0x00
            result = ctrl(dev, False, 0, 0x00, addr, 1)
            val = result[0] if result else -1
            label = KNOWN.get(addr, "")
            print(f"  0x{addr:02X}  →  0x{val:02X}  {label}")
            responding.append((addr, val))
        except Exception:
            pass

    if not responding:
        print("  (no I2C devices responded)")
    else:
        print(f"\n{len(responding)} device(s) found on I2C bus.")

    # Specifically probe R820T2 chip ID register
    print("\nChecking R820T2 chip ID register 0x00 directly...")
    for addr in [0x1a, 0x1b, 0x34, 0x35]:
        try:
            result = ctrl(dev, False, 0, 0x00, addr, 1)
            print(f"  addr 0x{addr:02X} reg0 = 0x{result[0]:02X}")
        except Exception as e:
            print(f"  addr 0x{addr:02X} → error ({e})")

    dev.reset()

if __name__ == "__main__":
    main()
