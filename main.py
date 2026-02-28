#!/usr/bin/env python3
"""
Telegram Bot - TronPanel + TRX Bot
Sadece Panel 2, güncellenmiş sitelerle ve Railway uyumlu
"""

import ssl
import asyncio
from datetime import datetime, timedelta
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

# ==================== ENV / SABİT DEĞERLER ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PANEL2_USERNAME = os.getenv("TRONPANEL_USER")
PANEL2_PASSWORD = os.getenv("TRONPANEL_PASS")

PANEL2_URL = "https://win.tronpanel.com"

if not BOT_TOKEN or not PANEL2_USERNAME or not PANEL2_PASSWORD:
    raise RuntimeError("Railway environment variables eksik! BOT_TOKEN, TRONPANEL_USER, TRONPANEL_PASS ekleyin.")

# ==================== PANEL SITE ID'LERI ====================
PANEL2_SITES = {
    "izmir": {"id": "9c69c72a-5f88-4130-bf9b-cef6755ffb78", "name": "İzmir(B)"},
    "adana": {"id": "b724ae8c-bd4b-4147-acb6-dfb72656c5d5", "name": "Adana(W)"},
    "eskisehir": {"id": "d36896e8-8500-4905-bc7c-c0988214b213", "name": "Eskişehir(T)"},
    "istanbul": {"id": "7af7e276-7dea-4fe2-8762-636e324917ac", "name": "İstanbul(O)"},
    "aydin": {"id": "d3ae4fcc-8224-48a4-936b-7f424ea8b26c", "name": "Aydın(L)"},
    "fiksturbet": {"id": "04710a73-5ccf-4aff-80d1-0380e75a503e", "name": "FikstürBet"},
    "bayconticasino": {"id": "0e9ac775-120b-45c1-bd60-90d2e4a0f23c", "name": "BayContiCasino"},
    "maximcasino": {"id": "759fe569-589b-4c28-acf5-2862f4ea5351", "name": "MaximCasino"},
    "rinabet": {"id": "ec567fc7-972f-48d5-b505-c4c7db2a5606", "name": "Rinabet"},
     "Denver": {"id": "dadac705-842f-4317-8564-8d169fed4f0f", "name": "Denver"},
}

# ==================== TL FORMAT ====================
def format_number(value):
    if value is None:
        return "0 TL"
    try:
        num = int(float(str(value).replace(',', '').replace(' ', '')))
        return f"{num:,}".replace(",", ".") + " TL"
    except:
        return f"{value} TL"

# ==================== PANEL VERI CEKME ====================
async def fetch_site_data(session, reports_url, api_csrf, site_info, today):
    try:
        async with session.post(
            reports_url,
            headers={"X-CSRF-TOKEN": api_csrf},
            json={"site": site_info["id"], "dateone": today, "datetwo": today, "bank": "", "user": ""}
        ) as r:
            data = await r.json()
            dep = data.get("deposit", [0,0,0,0])
            wth = data.get("withdraw", [0,0,0,0])
            return site_info["name"], {
                "yat": dep[0],
                "yat_adet": int(float(dep[2])) if len(dep) > 2 and dep[2] else 0,
                "cek": wth[0],
                "cek_adet": int(float(wth[2])) if len(wth) > 2 and wth[2] else 0
            }
    except Exception as e:
        print(f"Site verisi çekilemedi ({site_info['name']}): {e}")
        return site_info["name"], {"yat":0,"yat_adet":0,"cek":0,"cek_adet":0}

async def fetch_panel_data(panel_url, username, password, sites, use_plural=False):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_url}/login"
    reports_url = f"{panel_url}/{'reports' if use_plural else 'report'}/quickly"

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(login_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            csrf = soup.find("input", {"name": "_token"})
            csrf_token = csrf["value"] if csrf else ""
        await session.post(login_url, data={"_token": csrf_token, "email": username, "password": password})
        async with session.get(reports_url) as r:
            soup = BeautifulSoup(await r.text(), "html.parser")
            meta = soup.find("meta", {"name":"csrf-token"})
            api_csrf = meta["content"] if meta else ""
        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
        tasks = [fetch_site_data(session, reports_url, api_csrf, s, today) for s in sites.values()]
        results = await asyncio.gather(*tasks)
        return dict(results)

async def fetch_all_data():
    try:
        panel2_data = await fetch_panel_data(PANEL2_URL, PANEL2_USERNAME, PANEL2_PASSWORD, PANEL2_SITES, False)
    except Exception as e:
        print(f"Panel veri çekme hatası: {e}")
        panel2_data = {}
    today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
    return today, panel2_data

# ==================== TELEGRAM HANDLER ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎰 TronPanel Veri Bot\n\n/veri - Günlük TL verileri\n/abi - Özel mesaj"
    )

async def veri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Veriler çekiliyor...")
    try:
        date, panel2_data = await fetch_all_data()
        text = f"*{date}*\n\nPANEL 2 (TronPanel)\n\n"
        for k,v in panel2_data.items():
            text += f"{k}\nYat: {format_number(v['yat'])} ({v['yat_adet']} adet)\nÇek: {format_number(v['cek'])} ({v['cek_adet']} adet)\n\n"
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        print(f"Hata: {e}")
        await msg.edit_text("❌ Veriler alınırken hata oluştu")

async def abi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👑 @atmkrnca 👑")

# ==================== MAIN ====================
def main():
    print("🤖 TronPanel Veri Bot başlatılıyor...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("veri", veri))
    app.add_handler(CommandHandler("abi", abi))
    app.run_polling()

if __name__ == "__main__":
    main()

