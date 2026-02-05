import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

TOKEN = os.getenv("TOKEN")

games = {}
leaderboard = {}

TRACK_LENGTH = 20
SAFE_TILES = {5,10,15}

EMOJIS = ["🟥","🟦","🟩","🟨"]

# ---------------- GAME CLASS ----------------

class LudoGame:
    def __init__(self):
        self.players=[]
        self.positions={}
        self.turn=0
        self.started=False

    def current(self):
        return self.players[self.turn]

    def next(self):
        self.turn=(self.turn+1)%len(self.players)

# ---------------- BUILD TRACK ----------------

def build_track(game):
    track=["⬜"]*TRACK_LENGTH

    for i,(p,pos) in enumerate(game.positions.items()):
        if 0<=pos<TRACK_LENGTH:
            track[pos]=EMOJIS[i]

    for s in SAFE_TILES:
        if track[s]=="⬜":
            track[s]="⭐"

    return "🏁"+"".join(track)+"🏆"

# ---------------- HELP ----------------

async def help_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start lobby\n/help help\n/rules rules\n/stats leaderboard"
    )

# ---------------- RULES ----------------

async def rules(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Roll 🎲\nLand on player to kill\n⭐ = safe tiles\nReach 🏆 to win"
    )

# ---------------- STATS ----------------

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not leaderboard:
        await update.message.reply_text("No stats to show.")
        return

    text="🏆 Leaderboard\n"
    for i,(p,w) in enumerate(sorted(
        leaderboard.items(),
        key=lambda x:x[1],
        reverse=True
    ),1):
        text+=f"{i}. {p} - {w}\n"

    await update.message.reply_text(text)

# ---------------- START ----------------

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type=="private":
        await update.message.reply_text("Use in group only")
        return

    chat=update.effective_chat.id
    games[chat]=LudoGame()

    kb=[[InlineKeyboardButton("Join",callback_data="join")],
        [InlineKeyboardButton("Start",callback_data="begin")]]

    await update.message.reply_text(
        "🎲 Ludo Lobby",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------------- BUTTONS ----------------

async def button(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    user=q.from_user.first_name
    g=games.get(chat)

    if not g: return

    if q.data=="join":
        if user in g.players: return
        if len(g.players)>=4:
            await q.answer("Max 4")
            return

        g.players.append(user)
        g.positions[user]=-1

        await q.edit_message_text(
            "Players:\n"+"\n".join(g.players),
            reply_markup=q.message.reply_markup
        )

    elif q.data=="begin":
        if len(g.players)<2:
            await q.answer("Need 2+")
            return

        g.started=True
        await q.edit_message_text(
            f"Game started!\n{g.current()} turn\nSend 🎲"
        )

# ---------------- DICE ----------------

async def handle_dice(update:Update,context:ContextTypes.DEFAULT_TYPE):
    m=update.message
    if m.dice.emoji!="🎲": return

    chat=m.chat.id
    user=update.effective_user.first_name
    g=games.get(chat)

    if not g or not g.started: return
    if user!=g.current(): return

    await roll(m,g,user,m.dice.value)

# ---------------- ROLL ----------------

async def roll(msg,g,player,dice):
    chat=msg.chat.id
    pos=g.positions[player]

    text=f"{player} rolled {dice}\n"

    if pos==-1:
        if dice==6:
            pos=0
            text+="Entered!\n"
        else:
            text+="Need 6\n"
    else:
        pos+=dice

    # Kill
    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"Killed {p}\n"

    if pos>=TRACK_LENGTH:
        leaderboard[player]=leaderboard.get(player,0)+1
        await msg.reply_text(f"🏆 {player} wins!")
        del games[chat]
        return

    g.positions[player]=pos

    track=build_track(g)

    if dice!=6:
        g.next()

    await msg.reply_text(
        text+"\n"+track+
        f"\nNext: {g.current()}"
    )

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("help",help_cmd))
app.add_handler(CommandHandler("rules",rules))
app.add_handler(CommandHandler("stats",stats))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Bot running...")
app.run_polling()
