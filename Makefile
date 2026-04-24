CC      = gcc
CFLAGS  = -O2 -Wall -shared -fPIC
TARGET  = libtuncore.so

$(TARGET): tun_core.c
	$(CC) $(CFLAGS) -o $(TARGET) tun_core.c

clean:
	rm -f $(TARGET)
