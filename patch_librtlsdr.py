"""Patch librtlsdr.c to add GPIO brute-force tuner detection for rebadged devices."""
import re, sys

src = open("/tmp/rtl-sdr-patched/src/librtlsdr.c").read()

# The code we want to insert: after the R828D probe and BEFORE the GPIO4 block,
# try toggling GPIO 0-7 to power on R820T (for devices that need non-standard GPIO)
INSERTION_MARKER = "/* initialise GPIOs */"
FALLBACK = r"""
	/* Fallback: brute-force GPIO power search for rebadged RTL2832U devices.
	 * Some devices (e.g. GeCube LR538, VID 10FD) require a non-standard
	 * GPIO pin to be driven high before the R820T tuner responds on I2C. */
	{
		int gp;
		for (gp = 0; gp <= 7; gp++) {
			rtlsdr_set_gpio_output(dev, gp);
			rtlsdr_set_gpio_bit(dev, gp, 1);
			/* small delay to allow tuner power rail to settle */
#ifdef _WIN32
			Sleep(30);
#else
			usleep(30000);
#endif
			reg = rtlsdr_i2c_read_reg(dev, R820T_I2C_ADDR, R82XX_CHECK_ADDR);
			if (reg == R82XX_CHECK_VAL) {
				fprintf(stderr, "Found Rafael Micro R820T tuner (powered via GPIO%d)\n", gp);
				dev->tuner_type = RTLSDR_TUNER_R820T;
				goto found;
			}
			/* also try R828D address */
			reg = rtlsdr_i2c_read_reg(dev, R828D_I2C_ADDR, R82XX_CHECK_ADDR);
			if (reg == R82XX_CHECK_VAL) {
				fprintf(stderr, "Found Rafael Micro R828D tuner (powered via GPIO%d)\n", gp);
				dev->tuner_type = RTLSDR_TUNER_R828D;
				goto found;
			}
			/* de-assert before trying next pin */
			rtlsdr_set_gpio_bit(dev, gp, 0);
		}
	}

"""

if INSERTION_MARKER not in src:
    print("ERROR: marker not found in source")
    sys.exit(1)

patched = src.replace(INSERTION_MARKER, FALLBACK + "\t" + INSERTION_MARKER, 1)

# Also add windows.h include for Sleep() if not already included
if "#include <windows.h>" not in patched:
    patched = patched.replace("#ifdef _WIN32\n#include <windows.h>",
                               "#ifdef _WIN32\n#include <windows.h>", 1)
    # Add our own include near the top if the block exists differently
    if "ifdef _WIN32" in patched and "windows.h" not in patched:
        patched = patched.replace('#include "rtl-sdr.h"',
                                   '#include "rtl-sdr.h"\n#ifdef _WIN32\n#include <windows.h>\n#endif', 1)

open("/tmp/rtl-sdr-patched/src/librtlsdr.c", "w").write(patched)
print("Patch applied. Lines with GPIO fallback:")
for i, line in enumerate(patched.splitlines(), 1):
    if "GPIO" in line and "tuner" in line.lower():
        print(f"  {i}: {line}")
