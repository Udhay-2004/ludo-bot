import os
import random
from telegram import (
    Update, InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes
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
        self.names={}
        self.colors={}

    def current(self): return self.players[self.turn]
    def next(self): self.turn=(self.turn+1)%len(self.players)

# ---------------- NAME FORMAT ----------------

def name_of(user):
    if user.username:
        return f"{user.first_name} (@{user.username})"
    return user.first_name

# ---------------- BUILD TRACK ----------------

def build_track(g):
    t=["⬜"]*TRACK_LENGTH

    for p,pos in g.positions.items():
        if 0<=pos<TRACK_LENGTH:
            t[pos]=g.colors[p]

    for s in SAFE_TILES:
        if t[s]=="⬜": t[s]="⭐"

    return (
        "🏁"+"".join(t[:10])+"\n"+
        "".join(t[10:20])+"\n"+
        "".join(t[20:30])+"\n"+
        "".join(t[30:40])+"🏆"
    )

# ---------------- STATS ----------------

async def stats(update,context):

    if not leaderboard:
        await update.message.reply_text("No stats to show.")
        return

    text="🏆 Leaderboard\n\n"

    for i,(uid,wins) in enumerate(
        sorted(leaderboard.items(),
               key=lambda x:x[1],
               reverse=True),1):

        name="Player"

        for g in games.values():
            if uid in g.names:
                name=g.names[uid]
                break

        text+=f"{i}. {name} — {wins} wins\n"

    await update.message.reply_text(text)

# ---------------- START ----------------

async def start(update,context):
    if update.effective_chat.type=="private":
        await update.message.reply_text("Use in group 🎲")
        return

    chat=update.effective_chat.id
    games[chat]=LudoGame()

    kb=[[InlineKeyboardButton("Join",callback_data="join")],
        [InlineKeyboardButton("Start",callback_data="begin")]]

    await update.message.reply_text(
        "🎲 Ludo Lobby",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------------- BUTTON ----------------

async def button(update,context):
    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    user=q.from_user
    g=games.get(chat)

    if not g: return

# JOIN
    if q.data=="join":
        if user.id in g.players: return
        if len(g.players)>=4:
            await q.answer("Max 4 players")
            return

        color=EMOJIS[len(g.players)]

        g.players.append(user.id)
        g.positions[user.id]=-1
        g.names[user.id]=name_of(user)
        g.colors[user.id]=color

        plist="\n".join(
            f"{g.colors[p]} {g.names[p]}"
            for p in g.players
        )

        await q.edit_message_text(
            "Players:\n"+plist,
            reply_markup=q.message.reply_markup
        )

# START
    elif q.data=="begin":
        if len(g.players)<2:
            await q.answer("Need 2+ players")
            return

        g.started=True
        await show_turn(q.message,g)

# ROLL BUTTON
    elif q.data=="roll":
        if user.id!=g.current():
            await q.answer("Not your turn")
            return

        dice=random.randint(1,6)
        await roll(q.message,g,user.id,dice)

# ---------------- SHOW TURN ----------------

async def show_turn(msg,g):
    kb=[[InlineKeyboardButton("🎲 Roll Dice",callback_data="roll")]]

    await msg.reply_text(
        build_track(g)+
        f"\n👉 {g.names[g.current()]}'s turn",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------------- ROLL ----------------

async def roll(msg,g,player,dice):
    chat=msg.chat.id
    pos=g.positions[player]

    text=f"{g.colors[player]} {g.names[player]} rolled {dice}\n"

# ENTER BOARD
    if pos==-1:
        if dice==6:
            pos=0
            text+="Entered!\n"
        else:
            text+="Need 6 to enter\n"
            g.next()
            await msg.reply_text(text)
            await show_turn(msg,g)
            return
    else:
        if pos+dice>TRACK_LENGTH:
            text+="Need exact roll\n"
            g.next()
            await msg.reply_text(text)
            await show_turn(msg,g)
            return

        pos+=dice

# KILL
    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"💥 Killed {g.names[p]}\n"

# WIN
    if pos==TRACK_LENGTH:
        leaderboard[player]=leaderboard.get(player,0)+1
        await msg.reply_text(
            f"🏆 {g.names[player]} WINS!"
        )
        del games[chat]
        return

    g.positions[player]=pos

    if dice!=6:
        g.next()

    await msg.reply_text(text)
    await show_turn(msg,g)

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("stats",stats))
app.add_handler(CallbackQueryHandler(button))

print("Ludo running...")
app.run_polling()
