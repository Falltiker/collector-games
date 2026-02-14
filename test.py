import re

def parse_price(text):
    # Ищем последовательность из цифр, точек и запятых
    match = re.search(r'[\d.,]+', text)
    if match:
        raw_value = match.group()
        # Стандартизируем: убираем случайные пробелы и меняем запятую на точку
        clean_value = raw_value.replace(" ", "").replace(",", ".")
        try:
            return float(clean_value)
        except ValueError:
            return 0.0
    return 0.0

# Тесты:
print(parse_price("12.586₴"))    # 12.5
print(parse_price("16,7$"))    # 16.7
print(parse_price("1 500.00")) # 1500.0