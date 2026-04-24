# vpntun — 簡易 VPN Tunnel（AES-256-GCM 加密）

以 **C + Python** 實作的點對點 VPN 通道，使用 Linux TUN/TAP 虛擬網路介面與 AES-256-GCM 認證加密。

學習目標：從核心層的 TUN 裝置 ioctl，到 userspace 封包轉發與密碼學，完整理解 VPN 的運作原理。

---

## 運作原理

```
應用程式（ping、SSH、HTTP...）
      ↓
Linux 核心 TCP/IP 堆疊
      ↓
TUN 虛擬網卡  ←──── vpn_client.py 讀取原始 IP 封包
      ↓                         ↓
      │                  AES-256-GCM 加密
      │                  （12B nonce + 密文 + 16B GCM tag）
      │                         ↓
      │                  UDP socket → Server
      │
      │         vpn_server.py 收到 UDP
      │                  ↓
      │           AES-256-GCM 解密 + 完整性驗證
      │                  ↓
      └──────── write() 注入 TUN → 核心交付封包
```

所有在網路上傳輸的位元組都經過加密與認證。攻擊者抓到 UDP 51820 的封包，只會看到無意義的亂碼——沒有明文 IP header，沒有可讀內容。

---

## 專案結構

```
vpntun/
├── tun_core.c       # C：透過 ioctl 開啟 TUN 裝置，讀寫封包
├── tun_core.h
├── vpn_server.py    # Python：監聽 UDP、解密、注入 TUN
├── vpn_client.py    # Python：從 TUN 讀取、加密、送出 UDP
├── crypto.py        # AES-256-GCM + HKDF 金鑰衍生
└── Makefile
```

---

## 環境需求

**系統**
- Linux kernel 3.x 以上（預設支援 TUN/TAP）
- Root 權限（`sudo`）——開啟 `/dev/net/tun` 與設定網路介面需要

**Python 套件**
```bash
pip install cryptography
```

**C 編譯器**
```bash
sudo apt install gcc make      # Debian / Ubuntu
sudo dnf install gcc make      # Fedora / RHEL
```

---

## 編譯

```bash
# 編譯 C 共享函式庫
make

# 確認產生成功
ls -lh libtuncore.so
```

---

## 快速開始（單機測試）

開三個終端機分別執行：

### 終端機 1 — Server
```bash
sudo python3 vpn_server.py
```
預期輸出：
```
[tun] opened: tun0 (fd=3)
[server] listening on :51820, tun_fd=3
```

### 終端機 2 — Client
```bash
sudo python3 vpn_client.py
```
預期輸出：
```
[tun] opened: tun1 (fd=3)
[client] → ('127.0.0.1', 51820), tun_fd=3
```

### 終端機 3 — 測試連通
```bash
ping 10.8.0.2
```
預期輸出：
```
64 bytes from 10.8.0.2: icmp_seq=1 ttl=64 time=0.06 ms
64 bytes from 10.8.0.2: icmp_seq=2 ttl=64 time=0.05 ms
```

> **注意**：同一台機器測試時，Server 使用 `tun0`，Client 必須改用 `tun1`（編輯 `vpn_client.py` 頂部的 `TUN_DEV`）。

---

## 兩台機器部署

**Server（機器 B）** 不需修改，直接執行：
```bash
sudo python3 vpn_server.py
```

**Client（機器 A）** 修改 `vpn_client.py`：
```python
SERVER_IP = "你的 Server 公網 IP"
TUN_DEV   = "tun0"    # 不同機器可以都叫 tun0
```

然後執行：
```bash
sudo python3 vpn_client.py
```

---

## 驗證加密效果

ping 進行中，同時抓 UDP 封包：

```bash
sudo tcpdump -i lo udp port 51820 -X -c 5
```

實際抓到的輸出範例：
```
17:48:38.572005 IP localhost.43837 > localhost.51820: UDP, length 76
        0x0020:  80e7 2210 d97f 028f 1622 7079  ← 12 bytes nonce（隨機）
        0x002c:  64eb 5545 1b3c 8800 2be8 9408  ← AES-256-GCM 密文
        0x003c:  cf27 a219 5b19 3625 3e72 c541
        0x004c:  f779 fdfc 2af5 f301 f1cd f95d
        0x005c:  8ff7 5ce7 ac2a 7ec8 8276 eaa7  ← 16 bytes GCM 驗證 tag
```

28 bytes 的 ICMP ping 在網路上變成 76 bytes：
```
28B 明文 + 12B nonce + 16B GCM tag = 56B payload
56B + 8B UDP header + 20B IP header = 76B 總長
```

