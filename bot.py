import os
from telegram import (
    Update, InlineKeyboardButton,
    InlineKeyboardMarkup
)
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
        self.names={}
        self.colors={}
        self.finished=[]

    def current(self):
        if not self.players:
            return None
        return self.players[self.turn]

    def next(self):
        if self.players:
            self.turn=(self.turn+1)%len(self.players)

# ---------------- NAME ----------------

def name_of(user):
    if user.username:
        return f"{user.first_name} (@{user.username})"
    return user.first_name

# ---------------- TRACK ----------------

def build_track(g):
    t=["⬜"]*TRACK_LENGTH

    for p,pos in g.positions.items():
        if 0<=pos<TRACK_LENGTH:
            t[pos]=g.colors[p]

    for s in SAFE_TILES:
        if t[s]=="⬜":
            t[s]="⭐"

    return (
        "🏁"+"".join(t[:10])+"\n"+
        "".join(t[10:20])+"\n"+
        "".join(t[20:30])+"\n"+
        "".join(t[30:40])+"🏆"
    )

# ---------------- STATS ----------------

async def stats(update,context):

    if not leaderboard:
        await update.message.reply_text("No stats yet.")
        return

    text="🏆 Leaderboard\n\n"

    sorted_lb=sorted(
        leaderboard.items(),
        key=lambda x:x[1],
        reverse=True
    )

    for i,(name,wins) in enumerate(sorted_lb,1):
        text+=f"{i}. {name} - {wins} wins\n"

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

# JOIN (mid-game allowed)
    if q.data=="join":

        if user.id in g.players:
            return

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
            await q.answer("Need 2+")
            return

        g.started=True

        await q.edit_message_text(
            build_track(g)+
            f"\n👉 {g.names[g.current()]}'s turn 🎲"
        )

# ---------------- DICE ----------------

async def handle_dice(update,context):

    msg=update.message
    if msg.dice.emoji!="🎲": return

    chat=msg.chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g or not g.started: return
    if user.id!=g.current(): return

    await roll(msg,g,user.id,msg.dice.value)

# ---------------- ROLL ----------------

async def roll(msg,g,player,dice):

    chat=msg.chat.id
    pos=g.positions[player]

    text=f"{g.colors[player]} {g.names[player]} rolled {dice}\n"

    if pos==-1:
        if dice==6:
            pos=0
            text+="Entered!\n"
        else:
            text+="Need 6\n"
            g.next()
            await msg.reply_text(text)
            await msg.reply_text(
                build_track(g)+
                f"\n👉 {g.names[g.current()]}'s turn 🎲"
            )
            return
    else:
        if pos+dice>TRACK_LENGTH:
            text+="Need exact roll\n"
            g.next()
            await msg.reply_text(text)
            await msg.reply_text(
                build_track(g)+
                f"\n👉 {g.names[g.current()]}'s turn 🎲"
            )
            return
        pos+=dice

    # Kill
    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"💥 Killed {g.names[p]}\n"

# FINISH
    if pos==TRACK_LENGTH:

        g.finished.append(player)
        name=g.names[player]

        leaderboard[name]=leaderboard.get(name,0)+1

        await msg.reply_text(f"🥇 {name} finished!")

        g.players.remove(player)
        del g.positions[player]

        if len(g.players)<=1:
            await msg.reply_text("🏁 Game Over!")
            del games[chat]
            return

        g.turn%=len(g.players)
        await msg.reply_text(
            build_track(g)+
            f"\n👉 {g.names[g.current()]}'s turn 🎲"
        )
        return

    g.positions[player]=pos

    if dice!=6:
        g.next()

    await msg.reply_text(text)
    await msg.reply_text(
        build_track(g)+
        f"\n👉 {g.names[g.current()]}'s turn 🎲"
    )

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("stats",stats))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Ludo running updated...")
app.run_polling()

