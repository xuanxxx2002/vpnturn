
"""
Server 端：
  - 監聽 UDP socket（公網）
  - 解密收到的封包
  - 透過 tun_write() 注入 Linux 核心網路堆疊
  - 同時從 TUN 讀取回程封包，加密後送回 Client
"""
import ctypes, socket, select, sys
from crypto import derive_key, encrypt_packet, decrypt_packet

TUN_DEV   = "tun0"
LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 51820
MTU       = 1500
PSK       = b"my-super-secret-pre-shared-key!!"   # 32 bytes

# --- 載入 C 共享函式庫 ---
lib = ctypes.CDLL("./libtuncore.so")
lib.tun_open.restype  = ctypes.c_int
lib.tun_read.restype  = ctypes.c_int
lib.tun_write.restype = ctypes.c_int

def main():
    key = derive_key(PSK)
    tun_fd = lib.tun_open(TUN_DEV.encode())
    if tun_fd < 0:
        sys.exit("Failed to open TUN device (run as root?)")

    # 自動設定 TUN IP（呼叫 ip 指令）
    import subprocess
    subprocess.run(["ip", "addr", "add", "10.8.0.2/24", "dev", TUN_DEV])
    subprocess.run(["ip", "link", "set", TUN_DEV, "up"], check=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    print(f"[server] listening on :{LISTEN_PORT}, tun_fd={tun_fd}")

    buf = ctypes.create_string_buffer(MTU)
    peer_addr = None

    while True:
        r, _, _ = select.select([sock.fileno(), tun_fd], [], [])

        if sock.fileno() in r:
            # 收到來自 Client 的加密封包
            data, addr = sock.recvfrom(MTU + 28)  # 12 nonce + 16 tag + MTU
            peer_addr = addr
            try:
                plain = decrypt_packet(key, data)
                lib.tun_write(tun_fd, plain, len(plain))
                print(f"[server] ← {len(plain)}B decrypted from {addr}")
            except Exception as e:
                print(f"[server] decrypt error: {e}")

        if tun_fd in r:
            # TUN 有封包要送回 Client
            n = lib.tun_read(tun_fd, buf, MTU)
            if n > 0 and peer_addr:
                enc = encrypt_packet(key, bytes(buf[:n]))
                sock.sendto(enc, peer_addr)
                print(f"[server] → {n}B encrypted to {peer_addr}")

if __name__ == "__main__":
    main()
