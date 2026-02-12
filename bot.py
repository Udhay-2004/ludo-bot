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

TRACK_LENGTH=52
SAFE_TILES={0,8,13,21,26,34,39,47}

ALL_COLORS=["🟥","🟦","🟩","🟨"]

# ---------- GAME ----------

class LudoGame:
    def __init__(self,creator):
        self.players=[]
        self.positions={}
        self.turn=0
        self.started=False
        self.names={}
        self.colors={}
        self.creator=creator
        self.available_colors=ALL_COLORS.copy()

    def current(self):
        return self.players[self.turn]

    def next(self):
        self.turn=(self.turn+1)%len(self.players)

def fix_turn(g):
    if g.players and g.turn>=len(g.players):
        g.turn=0

# ---------- HELPERS ----------

def valid_cmd(update,cmd):
    if not update.message or not update.message.text:
        return False

    txt=update.message.text.strip()

    if update.effective_chat.type=="private":
        return "pm"

    return txt.startswith(f"/{cmd}@{BOT_USERNAME}")

def display_name(u):
    return u.first_name  # no usernames anywhere

async def is_admin(update,uid):
    m=await update.effective_chat.get_member(uid)
    return m.status in ["administrator","creator"]

async def no_game(update):
    await update.message.reply_text(
        "❌ No active game.\n/start@LudoooXBot to begin 🎲"
    )

# ---------- BOARD ----------

def build_track(g):
    t=["▫️"]*TRACK_LENGTH

    for p,pos in g.positions.items():
        if 0<=pos<TRACK_LENGTH:
            t[pos]=g.colors[p]

    for s in SAFE_TILES:
        if t[s]=="▫️":
            t[s]="⭐"

    # lane style layout
    return (
        "🏁 "+" ".join(t[:13])+"\n\n"+
        "    "+" ".join(t[13:26])+"\n\n"+
        "    "+" ".join(t[26:39])+"\n\n"+
        "🏆 "+" ".join(t[39:52])
    )

def leaderboard_text():
    if not leaderboard:
        return "📊 No wins yet."

    txt="🏆 Leaderboard\n\n"
    for n,w in sorted(leaderboard.items(),key=lambda x:x[1],reverse=True):
        txt+=f"⭐ {n} — {w} wins\n"
    return txt

# ---------- START ----------

async def start(update,context):
    v=valid_cmd(update,"start")
    if v=="pm":
        await update.message.reply_text("Play in a group 🎲")
        return
    if not v: return

    chat=update.effective_chat.id
    games[chat]=LudoGame(update.effective_user.id)

    kb=[[InlineKeyboardButton("🎮 Join",callback_data="join_btn")],
        [InlineKeyboardButton("🚀 Start",callback_data="start_game")]]

    await update.message.reply_text(
        "✨ Ludo Lobby Created!\nUse /join@LudoooXBot",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------- JOIN ----------

async def join_cmd(update,context):
    v=valid_cmd(update,"join")
    if v=="pm":
        await update.message.reply_text("Join from group 🙂")
        return
    if not v: return

    chat=update.effective_chat.id
    g=games.get(chat)
    if not g:
        await no_game(update); return

    u=update.effective_user

    if u.id in g.players:
        await update.message.reply_text("Already joined."); return

    if not g.available_colors:
        await update.message.reply_text("Lobby full."); return

    color=g.available_colors.pop(0)

    g.players.append(u.id)
    g.positions[u.id]=-1
    g.names[u.id]=display_name(u)
    g.colors[u.id]=color

    await update.message.reply_text(
        f"{color} {g.names[u.id]} joined!"
    )

# ---------- LEAVE ----------

async def leave_cmd(update,context):
    v=valid_cmd(update,"leave")
    if v=="pm":
        await update.message.reply_text("Use in group."); return
    if not v: return

    chat=update.effective_chat.id
    g=games.get(chat)
    if not g:
        await no_game(update); return

    u=update.effective_user
    if u.id not in g.players: return

    color=g.colors[u.id]
    g.available_colors.append(color)

    idx=g.players.index(u.id)

    g.players.remove(u.id)
    g.positions.pop(u.id,None)
    g.names.pop(u.id,None)
    g.colors.pop(u.id,None)

    if idx<=g.turn and g.turn>0:
        g.turn-=1

    fix_turn(g)
    await update.message.reply_text("Left game.")

# ---------- STATS ----------

async def stats(update,context):
    v=valid_cmd(update,"stats")
    if v=="pm":
        await update.message.reply_text("Use in group."); return
    if not v: return

    await update.message.reply_text(leaderboard_text())

# ---------- BUTTONS ----------

async def button(update,context):
    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    g=games.get(chat)
    if not g: return

    u=q.from_user

    if q.data=="join_btn":
        if u.id not in g.players and g.available_colors:
            color=g.available_colors.pop(0)
            g.players.append(u.id)
            g.positions[u.id]=-1
            g.names[u.id]=display_name(u)
            g.colors[u.id]=color
            await q.message.reply_text(
                f"{color} {g.names[u.id]} joined!"
            )

    elif q.data=="start_game" and len(g.players)>=2:
        g.started=True
        await q.message.reply_text(
            build_track(g)+
            f"\n\n👉 {g.names[g.current()]}'s turn 🎲"
        )

# ---------- DICE ----------

async def handle_dice(update,context):
    msg=update.message
    if msg.dice.emoji!="🎲": return

    chat=msg.chat.id
    g=games.get(chat)
    if not g or not g.started: return

    u=update.effective_user
    if u.id!=g.current(): return

    await roll(msg,g,u.id,msg.dice.value)

# ---------- ROLL ----------

async def roll(msg,g,p,dice):

    pos=g.positions[p]
    text=f"{g.colors[p]} {g.names[p]} rolled {dice}\n"

    if pos==-1 and dice!=6:
        g.next()
        await msg.reply_text(text+"Need 6.")
        await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
        return

    pos=0 if pos==-1 else pos+dice

    if pos>TRACK_LENGTH:
        g.next()
        await msg.reply_text(text+"Need exact.")
        await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
        return

    for o in g.players:
        if o!=p and g.positions[o]==pos and pos not in SAFE_TILES:
            g.positions[o]=-1
            text+=f"💥 {g.names[o]} out!\n"

    if pos==TRACK_LENGTH:

        name=g.names[p]
        leaderboard[name]=leaderboard.get(name,0)+1

        await msg.reply_text(f"🏆 {name} finished!")

        # free color
        g.available_colors.append(g.colors[p])

        g.players.remove(p)
        g.positions.pop(p,None)
        g.colors.pop(p,None)
        g.names.pop(p,None)

        if len(g.players)<=1:
            await msg.reply_text("🎉 Game Over!")
            await msg.reply_text(leaderboard_text())
            games.pop(msg.chat.id,None)
            return

        fix_turn(g)
        await msg.reply_text(
            f"👉 {g.names[g.current()]}'s turn 🎲"
        )
        return

    g.positions[p]=pos

    if dice!=6:
        g.next()

    await msg.reply_text(
        text+build_track(g)+
        f"\n\n👉 {g.names[g.current()]}'s turn 🎲"
    )

# ---------- RUN ----------

app=ApplicationBuilder().token(TOKEN).build()

for c,f in {
    "start":start,
    "join":join_cmd,
    "leave":leave_cmd,
    "stats":stats
}.items():
    app.add_handler(CommandHandler(c,f))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("🎲 Ludo improved running...")
app.run_polling()