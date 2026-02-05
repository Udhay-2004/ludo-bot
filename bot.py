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
POWER_TILES={8:"boost",18:"bomb",28:"boost"}

EMOJIS=["🟥","🟦","🟩","🟨"]

# ---------------- GAME ----------------

class LudoGame:
    def __init__(self):
        self.players=[]
        self.positions={}
        self.turn=0
        self.started=False

    def current(self): return self.players[self.turn]
    def next(self): self.turn=(self.turn+1)%len(self.players)

# ---------------- BUILD TRACK ----------------

def build_track(g):
    t=["⬜"]*TRACK_LENGTH

    for i,(p,pos) in enumerate(g.positions.items()):
        if 0<=pos<TRACK_LENGTH:
            t[pos]=EMOJIS[i]

    for s in SAFE_TILES:
        if t[s]=="⬜": t[s]="⭐"

    line1="".join(t[:10])
    line2="".join(t[10:20])
    line3="".join(t[20:30])
    line4="".join(t[30:40])

    return f"🏁{line1}\n{line2}\n{line3}\n{line4}🏆"

# ---------------- START ----------------

async def start(update,context):
    if update.effective_chat.type=="private":
        await update.message.reply_text("Use in group")
        return

    chat=update.effective_chat.id
    games[chat]=LudoGame()

    kb=[[InlineKeyboardButton("Join",callback_data="join")],
        [InlineKeyboardButton("Start",callback_data="begin")]]

    await update.message.reply_text(
        "🎲 Chaos Ludo 4-Line Mode",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------------- BUTTONS ----------------

async def button(update,context):
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
            f"Game started!\n{g.current()} turn 🎲"
        )

# ---------------- DICE ----------------

async def handle_dice(update,context):
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

    text=f"🎲 {player} rolled {dice}\n"
    move=dice

    # Lucky events
    ev=random.choice(["none","boost","back"])
    if ev=="boost":
        move+=2
        text+="🍀 +2 boost!\n"
    elif ev=="back":
        move=max(1,move-2)
        text+="😈 -2 bad luck!\n"

    # Enter board
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
        # EXACT FINISH RULE
        if pos+move>TRACK_LENGTH:
            text+="❗ Need exact roll to win\n"
            await msg.reply_text(text)
            g.next()
            return
        pos+=move

    # Power tiles
    if pos in POWER_TILES:
        if POWER_TILES[pos]=="boost":
            pos+=3
            text+="🚀 Power +3!\n"
        elif POWER_TILES[pos]=="bomb":
            victim=random.choice(
                [p for p in g.players if p!=player]
            )
            g.positions[victim]=-1
            text+=f"💣 Bomb! {victim} home!\n"

    # Kill
    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"💥 Killed {p}\n"

    # Win
    if pos==TRACK_LENGTH:
        leaderboard[player]=leaderboard.get(player,0)+1
        await msg.reply_text(f"🏆 {player} WINS!")
        del games[chat]
        return

    g.positions[player]=pos

    track=build_track(g)

    if dice!=6:
        g.next()

    await msg.reply_text(
        text+"\n"+track+
        f"\n👉 Next: {g.current()}"
    )

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Running 4-line Chaos Ludo...")
app.run_polling()
