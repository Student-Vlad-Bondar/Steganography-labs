import os
from PIL import Image

def _embed_bits(image: Image.Image, binary_message: str):
    """Внутрішня функція для вбудовування бітів (знижує Cognitive Complexity)."""
    pixel_map = image.load()
    binary_index = 0
    message_len = len(binary_message)
    
    for y in range(image.height):
        for x in range(image.width):
            if binary_index >= message_len:
                return
            
            # Розпаковуємо RGB напряму (type ignore приховує баг типізації Pylance)
            r, g, b = pixel_map[x, y]  # type: ignore
            
            # Записуємо біти у кольорові канали
            r = (r & ~1) | int(binary_message[binary_index])
            binary_index += 1
            
            if binary_index < message_len:
                g = (g & ~1) | int(binary_message[binary_index])
                binary_index += 1
                
            if binary_index < message_len:
                b = (b & ~1) | int(binary_message[binary_index])
                binary_index += 1
                
            pixel_map[x, y] = (r, g, b)  # type: ignore


def encode_image(image_path: str, message: str, output_path: str):
    """Приховує текстове повідомлення в зображенні методом LSB."""
    full_message = message + "END"
    binary_message = ''.join(format(ord(char), '08b') for char in full_message)
    
    image = Image.open(image_path).convert('RGB')
    max_capacity_bits = image.width * image.height * 3
    
    if len(binary_message) > max_capacity_bits:
        raise ValueError(
            f"Повідомлення завелике! Доступно: {max_capacity_bits} біт, "
            f"потрібно: {len(binary_message)} біт."
        )
    
    _embed_bits(image, binary_message)
    
    image.save(output_path)
    print(f"\n[Успіх] Повідомлення успішно вбудовано та збережено у: {output_path}")


def _extract_text(image: Image.Image) -> str:
    """Внутрішня функція для вилучення тексту (знижує Cognitive Complexity)."""
    pixel_map = image.load()
    binary_data = ""
    decoded_chars = []
    
    for y in range(image.height):
        for x in range(image.width):
            # Розпаковуємо RGB напряму (type ignore приховує баг типізації Pylance)
            r, g, b = pixel_map[x, y]  # type: ignore
            
            # Зчитуємо молодші біти відразу з трьох каналів
            binary_data += f"{r & 1}{g & 1}{b & 1}"
            
            # Конвертуємо накопичені 8 бітів у символ
            while len(binary_data) >= 8:
                byte = binary_data[:8]
                binary_data = binary_data[8:]
                
                decoded_chars.append(chr(int(byte, 2)))
                
                # Перевіряємо, чи не досягли ми маркера завершення
                if "".join(decoded_chars[-3:]) == "END":
                    return "".join(decoded_chars[:-3])
                    
    raise ValueError("Маркер завершення 'END' не знайдено або повідомлення відсутнє.")


def decode_image(image_path: str) -> str:
    """Вилучає приховане текстове повідомлення із зображення."""
    image = Image.open(image_path).convert('RGB')
    return _extract_text(image)


def main():
    while True:
        print("\n" + "=" * 20 + " LSB Steganography " + "=" * 20)
        print("1. Приховати повідомлення")
        print("2. Вилучити повідомлення")
        print("3. Вихід")
        choice = input("Оберіть опцію: ").strip()
        
        if choice == '1':
            img_path = input("Введіть шлях до вхідного зображення (PNG/BMP): ").strip().strip('"')
            msg = input("Введіть текст для приховування: ")
            out_path = input("Введіть шлях для збереження стегозображення: ").strip().strip('"')
            try:
                encode_image(img_path, msg, out_path)
            except Exception as e:
                print(f"[Помилка]: {e}")
                
        elif choice == '2':
            img_path = input("Введіть шлях до стегозображення: ").strip().strip('"')
            try:
                extracted = decode_image(img_path)
                print(f"\n[Вилучене повідомлення]: {extracted}")
            except Exception as e:
                print(f"[Помилка]: {e}")
                
        elif choice == '3':
            print("Роботу завершено.")
            break
        else:
            print("Невірний вибір. Спробуйте ще раз.")

if __name__ == "__main__":
    main()