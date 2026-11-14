import os
import math
from PIL import Image

# Увімкнення підтримки ANSI-кольорів для терміналу Windows
os.system('')

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def get_interval_info(d: int) -> tuple[int, int, int]:
    """Повертає нижню межу, верхню межу та кількість бітів для різниці d"""
    intervals = [
        (0, 7, 3), (8, 15, 3), (16, 31, 4), 
        (32, 63, 5), (64, 127, 6), (128, 255, 7)
    ]
    for lower, upper, bits in intervals:
        if lower <= d <= upper:
            return lower, upper, bits
    return 0, 0, 0

def _calculate_overflow(p: int) -> int:
    """Обчислює величину виходу пікселя за межі діапазону [0..255]"""
    if p < 0:
        return p
    if p > 255:
        return p - 255
    return 0

def _shift_pixels(p1: int, p2: int, m: int) -> tuple[int, int]:
    """Розподіляє різницю m між двома пікселями (зменшує Cognitive Complexity)"""
    if m == 0:
        return p1, p2
        
    delta_p1 = math.floor(abs(m) / 2)
    delta_p2 = math.ceil(abs(m) / 2)
    
    # Оптимізована логіка напрямку зсуву
    if (m > 0 and p2 >= p1) or (m < 0 and p1 > p2):
        return p1 - delta_p1, p2 + delta_p2
    
    return p1 + delta_p1, p2 - delta_p2

def embed_pvd_pair(p1: int, p2: int, secret_bits_str: str, verbose: bool = False) -> tuple[int, int, str]:
    """Вбудовує біти у пару пікселів за методом PVD з можливістю детального виводу"""
    d = abs(p2 - p1)
    l_k, u_k, n = get_interval_info(d)
    
    b_str = secret_bits_str[:n].ljust(n, '0')
    b = int(b_str, 2) if b_str else 0
    
    d_new = l_k + b
    m = d_new - d
    
    if verbose:
        print(f"\n{Colors.CYAN}--- ДЕТАЛІ ВБУДОВУВАННЯ ---{Colors.RESET}")
        print(f"Оригінальні пікселі: {Colors.BOLD}P1 = {p1}, P2 = {p2}{Colors.RESET}")
        print(f"1. Початкова різниця (d): |{p2} - {p1}| = {Colors.YELLOW}{d}{Colors.RESET}")
        print(f"2. Інтервал для d={d}: [{l_k}, {u_k}], можна вбудувати {Colors.YELLOW}{n} біт{Colors.RESET}")
        print(f"3. Беремо {n} біт секрету: '{Colors.GREEN}{b_str}{Colors.RESET}', десяткове b = {Colors.GREEN}{b}{Colors.RESET}")
        print(f"4. Нова різниця (d_new): l_k + b = {l_k} + {b} = {Colors.YELLOW}{d_new}{Colors.RESET}")
        print(f"5. Різниця змін (m): {d_new} - {d} = {Colors.YELLOW}{m}{Colors.RESET}")

    # Обчислення сирих значень через виділену функцію
    p1_new, p2_new = _shift_pixels(p1, p2, m)
        
    if verbose:
        print(f"6. Сирі значення після зсуву: P1' = {p1_new}, P2' = {p2_new}")

    # Компенсація виходу за межі [0..255] через виділену функцію
    overflow_p1 = _calculate_overflow(p1_new)
    overflow_p2 = _calculate_overflow(p2_new)
    
    p1_final = max(0, min(255, p1_new - overflow_p2))
    p2_final = max(0, min(255, p2_new - overflow_p1))
    
    if verbose:
        if overflow_p1 != 0 or overflow_p2 != 0:
            print(f"7. {Colors.RED}Відбувся вихід за межі!{Colors.RESET} Застосовано компенсацію.")
        print(f"8. Фінальні пікселі: {Colors.BOLD}{Colors.GREEN}P1 = {p1_final}, P2 = {p2_final}{Colors.RESET}")
        print(f"{Colors.CYAN}---------------------------{Colors.RESET}\n")

    return p1_final, p2_final, secret_bits_str[n:]

def extract_pvd_pair(p1: int, p2: int, verbose: bool = False) -> str:
    """Вилучає біти з пари пікселів"""
    d = abs(p2 - p1)
    l_k, u_k, n = get_interval_info(d)
    b = d - l_k
    b_str = bin(b)[2:].zfill(n)
    
    if verbose:
        print(f"\n{Colors.CYAN}--- ДЕТАЛІ ВИЛУЧЕННЯ ---{Colors.RESET}")
        print(f"Стегопікселі: {Colors.BOLD}P1 = {p1}, P2 = {p2}{Colors.RESET}")
        print(f"1. Зчитана різниця (d_new): |{p2} - {p1}| = {Colors.YELLOW}{d}{Colors.RESET}")
        print(f"2. Інтервал: [{l_k}, {u_k}], кількість прихованих бітів = {Colors.YELLOW}{n}{Colors.RESET}")
        print(f"3. Десяткове значення секрету (b): {d} - {l_k} = {Colors.GREEN}{b}{Colors.RESET}")
        print(f"4. Двійковий формат ({n} біт): {Colors.BOLD}{Colors.GREEN}{b_str}{Colors.RESET}")
        print(f"{Colors.CYAN}------------------------{Colors.RESET}\n")
        
    return b_str

def get_image_capacity(image: Image.Image) -> int:
    """Розраховує загальну ємність зображення у бітах без його зміни"""
    pixels = image.load()
    width, height = image.size
    total_capacity = 0
    
    for y in range(height):
        for x in range(0, width - 1, 2):
            # Явне приведення типів (int) та type ignore виправляють помилки Pylance
            p1 = int(pixels[x, y])     # type: ignore
            p2 = int(pixels[x+1, y])   # type: ignore
            d = abs(p2 - p1)
            _, _, n = get_interval_info(d)
            total_capacity += n
            
    return total_capacity

