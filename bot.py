import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

TOKEN=os.getenv("TOKEN")

games={}
leaderboard={}

TRACK_LENGTH=40
SAFE_TILES={5,10,15,20,25,30,35}
EMOJIS=["🟥","🟦","🟩","🟨"]

# ---------------- GAME ----------------

class LudoGame:
    def __init__(self):
        self.players=[]
        self.positions={}
        self.turn=0
        self.started=False
        self.usernames={}
        self.colors={}

    def current(self): return self.players[self.turn]
    def next(self): self.turn=(self.turn+1)%len(self.players)

# ---------------- TAG ----------------

def tag(user):
    if user.username:
        return "@"+user.username
    return user.first_name

# ---------------- BUILD TRACK ----------------

def build_track(g):
    t=["⬜"]*TRACK_LENGTH

    for p,pos in g.positions.items():
        if 0<=pos<TRACK_LENGTH:
            t[pos]=g.colors[p]

    for s in SAFE_TILES:
        if t[s]=="⬜":
            t[s]="⭐"

    l1="".join(t[:10])
    l2="".join(t[10:20])
    l3="".join(t[20:30])
    l4="".join(t[30:40])

    return f"🏁{l1}\n{l2}\n{l3}\n{l4}🏆"

# ---------------- STATS ----------------

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if not leaderboard:
        await update.message.reply_text("No stats to show.")
        return

    text="🏆 Leaderboard\n\n"

    sorted_lb=sorted(
        leaderboard.items(),
        key=lambda x:x[1],
        reverse=True
    )

    for i,(uid,wins) in enumerate(sorted_lb,1):

        name=f"User {uid}"
        color=""

        for g in games.values():
            if uid in g.usernames:
                name=g.usernames[uid]
                color=g.colors.get(uid,"")
                break

        text+=f"{i}. {color} {name} — {wins} wins\n"

    await update.message.reply_text(text)

# ---------------- START ----------------

async def start(update,context):
    if update.effective_chat.type=="private":
        await update.message.reply_text("Use me in a group to play 🎲")
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

async def button(update,context):
    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    user=q.from_user
    g=games.get(chat)

    if not g: return

    if q.data=="join":

        if user.id in g.players: return
        if len(g.players)>=4:
            await q.answer("Max 4 players")
            return

        color=EMOJIS[len(g.players)]

        g.players.append(user.id)
        g.positions[user.id]=-1
        g.usernames[user.id]=tag(user)
        g.colors[user.id]=color

        plist="\n".join(
            f"{g.colors[p]} {g.usernames[p]}"
            for p in g.players
        )

        await q.edit_message_text(
            "Players:\n"+plist,
            reply_markup=q.message.reply_markup
        )

    elif q.data=="begin":

        if len(g.players)<2:
            await q.answer("Need 2+ players")
            return

        g.started=True

        await q.edit_message_text(
            f"Game started!\n👉 {g.usernames[g.current()]}'s turn 🎲"
        )

# ---------------- DICE ----------------

async def handle_dice(update,context):
    m=update.message

    if m.dice.emoji!="🎲": return

    chat=m.chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g or not g.started: return
    if user.id!=g.current(): return

    await roll(m,g,user.id,m.dice.value)

# ---------------- ROLL ----------------

async def roll(msg,g,player,dice):
    chat=msg.chat.id
    pos=g.positions[player]

    text=f"{g.colors[player]} {g.usernames[player]} rolled {dice}\n"
    move=dice

    # chaos boost chance
    if random.random()<0.25:
        move+=2
        text+="🍀 Lucky +2 boost!\n"

    # enter board
    if pos==-1:
        if dice==6:
            pos=0
            text+="Entered!\n"
        else:
            text+="Need 6\n"
            await msg.reply_text(text)
            g.next()
            return
    else:
        if pos+move>TRACK_LENGTH:
            text+="❗ Need exact roll to win\n"
            await msg.reply_text(text)
            g.next()
            return
        pos+=move

    # kill logic
    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"💥 Killed {g.usernames[p]}\n"

    # win
    if pos==TRACK_LENGTH:
        leaderboard[player]=leaderboard.get(player,0)+1
        await msg.reply_text(
            f"🏆 {g.colors[player]} {g.usernames[player]} WINS!"
        )
        del games[chat]
        return

    g.positions[player]=pos

    track=build_track(g)

    if dice!=6:
        g.next()

    await msg.reply_text(
        text+"\n"+track+
        f"\n👉 {g.usernames[g.current()]}'s turn"
    )

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("stats",stats))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Ludo running with stats...")
app.run_polling()
