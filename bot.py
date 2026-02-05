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
leaderboard={
    "today":{},
    "week":{},
    "all":{}
}

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

# ---------------- LEADERBOARD ----------------

def get_name(uid):
    for g in games.values():
        if uid in g.names:
            return g.names[uid]
    return "Player"

def lb_text(mode):
    data=leaderboard[mode]

    title={
        "today":"🏆 Leaderboard - Today\n\n",
        "week":"🏆 Leaderboard - Week\n\n",
        "all":"🏆 Leaderboard - All Time\n\n"
    }

    if not data:
        return title[mode]+"No stats yet."

    medals=["🥇","🥈","🥉"]
    text=title[mode]

    sorted_lb=sorted(
        data.items(),
        key=lambda x:x[1],
        reverse=True
    )[:10]

    for i,(uid,w) in enumerate(sorted_lb):
        medal=medals[i] if i<3 else "🏅"
        text+=f"{medal} {get_name(uid)} - {w}\n"

    return text

async def stats(update,context):

    kb=[[
        InlineKeyboardButton("Today",callback_data="lb_today"),
        InlineKeyboardButton("Week",callback_data="lb_week"),
        InlineKeyboardButton("All Time",callback_data="lb_all")
    ]]

    await update.message.reply_text(
        lb_text("today"),
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def lb_buttons(update,context):
    q=update.callback_query
    await q.answer()
    mode=q.data.split("_")[1]
    await q.edit_message_text(lb_text(mode))

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

    if q.data=="join":

        if user.id in g.players: return
        if len(g.players)>=4:
            await q.answer("Max 4")
            return

        color=EMOJIS[len(g.players)]

        g.players.append(user.id)
        g.positions[user.id]=-1
        g.names[user.id]=name_of(user)
        g.colors[user.id]=color

        await q.edit_message_text(
            "Players:\n"+"\n".join(
                f"{g.colors[p]} {g.names[p]}"
                for p in g.players
            ),
            reply_markup=q.message.reply_markup
        )

    elif q.data=="begin":

        if len(g.players)<2:
            await q.answer("Need 2+")
            return

        g.started=True

        await q.edit_message_text(
            build_track(g)+
            f"\n👉 {g.names[g.current()]}'s turn 🎲\nSend 🎲"
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

    for p in g.players:
        if p!=player and g.positions[p]==pos and pos not in SAFE_TILES:
            g.positions[p]=-1
            text+=f"💥 Killed {g.names[p]}\n"

    if pos==TRACK_LENGTH:
        for k in leaderboard:
            leaderboard[k][player]=leaderboard[k].get(player,0)+1

        await msg.reply_text(f"🏆 {g.names[player]} WINS!")
        del games[chat]
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
app.add_handler(CallbackQueryHandler(button,pattern="^(join|begin)$"))
app.add_handler(CallbackQueryHandler(lb_buttons,pattern="^lb_"))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Ludo running clean...")
app.run_polling()
