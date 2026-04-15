import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# 1. I2C Bağlantısını senin pinlerine göre başlatır (SCL: Pin 3, SDA: Pin 5)
i2c = busio.I2C(board.SCL, board.SDA)

# 2. Ekran Boyutunu Tanımla (Genelde 128x64 veya 128x32 olur)
# Eğer ekranın yarısı gözükmüyorsa 32 kısmını 64 yapabilirsin.
width = 128
height = 64
oled = adafruit_ssd1306.SSD1306_I2C(width, height, i2c)

# 3. Ekranı Temizle
oled.fill(0)
oled.show()

# 4. Yazı Yazmak İçin Görüntü Oluştur
image = Image.new("1", (oled.width, oled.height))
draw = ImageDraw.Draw(image)

# Varsayılan yazı tipi
font = ImageFont.load_default()

# 5. Yazıyı Yazdır (x, y koordinatları)
draw.text((0, 0), "Merhaba!", font=font, fill=255)

# 6. Görüntüyü Ekrana Gönder
oled.image(image)
oled.show()

print("Ekrana 'Merhaba' yazdırıldı!")