def encode_image_pvd(image_path: str, message: str, output_path: str):
    """Повноцінне приховування тексту в зображенні у градаціях сірого"""
    full_message = message + "END"
    binary_message = ''.join(format(ord(char), '08b') for char in full_message)
    
    image = Image.open(image_path).convert('L')
    capacity = get_image_capacity(image)
    
    if len(binary_message) > capacity:
        raise ValueError(f"Повідомлення завелике! Доступно: {capacity} біт, потрібно: {len(binary_message)} біт.")
    
    pixels = image.load()
    width, height = image.size
    remaining_bits = binary_message
    
    for y in range(height):
        for x in range(0, width - 1, 2):
            if not remaining_bits:
                break
            
            p1 = int(pixels[x, y])    # type: ignore
            p2 = int(pixels[x+1, y])  # type: ignore
            
            new_p1, new_p2, remaining_bits = embed_pvd_pair(p1, p2, remaining_bits, verbose=False)
            
            pixels[x, y] = new_p1     # type: ignore
            pixels[x+1, y] = new_p2   # type: ignore
            
        if not remaining_bits:
            break
            
    image.save(output_path)
    print(f"{Colors.GREEN}[Успіх] Повідомлення успішно вбудовано!{Colors.RESET}")
    print(f"Збережено у: {Colors.BOLD}{output_path}{Colors.RESET}")

def decode_image_pvd(image_path: str) -> str:
    """Вилучення прихованого тексту із PVD-зображення"""
    image = Image.open(image_path).convert('L')
    pixels = image.load()
    width, height = image.size
    
    binary_data = ""
    decoded_chars = []
    
    for y in range(height):
        for x in range(0, width - 1, 2):
            p1 = int(pixels[x, y])    # type: ignore
            p2 = int(pixels[x+1, y])  # type: ignore
            
            extracted_bits = extract_pvd_pair(p1, p2, verbose=False)
            binary_data += extracted_bits
            
            while len(binary_data) >= 8:
                byte = binary_data[:8]
                binary_data = binary_data[8:]
                decoded_chars.append(chr(int(byte, 2)))
                
                if "".join(decoded_chars[-3:]) == "END":
                    return "".join(decoded_chars[:-3])
                    
    raise ValueError("Маркер завершення 'END' не знайдено або повідомлення відсутнє.")

def interactive_pair_test():
    """Інтерактивний ручний тест для пари пікселів"""
    print(f"\n{Colors.HEADER}=== РУЧНЕ ТЕСТУВАННЯ ПАРИ ПІКСЕЛІВ ==={Colors.RESET}")
    try:
        p1 = int(input(f"Введіть значення {Colors.BOLD}Pixel 1{Colors.RESET} (0-255): "))
        p2 = int(input(f"Введіть значення {Colors.BOLD}Pixel 2{Colors.RESET} (0-255): "))
        char = input("Введіть ОДИН секретний символ (наприклад 'a'): ")
        
        if not (0 <= p1 <= 255) or not (0 <= p2 <= 255):
            print(f"{Colors.RED}Пікселі мають бути в діапазоні 0-255!{Colors.RESET}")
            return
            
        binary_secret = format(ord(char[0]), '08b')
        print(f"ASCII код символу '{char[0]}': {ord(char[0])}, Двійковий код: {Colors.GREEN}{binary_secret}{Colors.RESET}")
        
        new_p1, new_p2, _ = embed_pvd_pair(p1, p2, binary_secret, verbose=True)
        extracted = extract_pvd_pair(new_p1, new_p2, verbose=True)
        
        print(f"{Colors.BOLD}Результат вилучення:{Colors.RESET} зчитано біти {Colors.GREEN}{extracted}{Colors.RESET}")
    except ValueError:
        print(f"{Colors.RED}Помилка вводу! Будь ласка, вводьте цілі числа для пікселів.{Colors.RESET}")

def main():
    while True:
        print(f"\n{Colors.HEADER}{Colors.BOLD}" + "=" * 15 + " PVD Steganography " + "=" * 15 + f"{Colors.RESET}")
        print(f"1. {Colors.CYAN}Протестувати пару пікселів вручну (з поясненнями){Colors.RESET}")
        print(f"2. {Colors.YELLOW}Приховати текст у зображенні (Grayscale PVD){Colors.RESET}")
        print(f"3. {Colors.YELLOW}Вилучити текст із зображення (Grayscale PVD){Colors.RESET}")
        print("4. Вихід")
        choice = input(f"{Colors.BOLD}Оберіть опцію:{Colors.RESET} ").strip()
        
        if choice == '1':
            interactive_pair_test()
            
        elif choice == '2':
            img_path = input("Введіть шлях до оригінального зображення: ").strip().strip('"')
            msg = input("Введіть секретний текст: ")
            out_path = input("Введіть шлях для збереження (напр. result.png): ").strip().strip('"')
            try:
                encode_image_pvd(img_path, msg, out_path)
            except Exception as e:
                print(f"{Colors.RED}[Помилка]: {e}{Colors.RESET}")
                
        elif choice == '3':
            img_path = input("Введіть шлях до стегозображення: ").strip().strip('"')
            try:
                extracted = decode_image_pvd(img_path)
                print(f"\n{Colors.GREEN}{Colors.BOLD}[Вилучене повідомлення]: {extracted}{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}[Помилка]: {e}{Colors.RESET}")
                
        elif choice == '4':
            print("Роботу завершено.")
            break
        else:
            print(f"{Colors.RED}Невірний вибір. Спробуйте ще раз.{Colors.RESET}")

if __name__ == "__main__":
    main()