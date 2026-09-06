import json
import os
from google import genai
from google.genai import types

# Инициализация клиента Gemini
# По умолчанию API_KEY берется из переменной окружения GEMINI_API_KEY
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6IXPAIOBIWUM9B585LCl0gsnIiOMk9bGlYVTA4Ap7S9lw"))

SYSTEM_INSTRUCTION = """
Ты — специализированный парсер прайс-листов электроники. Твоя задача — распарсить неструктурированный текст прайса, вычленить из него товары, определить их атрибуты, рассчитать итоговую цену согласно переданным правилам наценки и вернуть результат строго в формате JSON Array.

Правила обработки:
1. Игнорируй любые рекламные вступления, контакты продавца, условия доставки, эмодзи, флаги стран и мусорные символы.
2. Определяй бренд, категорию, модель и стандартизированное название.
3. Выделяй атрибуты в объект `attrs` (storage, color, sim_type).
4. Регион (region): если указан регион, страна или флаг (например 🇮🇳 -> Индия, 🇺🇸 -> США), добавь его как атрибут "region": {"name": "Регион", "value": "..."}. Если регион отсутствует, НЕ ВКЛЮЧАЙ ключ `region` в `attrs`.
5. Рассчитывай final_price как original_price + sum(наценки).
"""

# JSON Schema для структурированного ответа
RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "brand": {"type": "STRING"},
            "category": {"type": "STRING"},
            "model": {"type": "STRING"},
            "name": {"type": "STRING"},
            "original_price": {"type": "NUMBER"},
            "markup_applied": {"type": "NUMBER"},
            "final_price": {"type": "NUMBER"},
            "attrs": {
                "type": "OBJECT",
                "properties": {
                    "storage": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "value": {"type": "STRING"}
                        },
                        "required": ["name", "value"]
                    },
                    "color": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "value": {"type": "STRING"}
                        },
                        "required": ["name", "value"]
                    },
                    "sim_type": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "value": {"type": "STRING"}
                        },
                        "required": ["name", "value"]
                    },
                    "region": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "value": {"type": "STRING"}
                        },
                        "required": ["name", "value"]
                    }
                }
            }
        },
        "required": ["brand", "category", "model", "name", "original_price", "markup_applied", "final_price", "attrs"]
    }
}

USER_PROMPT = """
Правила наценки:
- Базовая наценка на линейку iPhone 15: +1000 руб.
- Объем памяти: 128гб +100 руб, 256гб +200 руб, 512гб +400 руб.
- Модели: Plus +1000 руб, Pro/Pro Max +2000 руб.
- Если eSIM: +100 руб.
- iPhone 14 и старше: без наценки.

Прайс-лист:
15 128 Black - 53800 🇮🇳
15 128 Blue - 52500
15 Plus 128 Pink - 56300 🇮🇳
15 Pro 512 Blue - 89000 🇺🇸(ESIM)
14 512 Red - 49900
"""

def parse_pricelist():
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=USER_PROMPT,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                temperature=0.1,  # Низкая температура для строгости выполнения правил
            )
        )
        
        # Десериализуем и красиво выводим результат
        parsed_json = json.loads(response.text)
        print(json.dumps(parsed_json, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Ошибка вызова Gemini API: {e}")

if __name__ == "__main__":
    parse_pricelist()