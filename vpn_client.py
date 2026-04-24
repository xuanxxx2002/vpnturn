# vpn_client.py
"""
Client 端：
  - 從 TUN 讀取應用程式封包
  - AES-256-GCM 加密
  - 透過 UDP 送往 Server
  - 接收 Server 回程封包，解密後注入 TUN
"""
import ctypes, socket, select, sys
from crypto import derive_key, encrypt_packet, decrypt_packet

TUN_DEV     = "tun1"
SERVER_IP = "127.0.0.1"
SERVER_PORT = 51820
MTU         = 1500
PSK         = b"my-super-secret-pre-shared-key!!"

lib = ctypes.CDLL("./libtuncore.so")
lib.tun_open.restype  = ctypes.c_int
lib.tun_read.restype  = ctypes.c_int
lib.tun_write.restype = ctypes.c_int

def main():
    key = derive_key(PSK)
    tun_fd = lib.tun_open(TUN_DEV.encode())
    if tun_fd < 0:
        sys.exit("Failed to open TUN device (run as root?)")

    import subprocess
    subprocess.run(["ip", "addr", "add", "10.8.0.1/24", "dev", TUN_DEV])
    subprocess.run(["ip", "link", "set", TUN_DEV, "up"], check=True)
    # 將目標網段路由到 TUN（按需調整）
    subprocess.run(["ip", "route", "add", "10.8.0.0/24", "dev", TUN_DEV])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (SERVER_IP, SERVER_PORT)
    print(f"[client] → {server_addr}, tun_fd={tun_fd}")

    buf = ctypes.create_string_buffer(MTU)

    while True:
        r, _, _ = select.select([tun_fd, sock.fileno()], [], [])

        if tun_fd in r:
            n = lib.tun_read(tun_fd, buf, MTU)
            if n > 0:
                enc = encrypt_packet(key, bytes(buf[:n]))
                sock.sendto(enc, server_addr)
                print(f"[client] → {n}B encrypted")

        if sock.fileno() in r:
            data, _ = sock.recvfrom(MTU + 28)
            try:
                plain = decrypt_packet(key, data)
                lib.tun_write(tun_fd, plain, len(plain))
                print(f"[client] ← {len(plain)}B decrypted")
            except Exception as e:
                print(f"[client] decrypt error: {e}")

if __name__ == "__main__":
    main()
