import streamlit as st
import json
import os
import requests
import pandas as pd
import time
#py -m streamlit run main.py

# --- Настройки ---
GAMES_DB_FILE = 'games.json'
MIN_PLAYTIME_MINUTES = 120  # 2 часа
MIN_RATING_PERCENT = 0.80   # 80%
MIN_REVIEWS_COUNT = 20000

# Настройка страницы
st.set_page_config(
    page_title="Steam Recommender",
    page_icon="🎮",
    layout="wide"
)

# --- Функции с кэшированием (чтобы не грузить данные каждый раз) ---

@st.cache_data
def load_games_database():
    if not os.path.exists(GAMES_DB_FILE):
        return None
    with open(GAMES_DB_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

@st.cache_data(ttl=3600) # Кэш на 1 час для запросов к API
def get_user_games(api_key, steam_id):
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        'key': api_key,
        'steamid': steam_id,
        'format': 'json',
        'include_played_free_games': 1
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        return data.get('response', {}).get('games', [])
    except Exception as e:
        st.error(f"Ошибка API: {e}")
        return []

def get_actual_price(app_id):
    """Получает актуальную цену (без кэширования, так как цена меняется)"""
    url = "https://store.steampowered.com/api/appdetails"
    params = {'appids': app_id, 'cc': 'us', 'l': 'russian'} # cc=ru можно поставить для рублей
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data and data.get(str(app_id)) and data[str(app_id)].get('success'):
            game_data = data[str(app_id)]['data']
            if game_data.get('is_free'):
                return "Free", 0
            price_info = game_data.get('price_overview')
            if price_info:
                return price_info.get('final_formatted', 'N/A'), price_info.get('discount_percent', 0)
        return "N/A", 0
    except Exception:
        return "Error", 0

# --- Основная логика анализа (без изменений логики, только структура) ---

def calculate_tag_weights(user_games, all_games_db):
    tag_playtime = {}
    valid_games_count = 0
    
    for game in user_games:
        playtime = game.get('playtime_forever', 0)
        app_id = str(game.get('appid'))
        
        if playtime < MIN_PLAYTIME_MINUTES:
            continue
            
        if app_id in all_games_db:
            valid_games_count += 1
            game_details = all_games_db[app_id]
            tags = game_details.get('tags', [])
            
            if isinstance(tags, dict):
                tags = list(tags.keys())
                
            for tag in tags:
                tag_playtime[tag] = tag_playtime.get(tag, 0) + playtime

    sorted_tags = sorted(tag_playtime.items(), key=lambda x: x[1])
    tag_weights = {tag: rank + 1 for rank, (tag, time) in enumerate(sorted_tags)}
    
    return tag_weights, valid_games_count

def find_recommendations(all_games_db, tag_weights, owned_ids, min_year):
    candidates = []
    
    # Определяем текущий год для расчета "свежести"
    current_year = 2026 
    
    for app_id, data in all_games_db.items():
        if str(app_id) in owned_ids:
            continue

        # --- ЛОГИКА ОБРАБОТКИ ДАТЫ ---
        raw_date = data.get('release_date', '1900')
        try:
            # Извлекаем год (последние 4 цифры)
            release_year = int(str(raw_date)[-4:])
        except:
            release_year = 1900

        # 1. Жесткий фильтр по году (из слайдера)
        if release_year < min_year:
            continue
        # -----------------------------

        positive = data.get('positive', 0)
        negative = data.get('negative', 0)
        total_reviews = positive + negative
        
        if total_reviews == 0:
            continue
            
        rating = positive / total_reviews
        if total_reviews < MIN_REVIEWS_COUNT or rating < MIN_RATING_PERCENT:
            continue
            
        game_tags = data.get('tags', [])
        if isinstance(game_tags, dict):
            game_tags = list(game_tags.keys())
            
        if not game_tags:
            continue
            
        # Расчет базового веса по тегам
        current_weight_sum = sum(tag_weights.get(tag, 0) for tag in game_tags)
        avg_score = current_weight_sum / len(game_tags)

        # --- МОДИФИКАТОР РЕЙТИНГА ДЛЯ НОВЫХ ИГР ---
        # Чем ближе игра к текущему году, тем выше бонус (до +20% к score)
        age_diff = current_year - release_year
        freshness_bonus = 1.0
        if age_diff <= 5: # Если игре меньше 5 лет
            freshness_bonus = 1.2 # Даем 20% бонус к баллу
        elif age_diff > 10:
            freshness_bonus = 0.9 # Старым играм (10+ лет) чуть снижаем приоритет
        
        final_score = avg_score * freshness_bonus
        # ------------------------------------------
        
        candidates.append({
            'name': data.get('name'),
            'appid': app_id,
            'score': final_score,
            'rating_val': rating,
            'reviews': total_reviews,
            'release_year': release_year, # Добавляем для вывода в таблицу
            'link': f"https://store.steampowered.com/app/{app_id}/"
        })
        
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates
# --- Интерфейс приложения ---

def main():
    st.title("🎮 AI Рекомендатор Steam Игр")
    st.markdown("Анализирует вашу библиотеку и ищет похожие игры на основе веса тегов и времени в игре.")

    # Сайдбар для ввода данных
    with st.sidebar:
        st.header("Настройки")
        # Пытаемся взять значения из secrets или .env, если нет - поле ввода пустое
        default_key = os.getenv("STEAM_API_KEY", "")
        default_id = os.getenv("STEAM_ID", "")
        
        api_key = st.text_input("Steam API Key", value=default_key, type="password")
        steam_id = st.text_input("Steam ID (64-bit)", value=default_id)
        
        limit = st.slider("Сколько игр показать?", 5, 200, 20)
        year_threshold = st.slider("Игры не старше какого года?", 2000, 2026, 2015)
        check_price = st.checkbox("Проверять актуальную цену (медленнее)")
        
        st.info("API Key можно получить здесь: https://steamcommunity.com/dev/apikey")

    # Проверка БД
    all_games_db = load_games_database()
    if not all_games_db:
        st.error(f"Файл {GAMES_DB_FILE} не найден! Пожалуйста, положите его в папку со скриптом.")
        st.stop()
    
    # Кнопка запуска
    if st.button("🔍 Найти игры", type="primary"):
        if not api_key or not steam_id:
            st.warning("Пожалуйста, введите API Key и Steam ID.")
            st.stop()
            
        with st.spinner('Загрузка профиля Steam...'):
            user_games = get_user_games(api_key, steam_id)
        
        if not user_games:
            st.error("Не удалось получить список игр. Проверьте настройки приватности профиля или ID.")
            st.stop()
            
        owned_ids = {str(g['appid']) for g in user_games}
        
        with st.spinner('Анализ вкусов и поиск похожих игр...'):
            user_tag_weights, valid_count = calculate_tag_weights(user_games, all_games_db)
            
            if not user_tag_weights:
                st.warning("Недостаточно данных (слишком мало сыгранных часов в известные игры).")
                st.stop()
                
            recommendations = find_recommendations(all_games_db, user_tag_weights, owned_ids, year_threshold)

        # Вывод статистики
        col1, col2 = st.columns(2)
        col1.metric("Игр в библиотеке", len(user_games))
        col2.metric("Использовано для анализа", valid_count)
        
        # Топ 5 любимых тегов
        top_tags = sorted(user_tag_weights.items(), key=lambda x: x[1], reverse=True)[:5]
        st.subheader("Ваши любимые жанры:")
        st.write(", ".join([f"**{tag}**" for tag, weight in top_tags]))

        st.divider()
        st.subheader(f"Топ {limit} рекомендаций")

        # Подготовка данных для таблицы
        top_recs = recommendations[:limit]
        
        # Если нужно проверить цены
        if check_price:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, game in enumerate(top_recs):
                status_text.text(f"Проверяем цену для: {game['name']}...")
                price, discount = get_actual_price(game['appid'])
                game['price'] = price
                game['discount'] = f"-{discount}%" if discount > 0 else ""
                progress_bar.progress((idx + 1) / limit)
                time.sleep(0.1) # Чтобы не словить бан API
            
            status_text.empty()
            progress_bar.empty()

        # Создаем красивый DataFrame
        display_data = []
        for game in top_recs:
            row = {
                "Score": round(game['score'], 2),
                "Название": game['name'],
                "Рейтинг": f"{game['rating_val']:.0%}",
                "Отзывы": game['reviews'],
                "Link": game['link']
            }
            if check_price:
                row["Цена"] = game.get('price', 'N/A')
                row["Скидка"] = game.get('discount', '')
            display_data.append(row)

        df = pd.DataFrame(display_data)

        # Конфигурация колонок таблицы для Streamlit
        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn("Ссылка в Steam"),
                "Score": st.column_config.ProgressColumn(
                    "Совместимость",
                    format="%.2f",
                    min_value=0,
                    max_value=max(g['score'] for g in top_recs),
                ),
            },
            hide_index=True,
            use_container_width=True
        )

if __name__ == "__main__":
    main()