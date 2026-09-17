import os, ctypes
os.add_dll_directory(os.path.dirname(os.path.abspath(__file__)))
lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rtlsdr.dll"))

dev_p = ctypes.c_void_p()
r = lib.rtlsdr_open(ctypes.byref(dev_p), 0)
print(f"open: {r}  handle: {dev_p.value}")
if r != 0:
    raise SystemExit("open failed")

TUNER_NAMES = {0:"UNKNOWN",1:"E4000",2:"FC0012",3:"FC0013",4:"FC2580",5:"R820T",6:"R828D"}
t = lib.rtlsdr_get_tuner_type(dev_p)
print(f"tuner_type: {t} ({TUNER_NAMES.get(t,'?')})")

# Force I2C gate open before scanning
lib.rtlsdr_open_i2c_gate(dev_p)
print("I2C gate forced open")

lib.rtlsdr_i2c_read_fn.restype  = ctypes.c_int
lib.rtlsdr_i2c_write_fn.restype = ctypes.c_int
rbuf = (ctypes.c_uint8 * 4)()
wbuf = (ctypes.c_uint8 * 1)(0x00)  # register 0x00
found = []
for addr in range(0, 0x80):
    lib.rtlsdr_open_i2c_gate(dev_p)
    # Write reg address 0x00 then read 1 byte — same sequence librtlsdr uses for tuner probe
    lib.rtlsdr_i2c_write_fn(dev_p, addr, wbuf, 1)
    r2 = lib.rtlsdr_i2c_read_fn(dev_p, addr, rbuf, 1)
    if r2 == 1:
        found.append((addr, rbuf[0]))

KNOWN = {
    0x10: "E4000",
    0x1a: "R820T / R820T2",
    0x1c: "R828D",
    0x60: "FC0012 / MT2063",
    0xac: "FC0013",
    0x56: "FC2580",
    0x50: "EEPROM (24C02)",
}
if found:
    print("I2C devices responding:")
    for addr, val in found:
        label = KNOWN.get(addr, "unknown")
        print(f"  addr=0x{addr:02X}  reg0=0x{val:02X}  -> {label}")
else:
    print("No I2C devices responded at any address 0x00-0x7F")

lib.rtlsdr_close(dev_p)
