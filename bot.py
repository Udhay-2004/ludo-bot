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
EMOJIS=["🟥","🟦","🟩","🟨"]

# -------- GAME --------

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

def fix_turn(g):
    if g.players and g.turn>=len(g.players):
        g.turn=0

# -------- HELPERS --------

def valid_cmd(update,cmd):
    if not update.message or not update.message.text:
        return False

    text=update.message.text.strip()

    if update.effective_chat.type=="private":
        return "pm"

    if text.startswith(f"/{cmd}@{BOT_USERNAME}"):
        return True

    return False

def name_of(u):
    return f"{u.first_name} (@{u.username})" if u.username else u.first_name

async def is_admin(update,uid):
    m=await update.effective_chat.get_member(uid)
    return m.status in ["administrator","creator"]

async def no_game(update):
    await update.message.reply_text(
        "❌ No active game in this group.\n"
        "Start one with /start@LudoooXBot 🎲"
    )

# -------- TRACK --------

def build_track(g):
    t=["⬜"]*TRACK_LENGTH

    for p,pos in g.positions.items():
        if 0<=pos<TRACK_LENGTH:
            t[pos]=g.colors[p]

    for s in SAFE_TILES:
        if t[s]=="⬜":
            t[s]="⭐"

    return (
        "🏁"+"".join(t[:13])+"\n"+
        "".join(t[13:26])+"\n"+
        "".join(t[26:39])+"\n"+
        "".join(t[39:52])+"🏆"
    )

# -------- COMMANDS --------

async def start(update,context):
    v=valid_cmd(update,"start")
    if v=="pm":
        await update.message.reply_text("🎲 Play Ludo in a group!")
        return
    if not v: return

    chat=update.effective_chat.id

    games[chat]=LudoGame(update.effective_user.id)

    kb=[[InlineKeyboardButton("🎮 Join",callback_data="join_btn")],
        [InlineKeyboardButton("🚀 Start",callback_data="start_game")]]

    await update.message.reply_text(
        "✨ *Ludo Lobby Created!*\n\n"
        "Players join using /join@LudoooXBot\n"
        "2–4 players supported 🎯",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def join_cmd(update,context):
    v=valid_cmd(update,"join")
    if v=="pm":
        await update.message.reply_text("Join from a group 🙂")
        return
    if not v: return

    chat=update.effective_chat.id
    g=games.get(chat)

    if not g:
        await no_game(update)
        return

    u=update.effective_user

    if u.id in g.players:
        await update.message.reply_text("⚠️ You already joined.")
        return

    if len(g.players)>=4:
        await update.message.reply_text("🚫 Lobby full (4/4).")
        return

    c=EMOJIS[len(g.players)]
    g.players.append(u.id)
    g.positions[u.id]=-1
    g.names[u.id]=name_of(u)
    g.colors[u.id]=c

    await update.message.reply_text(
        f"✅ {c} {g.names[u.id]} joined the lobby!"
    )

async def leave_cmd(update,context):
    v=valid_cmd(update,"leave")
    if v=="pm":
        await update.message.reply_text("Use in group.")
        return
    if not v: return

    chat=update.effective_chat.id
    g=games.get(chat)

    if not g:
        await no_game(update)
        return

    u=update.effective_user

    if u.id not in g.players:
        return

    idx=g.players.index(u.id)

    g.players.remove(u.id)
    g.positions.pop(u.id,None)
    g.names.pop(u.id,None)
    g.colors.pop(u.id,None)

    if idx<=g.turn and g.turn>0:
        g.turn-=1

    fix_turn(g)

    await update.message.reply_text(
        f"👋 {name_of(u)} left the game."
    )

# -------- KILL --------

async def kill_cmd(update,context):
    v=valid_cmd(update,"kill")
    if v=="pm":
        await update.message.reply_text("Use in group.")
        return
    if not v: return

    chat=update.effective_chat.id
    g=games.get(chat)

    if not g:
        await update.message.reply_text(
            "❌ No game running right now."
        )
        return

    u=update.effective_user

    if not await is_admin(update,u.id):
        await update.message.reply_text(
            "🚫 Admins only."
        )
        return

    games.pop(chat)

    await update.message.reply_text(
        "💥 *Game terminated.*\n"
        "New game? /start@LudoooXBot",
        parse_mode="Markdown"
    )

# -------- RELOAD --------

async def reload_cmd(update,context):
    v=valid_cmd(update,"reload")
    if v=="pm":
        await update.message.reply_text("Use in group.")
        return
    if not v: return

    if not games:
        await update.message.reply_text("♻️ Nothing to reload.")
        return

    games.clear()

    await update.message.reply_text(
        "✅ *Bot reloaded successfully!*",
        parse_mode="Markdown"
    )

# -------- STATS --------

async def stats(update,context):
    v=valid_cmd(update,"stats")
    if v=="pm":
        await update.message.reply_text("Use in group.")
        return
    if not v: return

    if not leaderboard:
        await update.message.reply_text("📊 No wins recorded yet.")
        return

    text="🏆 *Global Leaderboard*\n\n"
    for n,w in sorted(leaderboard.items(),key=lambda x:x[1],reverse=True):
        text+=f"⭐ {n} — {w} wins\n"

    await update.message.reply_text(text,parse_mode="Markdown")

# -------- BUTTONS --------

async def button(update,context):
    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    g=games.get(chat)

    if not g: return

    u=q.from_user

    if q.data=="join_btn":
        if u.id not in g.players and len(g.players)<4:
            c=EMOJIS[len(g.players)]
            g.players.append(u.id)
            g.positions[u.id]=-1
            g.names[u.id]=name_of(u)
            g.colors[u.id]=c
            await q.message.reply_text(
                f"🎉 {c} {g.names[u.id]} joined!"
            )

    elif q.data=="start_game":
        if len(g.players)<2:
            await q.message.reply_text("Need 2+ players.")
            return

        g.started=True

        await q.message.reply_text(
            build_track(g)+
            f"\n👉 {g.names[g.current()]}'s turn 🎲"
        )

# -------- DICE --------

async def handle_dice(update,context):
    msg=update.message
    if msg.dice.emoji!="🎲": return

    chat=msg.chat.id
    g=games.get(chat)

    if not g or not g.started: return

    u=update.effective_user
    if u.id!=g.current(): return

    await roll(msg,g,u.id,msg.dice.value)

# -------- ROLL --------

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
            text+=f"💥 {g.names[o]} sent home!\n"

    if pos==TRACK_LENGTH:
        name=g.names[p]
        leaderboard[name]=leaderboard.get(name,0)+1

        await msg.reply_text(f"🏆 {name} finished!")

        g.players.remove(p)
        g.positions.pop(p,None)

        if len(g.players)<=1:
            await msg.reply_text("🎉 Game Over!")
            games.pop(msg.chat.id,None)
            return

        fix_turn(g)
        await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
        return

    g.positions[p]=pos

    if dice!=6:
        g.next()

    await msg.reply_text(
        text+build_track(g)+
        f"\n👉 {g.names[g.current()]}'s turn 🎲"
    )

# -------- RUN --------

app=ApplicationBuilder().token(TOKEN).build()

for c,f in {
    "start":start,"join":join_cmd,"leave":leave_cmd,
    "kill":kill_cmd,"reload":reload_cmd,"stats":stats
}.items():
    app.add_handler(CommandHandler(c,f))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("✨ Ludo polished running...")
app.run_polling()
