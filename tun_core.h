#pragma once
#include <stdint.h>

#define TUN_MTU 1500

int  tun_open(const char *dev_name);   // 開啟或建立 TUN 介面，回傳 fd
int  tun_read(int fd, uint8_t *buf, int len);
int  tun_write(int fd, const uint8_t *buf, int len);
void tun_close(int fd);
