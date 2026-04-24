#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/if_tun.h>
#include "tun_core.h"

int tun_open(const char *dev_name) {
    struct ifreq ifr;
    int fd, err;

    // 1. 開啟 /dev/net/tun 字元裝置
    if ((fd = open("/dev/net/tun", O_RDWR)) < 0) {
        perror("open /dev/net/tun");
        return -1;
    }

    // 2. 設定 IFF_TUN（L3 IP 封包，無乙太網頭）
    //    IFF_NO_PI：不附加 4-byte 協定資訊頭
    memset(&ifr, 0, sizeof(ifr));
    ifr.ifr_flags = IFF_TUN | IFF_NO_PI;
    if (dev_name && *dev_name)
        strncpy(ifr.ifr_name, dev_name, IFNAMSIZ - 1);

    // 3. ioctl TUNSETIFF 向核心登記介面
    if ((err = ioctl(fd, TUNSETIFF, &ifr)) < 0) {
        perror("ioctl TUNSETIFF");
        close(fd);
        return -1;
    }

    printf("[tun] opened: %s (fd=%d)\n", ifr.ifr_name, fd);
    return fd;
}

int tun_read(int fd, uint8_t *buf, int len) {
    int n = read(fd, buf, len);
    if (n < 0) perror("tun_read");
    return n;
}

int tun_write(int fd, const uint8_t *buf, int len) {
    int n = write(fd, buf, len);
    if (n < 0) perror("tun_write");
    return n;
}

void tun_close(int fd) {
    close(fd);
}
