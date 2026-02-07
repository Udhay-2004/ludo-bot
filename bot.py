import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

TOKEN=os.getenv("TOKEN")
BOT_USERNAME="LudoooXBot"

games={}
leaderboard={}

# --------- BOARD SETTINGS ---------

TRACK_LENGTH=52

# Diagonal safe stars
SAFE_TILES={
    0,8,13,21,26,34,39,47
}

EMOJIS=["🟥","🟦","🟩","🟨"]

# ---------------- GAME ----------------

class LudoGame:
    def __init__(self,creator):
        self.players=[]
        self.positions={}
        self.turn=0
        self.started=False
        self.names={}
        self.colors={}
        self.creator=creator

    def current(self):
        return self.players[self.turn]

    def next(self):
        self.turn=(self.turn+1)%len(self.players)

# ---------------- HELPERS ----------------

def valid_cmd(update,cmd):
    return update.message and update.message.text.startswith(f"/{cmd}@{BOT_USERNAME}")

def name_of(user):
    return f"{user.first_name} (@{user.username})" if user.username else user.first_name

def fix_turn(g):
    if g.turn>=len(g.players):
        g.turn=0

# ---------------- TRACK ----------------

def build_track(g):

    t=["⬜"]*TRACK_LENGTH

    for p,pos in g.positions.items():
        if 0<=pos<TRACK_LENGTH:
            t[pos]=g.colors[p]

    for s in SAFE_TILES:
        if s<TRACK_LENGTH and t[s]=="⬜":
            t[s]="⭐"

    # 4-row board
    return (
        "🏁"+"".join(t[:13])+"\n"+
        "".join(t[13:26])+"\n"+
        "".join(t[26:39])+"\n"+
        "".join(t[39:52])+"🏆"
    )

# ---------------- ADMIN CHECK ----------------

async def is_admin(update,user_id):
    m=await update.effective_chat.get_member(user_id)
    return m.status in ["administrator","creator"]

# ---------------- START ----------------

async def start(update,context):

    if not valid_cmd(update,"start"): return

    chat=update.effective_chat.id
    games[chat]=LudoGame(update.effective_user.id)

    kb=[[InlineKeyboardButton("Join",callback_data="join_btn")],
        [InlineKeyboardButton("Start",callback_data="start_game")]]

    await update.message.reply_text(
        "🎲 Lobby open!\nUse /join@LudoooXBot",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------------- JOIN ----------------

async def join_cmd(update,context):

    if not valid_cmd(update,"join"): return

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g: return

    if user.id in g.players: return
    if len(g.players)>=4: return

    c=EMOJIS[len(g.players)]
    g.players.append(user.id)
    g.positions[user.id]=-1
    g.names[user.id]=name_of(user)
    g.colors[user.id]=c

    await update.message.reply_text(f"{c} {g.names[user.id]} joined!")

# ---------------- DICE ----------------

async def handle_dice(update,context):

    msg=update.message
    if msg.dice.emoji!="🎲": return

    chat=msg.chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g or not g.started or user.id!=g.current(): return

    await roll(msg,g,user.id,msg.dice.value)

# ---------------- ROLL ----------------

async def roll(msg,g,player,dice):

    pos=g.positions[player]

    text=f"{g.colors[player]} {g.names[player]} rolled {dice}\n"

# ENTER BOARD
    if pos==-1:
        if dice!=6:
            g.next()
            await msg.reply_text(text+"Need 6")
            await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
            return
        pos=0

# MOVE
    else:
        if pos+dice>TRACK_LENGTH:
            g.next()
            await msg.reply_text(text+"Need exact")
            await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
            return
        pos+=dice

# KILL CHECK (no safety near end!)
    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"💥 Killed {g.names[p]}\n"

# WIN
    if pos==TRACK_LENGTH:
        name=g.names[player]
        leaderboard[name]=leaderboard.get(name,0)+1

        await msg.reply_text(f"🥇 {name} finished!")

        g.players.remove(player)
        g.positions.pop(player,None)

        if len(g.players)<=1:
            await msg.reply_text("🏁 Game Over")
            del games[msg.chat.id]
            return

        fix_turn(g)
        await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
        return

    g.positions[player]=pos

    if dice!=6:
        g.next()

    await msg.reply_text(
        text+build_track(g)+
        f"\n👉 {g.names[g.current()]}'s turn 🎲"
    )

# ---------------- BUTTONS ----------------

async def button(update,context):

    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    user=q.from_user
    g=games.get(chat)

    if not g: return

    if q.data=="join_btn":
        if user.id not in g.players and len(g.players)<4:
            c=EMOJIS[len(g.players)]
            g.players.append(user.id)
            g.positions[user.id]=-1
            g.names[user.id]=name_of(user)
            g.colors[user.id]=c
            await q.message.reply_text(f"{c} {g.names[user.id]} joined!")

    elif q.data=="start_game":
        if len(g.players)<2: return
        g.started=True
        await q.message.reply_text(
            build_track(g)+
            f"\n👉 {g.names[g.current()]}'s turn 🎲"
        )

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("join",join_cmd))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Ludo upgraded board running...")
app.run_polling()

