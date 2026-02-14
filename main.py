# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import requests
import io
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Импорты для графиков
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# ---------- WINDOWS UTF-8 ----------
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print(Fore.RED + "❌ Ошибка: TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не найдены в .env")
    sys.exit(1)

# ========== НАСТРОЙКИ ==========
SPREAD_THRESHOLD = 7              # % расхождения
COOLDOWN = 60                        # секунд между алертами
MIN_VOLUME_USD = 0                   # минимальный объем
INTERVAL = 10                         # частота опроса API
SHOW_MOVEMENTS = True                 # показывать в консоли
SYMBOL_FILTER = ""                    # фильтр по символам

MEXC_FUTURES_TICKER_URL = "https://contract.mexc.com/api/v1/contract/ticker"

init(autoreset=True)

# Хранилища
last_alert_time = {}
symbol_info = {}
sent_signals = set()

# ---------- ПОЛУЧЕНИЕ ДАННЫХ ----------
def get_all_futures_tickers():
    try:
        resp = requests.get(MEXC_FUTURES_TICKER_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get('success'):
            return None
        tickers = data.get('data', [])
        print(Fore.CYAN + f"📡 Получено {len(tickers)} контрактов")
        return tickers
    except Exception as e:
        print(Fore.RED + f"❌ Ошибка запроса: {e}")
        return None

# ---------- ИНИЦИАЛИЗАЦИЯ ----------
def init_symbols_from_tickers(tickers):
    symbols = []
    for contract in tickers:
        symbol = contract.get('symbol')
        if symbol:
            symbols.append(symbol)
            # Извлекаем базовую валюту (убираем _USDT, _USDC и т.д.)
            base = symbol.split('_')[0]
            symbol_info[symbol] = {'base': base, 'quote': 'USDT'}
    return symbols

# ---------- ПРОВЕРКА РАСХОЖДЕНИЯ ----------
def check_price_deviation(contract):
    try:
        symbol = contract.get('symbol')
        last = float(contract.get('lastPrice', 0))
        fair = float(contract.get('fairPrice', 0))
        volume = float(contract.get('volume24', 0))
        
        if SYMBOL_FILTER and SYMBOL_FILTER not in symbol:
            return False, 0, 0, 0, 0
        
        if last == 0 or fair == 0:
            return False, 0, 0, 0, 0
        
        if MIN_VOLUME_USD > 0 and volume < MIN_VOLUME_USD:
            return False, 0, 0, 0, 0
        
        deviation = ((last - fair) / fair) * 100
        
        return True, deviation, last, fair, volume
        
    except Exception as e:
        return False, 0, 0, 0, 0

# ---------- ПОЛУЧЕНИЕ KLINE ДАННЫХ ----------
def get_kline_data(symbol, interval="5m", limit=50):
    """
    Получает свечные данные для графика с обработкой ошибок
    Интервалы: 1m, 5m, 15m, 30m, 60m
    """
    try:
        base_symbol = symbol.split('_')[0]
        
        symbol_variants = [
            f'{base_symbol}USDT',  # Обычный USDT
            f'{base_symbol}USDC',  # USDC если есть
            base_symbol,            # Просто символ
            symbol.replace('_', '') # Без подчеркивания
        ]
        
        for test_symbol in symbol_variants:
            try:
                # Формируем URL для MEXC API
                url = "https://api.mexc.com/api/v3/klines"
                
                params = {
                    'symbol': test_symbol,
                    'interval': interval,
                    'limit': limit
                }
                
                print(Fore.CYAN + f"📊 Пробуем: {test_symbol}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                resp = requests.get(url, params=params, headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        print(Fore.GREEN + f"✅ Успешно для {test_symbol}")
                        return data
                elif resp.status_code == 400:
                    # Пробуем следующий вариант
                    continue
                else:
                    continue
                    
            except:
                continue
        
        print(Fore.YELLOW + f"⚠️ Пробуем альтернативный API...")
        
        # Альтернативный API (MEXC Contract API)
        alt_url = f"https://contract.mexc.com/api/v1/contract/kline/{base_symbol}_USDT"
        alt_params = {
            'interval': interval.replace('m', ''),  # убираем 'm'
            'limit': limit
        }
        
        alt_resp = requests.get(alt_url, params=alt_params, timeout=5)
        if alt_resp.status_code == 200:
            alt_data = alt_resp.json()
            if alt_data.get('success') and alt_data.get('code') == 0:
                kline_data = alt_data.get('data', [])
                if kline_data and len(kline_data) > 0:
                    print(Fore.GREEN + f"✅ Альтернативный API сработал")
                    return kline_data
        
        print(Fore.YELLOW + f"⚠️ Не удалось получить данные для {symbol}")
        return None
            
    except Exception as e:
        print(Fore.YELLOW + f"⚠️ Ошибка получения kline для {symbol}: {e}")
        return None

# ---------- СОЗДАНИЕ ГРАФИКА ----------
def create_chart(symbol, kline_data, last_price, fair_price):
    """
    Создает график цены на основе свечных данных
    Поддерживает разные форматы данных
    """
    if not kline_data or len(kline_data) < 2:
        print(Fore.YELLOW + f"⚠️ Недостаточно данных для графика")
        return None
    
    try:
        times = []
        prices = []
        volumes = []
        
        # Определяем формат данных и парсим
        for candle in kline_data:
            if isinstance(candle, list):
                if len(candle) >= 6:
                    # Формат MEXC Spot API
                    timestamp = int(candle[0])
                    close_price = float(candle[4])
                    volume = float(candle[5])
                    
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    times.append(dt)
                    prices.append(close_price)
                    volumes.append(volume)
                elif len(candle) >= 5:
                    # Формат MEXC Contract API
                    timestamp = int(candle[0])
                    close_price = float(candle[4])
                    volume = float(candle[5]) if len(candle) > 5 else 0
                    
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    times.append(dt)
                    prices.append(close_price)
                    volumes.append(volume)
            elif isinstance(candle, dict):
                # Альтернативный формат
                if 'time' in candle and 'close' in candle:
                    timestamp = int(candle['time'])
                    close_price = float(candle['close'])
                    volume = float(candle.get('volume', 0))
                    
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    times.append(dt)
                    prices.append(close_price)
                    volumes.append(volume)
        
        if len(times) < 2:
            print(Fore.YELLOW + f"⚠️ Мало данных после парсинга")
            return None
        
        # Создаем фигуру
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), 
                                        gridspec_kw={'height_ratios': [3, 1]})
        
        # Настройка стиля
        plt.style.use('dark_background')
        fig.patch.set_facecolor('#0d0d0d')
        ax1.set_facecolor('#1a1a1a')
        ax2.set_facecolor('#1a1a1a')
        
        # Верхний график - цена
        ax1.plot(times, prices, color='#00aaff', linewidth=2, label='Price')
        
        # Линии текущей и справедливой цены
        ax1.axhline(y=last_price, color='#ffaa00', linestyle='--', 
                   linewidth=2, label=f'Last: ${last_price:.4f}', alpha=0.8)
        ax1.axhline(y=fair_price, color='#00ff88', linestyle='--', 
                   linewidth=2, label=f'Fair: ${fair_price:.4f}', alpha=0.8)
        
        ax1.legend(loc='upper left', facecolor='#2a2a2a', edgecolor='none')
        ax1.set_title(f'{symbol} Price Chart', color='white', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Price (USDT)', color='white')
        ax1.tick_params(colors='white')
        ax1.grid(True, alpha=0.2, linestyle='--')
        
        # Нижний график - объем
        if any(v > 0 for v in volumes):
            ax2.bar(times, volumes, color='#ffaa00', alpha=0.6, width=0.02)
        else:
            # Если нет данных по объему, показываем простую линию
            ax2.plot(times, [1] * len(times), color='#ffaa00', alpha=0.3)
            ax2.text(0.5, 0.5, 'No volume data', transform=ax2.transAxes,
                    ha='center', va='center', color='gray', alpha=0.5)
        
        ax2.set_ylabel('Volume', color='white')
        ax2.tick_params(colors='white')
        ax2.grid(True, alpha=0.2, linestyle='--')
        
        # Форматирование оси X
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', color='white')
        
        plt.tight_layout()
        
        # Сохраняем
        buf = io.BytesIO()
        plt.savefig(buf, format='PNG', dpi=100, facecolor='#0d0d0d', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        print(Fore.GREEN + f"✅ График создан успешно")
        return buf
        
    except Exception as e:
        print(Fore.RED + f"❌ Ошибка создания графика: {e}")
        import traceback
        traceback.print_exc()
        return None

# ---------- ФОРМАТ СООБЩЕНИЯ ----------
def format_alert(symbol, deviation, last_price, fair_price, volume_usd, alert_time):
    base = symbol_info.get(symbol, {}).get('base', symbol.split('_')[0])
    
    if deviation > 0:
        direction = "🟢 LONG"
        spread_sign = "+"
    else:
        direction = "🔴 SHORT"
        spread_sign = ""
    
    # Форматирование цен
    if last_price >= 1000:
        last_str = f"${last_price:,.2f}"
        fair_str = f"${fair_price:,.2f}"
    elif last_price >= 1:
        last_str = f"${last_price:.2f}"
        fair_str = f"${fair_price:.2f}"
    else:
        last_str = f"${last_price:.6f}"
        fair_str = f"${fair_price:.6f}"
    
    # Объём
    if volume_usd >= 1e9:
        vol_str = f"${volume_usd/1e9:.2f}B"
    elif volume_usd >= 1e6:
        vol_str = f"${volume_usd/1e6:.2f}M"
    elif volume_usd >= 1e3:
        vol_str = f"${volume_usd/1e3:.2f}K"
    else:
        vol_str = f"${volume_usd:.2f}"
    
    tz_offset = timedelta(hours=3)
    local_time = (alert_time + tz_offset).strftime("%H:%M:%S")
    
    return f"""
⚠️ FAIR PRICE ALERT | {direction}

───◇───────────────
🔖 Token: ${base}
📊 Last Price: {last_str}
⚖️ Fair Price:  {fair_str}
📈 Spread:      {spread_sign}{abs(deviation):.2f}%

📦 Volume 24h: {vol_str}
⏰ Time:       {local_time} UTC+3
───◇───────────────
😎 @LBScalp
📉 @aslgw
""".strip()

# ---------- ОТПРАВКА В TELEGRAM С ФОТО ----------
def send_telegram_alert_with_photo(text, symbol, chart_buffer):
    try:
        base = symbol_info.get(symbol, {}).get('base', symbol.split('_')[0])
        mexc_url = f"https://futures.mexc.com/contract/{base}-USDT"
        
        # Создаем клавиатуру
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 LBScalp", "url": "https://t.me/LBScalp"}],
                [{"text": "🔗 MEXC", "url": mexc_url}]
            ]
        }
        
        # Подготавливаем файл
        files = {
            'photo': ('chart.png', chart_buffer.getvalue(), 'image/png')
        }
        
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': text,
            'parse_mode': 'HTML',
            'reply_markup': json.dumps(keyboard)
        }
        
        print(Fore.CYAN + "📤 Отправка фото в Telegram...")
        
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            print(Fore.GREEN + "✅ Алерт с графиком отправлен!")
            return True
        else:
            print(Fore.RED + f"❌ Ошибка Telegram: {response.status_code}")
            print(Fore.RED + f"Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(Fore.RED + f"❌ Ошибка отправки с фото: {e}")
        return False

# ---------- ОТПРАВКА БЕЗ ФОТО ----------
def send_telegram_alert_text(text, symbol):
    try:
        base = symbol_info.get(symbol, {}).get('base', symbol.split('_')[0])
        mexc_url = f"https://futures.mexc.com/contract/{base}-USDT"
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "📢 LBScalp", "url": "https://t.me/LBScalp"}],
                [{"text": "🔗 MEXC", "url": mexc_url}]
            ]
        }
        
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': json.dumps(keyboard)
        }
        
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(Fore.YELLOW + "⚠️ Алерт отправлен без графика")
            return True
        else:
            return False
            
    except Exception as e:
        print(Fore.RED + f"❌ Ошибка отправки: {e}")
        return False

