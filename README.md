# Steam-Recommender
# 🎮 Steam DNA & Freshness Recommender

A Python-based web application that generates a personalized top-tier game list by analyzing your actual Steam gaming experience.

## ✨ Key Features
* **Player DNA Analysis:** The algorithm calculates tag weights based on hours spent in each game (minimum 2-hour filter).
* **Freshness System:** Priority is given to modern titles (releases from the last 5 years).
* **Strict Quality Control:** Only highly trusted games make the cut (20,000+ reviews and 80%+ positive rating).
* **Live Pricing:** Integrated with the Steam Store API to show real-time prices and current discounts.

## 🛠 Tech Stack
* **Frontend/Backend:** [Streamlit](https://streamlit.io/)
* **Data Processing:** Pandas, JSON
* **APIs:** Steam Web API (IPlayerService), Steam Store API (appdetails)

## 📊 Data Source
The game database for analysis is built upon the following dataset:
👉 [Steam Games Dataset (Kaggle)](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) by **fronkongames**.

## 🔒 Security & Privacy
* **No Passwords:** The app only requires your public Steam ID.
* **API Safety:** Your Steam API Key is never shared or stored.
* **Real-time Processing:** Data is processed in the cloud and cleared after your session.
