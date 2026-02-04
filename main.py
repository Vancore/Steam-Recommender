import streamlit as st
import json
import os
import requests
import pandas as pd
import time

GAMES_DB_FILE = 'games.json'
MIN_PLAYTIME_MINUTES = 120
MIN_RATING_PERCENT = 0.80
MIN_REVIEWS_COUNT = 20000

st.set_page_config(page_title="Steam Recommender", page_icon="🎮", layout="wide")

TRANSLATIONS = {
    "ru": {
        "title": "🎮 AI Рекомендатор Steam",
        "desc": "Анализирует вашу библиотеку и ищет похожие игры на основе веса тегов и времени в игре.",
        "settings": "Настройки",
        "api_key": "Steam API Key",
        "steam_id": "Steam ID (64-bit)",
        "limit": "Сколько игр показать?",
        "year": "Игры не старше какого года?",
        "price_check": "Проверять актуальную цену (медленнее)",
        "api_info": "API Key можно получить здесь:",
        "btn_find": "🔍 Найти игры",
        "err_db": f"Файл {GAMES_DB_FILE} не найден!",
        "warn_input": "Пожалуйста, введите API Key и Steam ID.",
        "spin_profile": "Загрузка профиля Steam...",
        "err_profile": "Не удалось получить список игр. Проверьте настройки приватности.",
        "spin_analyze": "Анализ вкусов и поиск похожих игр...",
        "warn_data": "Недостаточно данных (мало сыгранных часов).",
        "stat_lib": "Игр в библиотеке",
        "stat_used": "Использовано для анализа",
        "genres": "Ваши любимые жанры:",
        "top_header": "Топ рекомендаций",
        "status_price": "Проверяем цену для:",
        "col_score": "Совместимость",
        "col_name": "Название",
        "col_rating": "Рейтинг",
        "col_reviews": "Отзывы",
        "col_link": "Ссылка",
        "col_price": "Цена",
        "col_discount": "Скидка",
        "currency": "ru"
    },
    "en": {
        "title": "🎮 Steam AI Recommender",
        "desc": "Analyzes your library to find similar games based on tag weights and playtime.",
        "settings": "Settings",
        "api_key": "Steam API Key",
        "steam_id": "Steam ID (64-bit)",
        "limit": "How many games to show?",
        "year": "Games released after:",
        "price_check": "Check actual price (slower)",
        "api_info": "Get your API Key here:",
        "btn_find": "🔍 Find Games",
        "err_db": f"File {GAMES_DB_FILE} not found!",
        "warn_input": "Please enter API Key and Steam ID.",
        "spin_profile": "Loading Steam profile...",
        "err_profile": "Failed to fetch games. Check privacy settings.",
        "spin_analyze": "Analyzing tastes and finding games...",
        "warn_data": "Not enough data (playtime is too low).",
        "stat_lib": "Games in Library",
        "stat_used": "Used for analysis",
        "genres": "Your favorite genres:",
        "top_header": "Top Recommendations",
        "status_price": "Checking price for:",
        "col_score": "Match Score",
        "col_name": "Name",
        "col_rating": "Rating",
        "col_reviews": "Reviews",
        "col_link": "Link",
        "col_price": "Price",
        "col_discount": "Discount",
        "currency": "us"
    }
}

# --- Функции ---