沒有金鑰，任何人都無法還原原始內容。

---

## 封包格式

```
┌─────────────────────────────────────────────────────┐
│  UDP Payload（VPN 封包）                            │
├────────────────┬────────────────────────────────────┤
│  Nonce（12B）  │  密文 + GCM Tag（N+16 B）          │
│  每次隨機生成  │  AES-256-GCM 加密後的原始 IP 封包  │
└────────────────┴────────────────────────────────────┘
```

- **Nonce**：`os.urandom(12)` 每封包唯一，防止 IV 重用攻擊
- **密文**：原始 IP 封包以 AES-256-GCM 加密
- **GCM Tag**：16 bytes 驗證碼，任何竄改都會導致 `InvalidTag`，封包直接丟棄

---

## 密碼學設計

| 元件 | 選擇 | 理由 |
|---|---|---|
| 加密演算法 | AES-256-GCM | AEAD，一次完成加密 + 完整性驗證 |
| 金鑰長度 | 256 bit | AES 最高安全等級 |
| 金鑰衍生 | HKDF-SHA256 | 從預共享密碼安全地衍生會話金鑰 |
| Nonce | 96-bit 隨機 | GCM 標準長度，碰撞機率可忽略 |
| 驗證 Tag | 128-bit | 完整 GCM tag，不截短 |

金鑰衍生流程（`crypto.py`）：
```python
HKDF(SHA256, length=32, salt="vpntun-salt-v1", info="vpntun-aes256gcm")
    .derive(pre_shared_key)
```

---

## 設定參數

| 變數 | 檔案 | 預設值 | 說明 |
|---|---|---|---|
| `TUN_DEV` | server | `tun0` | TUN 介面名稱 |
| `TUN_DEV` | client | `tun1` | 同機測試時必須與 server 不同 |
| `LISTEN_PORT` | server | `51820` | UDP 監聽埠 |
| `SERVER_IP` | client | `127.0.0.1` | Server IP 位址 |
| `PSK` | 兩端 | `my-super-secret...` | 預共享密碼（兩端必須相同） |

---

## 清理環境

```bash
sudo ip link delete tun0 2>/dev/null || true
sudo ip link delete tun1 2>/dev/null || true
sudo ip route del 10.8.0.0/24 2>/dev/null || true
```

---

## 已知限制

- **靜態 PSK**：沒有前向保密（Forward Secrecy）。金鑰一旦洩漏，所有歷史流量都可被解密。正式場景應改用 X25519 ECDH 金鑰交換（WireGuard 的做法）。
- **無重放保護**：缺少封包序號或時間戳驗證，正式部署需補上。
- **單執行緒**：以 `select()` 做 I/O 多工，足夠學習用途，不適合高吞吐量場景。
- **同機 TUN 命名衝突**：兩個 process 在同一台機器時，介面名稱必須不同。

---

## 延伸方向

| 功能 | 實作方式 |
|---|---|
| X25519 金鑰交換 | 以 ECDH 取代 PSK，實現 Perfect Forward Secrecy |
| TAP 模式（L2） | 改 `IFF_TUN` → `IFF_TAP`，隧道完整乙太網路幀 |
| 重放攻擊防護 | 加入封包序號 + 滑動視窗驗證 |
| 多 Client 支援 | Server 以 dict 追蹤每個 client 的 `peer_addr` |
| 硬體加速 | 串接 OpenSSL EVP，啟用 AES-NI 指令集 |
| 封包混淆 | 前綴隨機 padding，對抗 DPI 流量特徵識別 |

---

## 涵蓋技能

- **C**：`ioctl`、file descriptor、共享函式庫（`ctypes` 橋接）
- **Python**：`ctypes` FFI、`select()` I/O 多工、UDP socket
- **Linux 網路**：TUN/TAP 裝置、核心路由、`ip` 指令
- **密碼學**：AES-256-GCM、HKDF、nonce 管理、AEAD 設計
- **系統程式設計**：Userspace ↔ 核心封包注入

---

## 參考資料

- [Linux Kernel TUN/TAP 文件](https://www.kernel.org/doc/html/latest/networking/tuntap.html)
- [RFC 5116 — AEAD 介面規範](https://datatracker.ietf.org/doc/html/rfc5116)
- [RFC 5869 — HKDF](https://datatracker.ietf.org/doc/html/rfc5869)
- [WireGuard 白皮書](https://www.wireguard.com/papers/wireguard.pdf)
- [Python cryptography 函式庫](https://cryptography.io/en/latest/)

---

## 授權

MIT
