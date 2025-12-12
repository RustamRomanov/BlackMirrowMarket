#!/usr/bin/env python3
"""
Скрипт для исправления баланса через API эндпоинт.

Использование:
    python3 fix_balance_via_api.py <telegram_id> [API_URL]

Примеры:
    python3 fix_balance_via_api.py 8032604270
    python3 fix_balance_via_api.py 8032604270 https://blackmirrowmarket-production.up.railway.app
"""

import sys
import requests
import json

def fix_balance_via_api(telegram_id: int, api_url: str = None):
    """Исправляет баланс через API эндпоинт"""
    if not api_url:
        # Пробуем найти API URL из переменных окружения или используем Railway домен
        import os
        api_url = os.getenv("API_URL") or "https://blackmirrowmarket-production.up.railway.app"
    
    # Убираем слэш в конце, если есть
    api_url = api_url.rstrip('/')
    
    endpoint = f"{api_url}/api/balance/{telegram_id}/recalculate-from-tasks"
    
    print(f"🔗 Вызываю API: {endpoint}")
    print(f"👤 Telegram ID: {telegram_id}")
    print()
    
    try:
        response = requests.post(endpoint, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Баланс успешно пересчитан!")
            print()
            print(f"📊 Текущий баланс: {data.get('current_balance_ton', 0):.4f} TON")
            print(f"📈 Правильный баланс: {data.get('correct_balance_ton', 0):.4f} TON")
            print(f"🔍 Разница: {data.get('difference_ton', 0):+.4f} TON")
            print()
            print(f"💰 Депозиты: {data.get('deposits_ton', 0):.4f} TON")
            print(f"💸 Выводы: {data.get('withdrawals_ton', 0):.4f} TON")
            print(f"💵 Потрачено на задания: {data.get('spent_on_active_tasks_ton', 0):.4f} TON")
            print(f"📋 Активных заданий: {data.get('active_tasks_count', 0)}")
            print()
            print(f"💬 {data.get('message', '')}")
            
            if data.get('active_tasks'):
                print("\n📋 Детали заданий:")
                for task in data['active_tasks']:
                    print(f"  - #{task['task_id']}: '{task['title']}'")
                    print(f"    Бюджет: {task['task_budget_ton']:.4f} TON ({task['total_slots']} слотов × {task['price_per_slot_ton']:.4f} TON)")
            
        elif response.status_code == 404:
            print(f"❌ Пользователь с telegram_id {telegram_id} не найден")
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Детали: {error_data}")
            except:
                print(f"   Ответ: {response.text}")
                
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удалось подключиться к {api_url}")
        print("   Проверьте, что бэкенд развернут и доступен")
    except requests.exceptions.Timeout:
        print(f"❌ Превышено время ожидания при подключении к {api_url}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 fix_balance_via_api.py <telegram_id> [API_URL]")
        print("Пример: python3 fix_balance_via_api.py 8032604270")
        print("Или: python3 fix_balance_via_api.py 8032604270 https://your-backend.railway.app")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        api_url = sys.argv[2] if len(sys.argv) > 2 else None
        fix_balance_via_api(telegram_id, api_url)
    except ValueError:
        print(f"❌ Ошибка: '{sys.argv[1]}' не является числом")
        sys.exit(1)

