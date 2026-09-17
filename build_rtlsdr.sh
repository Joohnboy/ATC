#!/bin/bash
export PATH="/mingw64/bin:/usr/bin:$PATH"
set -e
cd /tmp/rtl-sdr-patched
git checkout src/librtlsdr.c

# Patch 1: add GeCube VID:PID
sed -i 's/{ 0x0bda, 0x2832,/{ 0x10fd, 0x1513, "GeCube LR538 (RTL2832U)" },\n\t{ 0x0bda, 0x2832,/' src/librtlsdr.c

# Patch 2: export an I2C gate open function so Python can force-enable it
# Insert before the final #endif in the C file
cat >> src/librtlsdr.c << 'CPATCH'

/* Exported helper: force the I2C repeater gate open for external I2C scanning */
RTLSDR_API void rtlsdr_open_i2c_gate(rtlsdr_dev_t *dev)
{
    if (dev)
        rtlsdr_set_i2c_repeater(dev, 1);
}
CPATCH

# Also add the declaration to the public header
sed -i 's|RTLSDR_API int rtlsdr_set_bias_tee|RTLSDR_API void rtlsdr_open_i2c_gate(rtlsdr_dev_t *dev);\nRTLSDR_API int rtlsdr_set_bias_tee|' include/rtl-sdr.h

echo "Patches applied"
grep "10fd\|open_i2c_gate" src/librtlsdr.c | head -5

cd build
mingw32-make -j4 rtlsdr 2>&1 | tail -4
cp src/librtlsdr.dll /c/Users/JohnGetley/ATC/librtlsdr.dll
cp src/librtlsdr.dll /c/Users/JohnGetley/ATC/rtlsdr.dll
echo "DONE"
