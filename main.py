import streamlit as st
import json
import os
import requests
import pandas as pd
import time

db_f = 'games.json'
m_p = 120
m_r = 0.80
m_rc = 20000

st.set_page_config(page_title="Steam Recommender", page_icon="🎮", layout="wide")

TR = {
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
        "err_db": f"Файл {db_f} не найден!",
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
        "err_db": f"File {db_f} not found!",
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

@st.cache_data
def get_db():
    if not os.path.exists(db_f):
        return None
    with open(db_f, 'r', encoding='utf-8') as f:
        return json.load(f)

@st.cache_data(ttl=3600)
def get_ug(ak, sid):
    u = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    p = {'key': ak, 'steamid': sid, 'format': 'json', 'include_played_free_games': 1}
    try:
        r = requests.get(u, params=p)
        d = r.json()
        return d.get('response', {}).get('games', [])
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

def get_p(aid, cc='us'):
    u = "https://store.steampowered.com/api/appdetails"
    p = {'appids': aid, 'cc': cc}
    try:
        r = requests.get(u, params=p)
        d = r.json()
        if d and d.get(str(aid)) and d[str(aid)].get('success'):
            gd = d[str(aid)]['data']
            if gd.get('is_free'):
                return "Free", 0
            pi = gd.get('price_overview')
            if pi:
                return pi.get('final_formatted', 'N/A'), pi.get('discount_percent', 0)
        return "N/A", 0
    except Exception:
        return "Error", 0

def calc_tw(ug, db):
    tp = {}
    vc = 0
    for g in ug:
        pt = g.get('playtime_forever', 0)
        aid = str(g.get('appid'))
        if pt < m_p:
            continue
        if aid in db:
            vc += 1
            gd = db[aid]
            tg = gd.get('tags', [])
            if isinstance(tg, dict):
                tg = list(tg.keys())
            for t in tg:
                tp[t] = tp.get(t, 0) + pt
    stg = sorted(tp.items(), key=lambda x: x[1])
    tw = {t: rank + 1 for rank, (t, time) in enumerate(stg)}
    return tw, vc

def find_r(db, tw, oid, my):
    cnd = []
    cy = 2026 
    for aid, d in db.items():
        if str(aid) in oid:
            continue
        rd = d.get('release_date', '1900')
        try:
            ry = int(str(rd)[-4:])
        except:
            ry = 1900
        if ry < my:
            continue
        pos = d.get('positive', 0)
        neg = d.get('negative', 0)
        trv = pos + neg
        if trv == 0:
            continue
        rtg = pos / trv
        if trv < m_rc or rtg < m_r:
            continue
        gt = d.get('tags', [])
        if isinstance(gt, dict):
            gt = list(gt.keys())
        if not gt:
            continue
        cws = sum(tw.get(t, 0) for t in gt)
        acs = cws / len(gt)
        ad = cy - ry
        fb = 1.0
        if ad <= 5:
            fb = 1.2
        elif ad > 10:
            fb = 0.9
        fs = acs * fb
        cnd.append({
            'name': d.get('name'),
            'appid': aid,
            'score': fs,
            'rating_val': rtg,
            'reviews': trv,
            'release_year': ry,
            'link': f"https://store.steampowered.com/app/{aid}/"
        })
    cnd.sort(key=lambda x: x['score'], reverse=True)
    return cnd

def main():
    with st.sidebar:
        lc = st.radio("Language / Язык", options=["ru", "en"], horizontal=True)
        t = TR[lc]
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
        [data-testid="stMetricValue"] {
            color: #ff4b4b;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.title(t["title"])
    st.markdown(t["desc"])

    with st.sidebar:
        st.header(t["settings"])
        dk = os.getenv("STEAM_API_KEY", "")
        did = os.getenv("STEAM_ID", "")
        
        ak = st.text_input(t["api_key"], value=dk, type="password")
        sid = st.text_input(t["steam_id"], value=did)
        
        lm = st.slider(t["limit"], 5, 200, 20)
        yt = st.slider(t["year"], 2000, 2026, 2015)
        cp = st.checkbox(t["price_check"])
        
        st.info(f"{t['api_info']} https://steamcommunity.com/dev/apikey")

    db = get_db()
    if not db:
        st.error(t["err_db"])
        st.stop()
    
    if st.button(t["btn_find"], type="primary"):
        if not ak or not sid:
            st.warning(t["warn_input"])
            st.stop()
            
        with st.spinner(t["spin_profile"]):
            ug = get_ug(ak, sid)
        
        if not ug:
            st.error(t["err_profile"])
            st.stop()
            
        oids = {str(g['appid']) for g in ug}
        
        with st.spinner(t["spin_analyze"]):
            utw, vc = calc_tw(ug, db)
            
            if not utw:
                st.warning(t["warn_data"])
                st.stop()
                
            recs = find_r(db, utw, oids, yt)

        c1, c2 = st.columns(2)
        c1.metric(t["stat_lib"], len(ug))
        c2.metric(t["stat_used"], vc)
        
        tt = sorted(utw.items(), key=lambda x: x[1], reverse=True)[:5]
        st.subheader(t["genres"])
        st.write(", ".join([f"**{tg}**" for tg, w in tt]))

        st.divider()
        st.subheader(f"{t['top_header']} ({lm})")

        tr_lst = recs[:lm]
        
        if cp:
            pb = st.progress(0)
            st_t = st.empty()
            
            for i, g in enumerate(tr_lst):
                st_t.text(f"{t['status_price']} {g['name']}...")
                pr, dsc = get_p(g['appid'], cc=t["currency"])
                g['price'] = pr
                g['discount'] = f"-{dsc}%" if dsc > 0 else ""
                pb.progress((i + 1) / lm)
                time.sleep(0.1) 
            
            st_t.empty()
            pb.empty()

        dd = []
        for g in tr_lst:
            rw = {
                "Score": round(g['score'], 2),
                t["col_name"]: g['name'],
                t["col_rating"]: f"{g['rating_val']:.0%}",
                t["col_reviews"]: g['reviews'],
                "Link": g['link']
            }
            if cp:
                rw[t["col_price"]] = g.get('price', 'N/A')
                rw[t["col_discount"]] = g.get('discount', '')
            dd.append(rw)

        df_out = pd.DataFrame(dd)

        st.dataframe(
            df_out,
            column_config={
                "Link": st.column_config.LinkColumn(t["col_link"]),
                "Score": st.column_config.ProgressColumn(
                    t["col_score"],
                    format="%.2f",
                    min_value=0,
                    max_value=max(g['score'] for g in tr_lst),
                ),
            },
            hide_index=True,
            use_container_width=True
        )

if __name__ == "__main__":
    main()