# ---------- ГЛАВНЫЙ ЦИКЛ ----------
def main():
    print(Fore.CYAN + Style.BRIGHT + "\n⚡ MEXC FAIR PRICE PARSER ⚡")
    print(Fore.CYAN + "="*70)
    print(Fore.CYAN + f"📊 Порог расхождения: {SPREAD_THRESHOLD}% | Cooldown: {COOLDOWN}s")
    print(Fore.CYAN + f"🔄 Опрос API: каждые {INTERVAL}с")
    print(Fore.CYAN + f"💰 Min Volume: {'ВЫКЛЮЧЕН' if MIN_VOLUME_USD == 0 else f'${MIN_VOLUME_USD:,}'}")
    if SYMBOL_FILTER:
        print(Fore.CYAN + f"🔍 Фильтр символов: {SYMBOL_FILTER}")
    else:
        print(Fore.CYAN + f"🔍 Фильтр символов: ВСЕ МОНЕТЫ")
    print(Fore.CYAN + "="*70 + "\n")
    
    # ПЕРВЫЙ ЗАПРОС
    print(Fore.YELLOW + "🔄 Получение списка контрактов...")
    first_tickers = get_all_futures_tickers()
    if not first_tickers:
        print(Fore.RED + "❌ Не удалось получить данные.")
        sys.exit(1)
    
    symbols = init_symbols_from_tickers(first_tickers)
    if not symbols:
        print(Fore.RED + "❌ Нет контрактов.")
        sys.exit(1)
    
    print(Fore.GREEN + f"📡 Получено {len(first_tickers)} контрактов")
    print(Fore.GREEN + f"✅ Загружено {len(symbols)} контрактов")
    print(Fore.GREEN + f"📋 Первые 5: {symbols[:5]}")
    
    print(Fore.GREEN + f"\n✅ Погнали! Ищем расхождения больше {SPREAD_THRESHOLD}%...\n")
    
    cycle_count = 0
    total_alerts = 0
    
    while True:
        try:
            cycle_start = time.time()
            cycle_count += 1
            now_utc = datetime.now(UTC)
            now_ts = now_utc.timestamp()
            
            tickers = get_all_futures_tickers()
            
            if tickers:
                for contract in tickers:
                    symbol = contract.get('symbol')
                    
                    is_deviated, deviation, last, fair, volume = check_price_deviation(contract)
                    
                    if is_deviated and abs(deviation) >= SPREAD_THRESHOLD:
                        signal_key = f"{symbol}_{deviation:.2f}"
                        last_time = last_alert_time.get(symbol, 0)
                        
                        if time.time() - last_time >= COOLDOWN and signal_key not in sent_signals:
                            
                            if SHOW_MOVEMENTS:
                                direction = "📈 LONG" if deviation > 0 else "📉 SHORT"
                                print(Fore.YELLOW + f"{direction} {symbol}: {deviation:+.2f}%")
                            
                            msg = format_alert(symbol, deviation, last, fair, volume, now_utc)
                            
                            print(Fore.MAGENTA + "\n" + "🚨 FAIR PRICE ALERT! " + "="*45)
                            print(msg)
                            
                            # Пробуем получить график
                            print(Fore.CYAN + f"📊 Получаем график для {symbol}...")
                            kline_data = get_kline_data(symbol, "5m", 30)
                            
                            if kline_data:
                                chart_buffer = create_chart(symbol, kline_data, last, fair)
                                if chart_buffer:
                                    # Отправляем с графиком
                                    if send_telegram_alert_with_photo(msg, symbol, chart_buffer):
                                        print(Fore.GREEN + "✅ Отправлено с графиком")
                                    else:
                                        # Если не получилось с фото, отправляем текст
                                        send_telegram_alert_text(msg, symbol)
                                else:
                                    send_telegram_alert_text(msg, symbol)
                            else:
                                send_telegram_alert_text(msg, symbol)
                            
                            print(Fore.MAGENTA + "="*60 + "\n")
                            
                            last_alert_time[symbol] = time.time()
                            sent_signals.add(signal_key)
                            total_alerts += 1
                            
                            if len(sent_signals) > 100:
                                sent_signals.clear()
                            
                            time.sleep(1)  # Пауза между отправками
                
                # Статистика
                if cycle_count % 6 == 0:
                    print(Fore.CYAN + f"\n📈 Статистика: циклов: {cycle_count}, алертов: {total_alerts}\n")
            
            # Пауза
            elapsed = time.time() - cycle_start
            time.sleep(max(0.1, INTERVAL - elapsed))
            
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n⏹️ Скрипт остановлен.")
            print(Fore.GREEN + f"📊 Итог: циклов: {cycle_count}, алертов: {total_alerts}")
            sys.exit(0)
        except Exception as e:
            print(Fore.RED + f"❌ Ошибка: {e}")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    main()