@st.cache_data
def load_games_database():
    if not os.path.exists(GAMES_DB_FILE):
        return None
    with open(GAMES_DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

@st.cache_data(ttl=3600)
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
        st.error(f"API Error: {e}")
        return []

def get_actual_price(app_id, currency_code='us'):
    """Получает цену. currency_code: 'us' (USD) или 'ru' (RUB)"""
    url = "https://store.steampowered.com/api/appdetails"
    params = {'appids': app_id, 'cc': currency_code}
    
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
    current_year = 2026 
    
    for app_id, data in all_games_db.items():
        if str(app_id) in owned_ids:
            continue

        raw_date = data.get('release_date', '1900')
        try:
            release_year = int(str(raw_date)[-4:])
        except:
            release_year = 1900

        if release_year < min_year:
            continue

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
            
        current_weight_sum = sum(tag_weights.get(tag, 0) for tag in game_tags)
        avg_score = current_weight_sum / len(game_tags)

        age_diff = current_year - release_year
        freshness_bonus = 1.0
        if age_diff <= 5:
            freshness_bonus = 1.2
        elif age_diff > 10:
            freshness_bonus = 0.9
        
        final_score = avg_score * freshness_bonus
        
        candidates.append({
            'name': data.get('name'),
            'appid': app_id,
            'score': final_score,
            'rating_val': rating,
            'reviews': total_reviews,
            'release_year': release_year,
            'link': f"https://store.steampowered.com/app/{app_id}/"
        })
        
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates

def main():
    with st.sidebar:
        lang_code = st.radio("Language / Язык", options=["ru", "en"], horizontal=True)
        txt = TRANSLATIONS[lang_code]
        st.divider()
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5)), 
            url("https://cdn.akamai.steamstatic.com/store/home/store_home_share.jpg");
            background-size: cover;
            background-attachment: fixed;
        }
        /* Делаем карточки чуть прозрачными, чтобы фон слегка просвечивал */
        [data-testid="stMetricValue"] {
            color: #ff4b4b;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.title(txt["title"])
    st.markdown(txt["desc"])

    with st.sidebar:
        st.header(txt["settings"])
        default_key = os.getenv("STEAM_API_KEY", "")
        default_id = os.getenv("STEAM_ID", "")
        
        api_key = st.text_input(txt["api_key"], value=default_key, type="password")
        steam_id = st.text_input(txt["steam_id"], value=default_id)
        
        limit = st.slider(txt["limit"], 5, 200, 20)
        year_threshold = st.slider(txt["year"], 2000, 2026, 2015)
        check_price = st.checkbox(txt["price_check"])
        
        st.info(f"{txt['api_info']} https://steamcommunity.com/dev/apikey")

    all_games_db = load_games_database()
    if not all_games_db:
        st.error(txt["err_db"])
        st.stop()
    
    if st.button(txt["btn_find"], type="primary"):
        if not api_key or not steam_id:
            st.warning(txt["warn_input"])
            st.stop()
            
        with st.spinner(txt["spin_profile"]):
            user_games = get_user_games(api_key, steam_id)
        
        if not user_games:
            st.error(txt["err_profile"])
            st.stop()
            
        owned_ids = {str(g['appid']) for g in user_games}
        
        with st.spinner(txt["spin_analyze"]):
            user_tag_weights, valid_count = calculate_tag_weights(user_games, all_games_db)
            
            if not user_tag_weights:
                st.warning(txt["warn_data"])
                st.stop()
                
            recommendations = find_recommendations(all_games_db, user_tag_weights, owned_ids, year_threshold)

        col1, col2 = st.columns(2)
        col1.metric(txt["stat_lib"], len(user_games))
        col2.metric(txt["stat_used"], valid_count)
        
        top_tags = sorted(user_tag_weights.items(), key=lambda x: x[1], reverse=True)[:5]
        st.subheader(txt["genres"])
        st.write(", ".join([f"**{tag}**" for tag, weight in top_tags]))

        st.divider()
        st.subheader(f"{txt['top_header']} ({limit})")

        top_recs = recommendations[:limit]
        
        if check_price:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, game in enumerate(top_recs):
                status_text.text(f"{txt['status_price']} {game['name']}...")
                price, discount = get_actual_price(game['appid'], currency_code=txt["currency"])
                game['price'] = price
                game['discount'] = f"-{discount}%" if discount > 0 else ""
                progress_bar.progress((idx + 1) / limit)
                time.sleep(0.1) 
            
            status_text.empty()
            progress_bar.empty()

        display_data = []
        for game in top_recs:
            row = {
                "Score": round(game['score'], 2),
                txt["col_name"]: game['name'],
                txt["col_rating"]: f"{game['rating_val']:.0%}",
                txt["col_reviews"]: game['reviews'],
                "Link": game['link']
            }
            if check_price:
                row[txt["col_price"]] = game.get('price', 'N/A')
                row[txt["col_discount"]] = game.get('discount', '')
            display_data.append(row)

        df = pd.DataFrame(display_data)

        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn(txt["col_link"]),
                "Score": st.column_config.ProgressColumn(
                    txt["col_score"],
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
