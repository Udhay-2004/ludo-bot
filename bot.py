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

TRACK_LENGTH=40
SAFE_TILES={5,10,15,20,25,30,35}
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
        if not self.players:
            return None
        return self.players[self.turn]

    def next(self):
        if self.players:
            self.turn=(self.turn+1)%len(self.players)

# ---------------- HELPERS ----------------

def valid_cmd(update,cmd):
    return update.message and update.message.text and update.message.text.startswith(f"/{cmd}@{BOT_USERNAME}")

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
        if t[s]=="⬜":
            t[s]="⭐"

    return "🏁"+"".join(t[:10])+"\n"+"".join(t[10:20])+"\n"+"".join(t[20:30])+"\n"+"".join(t[30:40])+"🏆"

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

    if not g:
        await update.message.reply_text("Start first /start@LudoooXBot")
        return

    if user.id in g.players:
        return

    if len(g.players)>=4:
        await update.message.reply_text("Game full")
        return

    c=EMOJIS[len(g.players)]
    g.players.append(user.id)
    g.positions[user.id]=-1
    g.names[user.id]=name_of(user)
    g.colors[user.id]=c

    await update.message.reply_text(f"{c} {g.names[user.id]} joined!")

# ---------------- LEAVE ----------------

async def leave_cmd(update,context):

    if not valid_cmd(update,"leave"): return

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g or user.id not in g.players: return

    idx=g.players.index(user.id)

    g.players.remove(user.id)
    g.positions.pop(user.id,None)
    g.names.pop(user.id,None)
    g.colors.pop(user.id,None)

    if idx<=g.turn and g.turn>0:
        g.turn-=1

    fix_turn(g)

    await update.message.reply_text("Left game.")

# ---------------- KICK ----------------

async def kick_cmd(update,context):

    if not valid_cmd(update,"kick"): return

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g: return

    admin=await is_admin(update,user.id)

    if not admin and user.id!=g.creator:
        await update.message.reply_text("Only admin/creator can kick.")
        return

    target=None

    if update.message.reply_to_message:
        target=update.message.reply_to_message.from_user
    elif context.args:
        uname=context.args[0].replace("@","")
        for uid,name in g.names.items():
            if uname in name:
                target=type("obj",(object,),{"id":uid})
                break

    if not target or target.id not in g.players:
        return

    idx=g.players.index(target.id)

    g.players.remove(target.id)
    g.positions.pop(target.id,None)
    g.names.pop(target.id,None)
    g.colors.pop(target.id,None)

    if idx<=g.turn and g.turn>0:
        g.turn-=1

    fix_turn(g)

    await update.message.reply_text("Player kicked.")

# ---------------- KILL GAME ----------------

async def kill_cmd(update,context):

    if not valid_cmd(update,"kill"): return

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g: return

    admin=await is_admin(update,user.id)

    if not admin and user.id!=g.creator:
        return

    del games[chat]
    await update.message.reply_text("Game killed.")

# ---------------- STATS ----------------

async def stats(update,context):

    if not valid_cmd(update,"stats"): return

    if not leaderboard:
        await update.message.reply_text("No stats yet.")
        return

    text="🏆 Leaderboard\n\n"
    for n,w in sorted(leaderboard.items(),key=lambda x:x[1],reverse=True):
        text+=f"{n} — {w}\n"

    await update.message.reply_text(text)

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
        if len(g.players)<2:
            return
        g.started=True
        await q.message.reply_text(
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

    if not g or not g.started or user.id!=g.current(): return

    await roll(msg,g,user.id,msg.dice.value)

# ---------------- ROLL ----------------

async def roll(msg,g,player,dice):

    pos=g.positions[player]

    text=f"{g.colors[player]} {g.names[player]} rolled {dice}\n"

    if pos==-1 and dice!=6:
        g.next()
        await msg.reply_text(text+"Need 6")
        await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
        return

    if pos==-1:
        pos=0
    else:
        if pos+dice>TRACK_LENGTH:
            g.next()
            await msg.reply_text(text+"Need exact")
            await msg.reply_text(f"👉 {g.names[g.current()]}'s turn 🎲")
            return
        pos+=dice

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

# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler(["start","join","leave","kick","kill","stats"],lambda u,c:None))
app.add_handler(MessageHandler(filters.TEXT & filters.COMMAND,lambda u,c:None))

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("join",join_cmd))
app.add_handler(CommandHandler("leave",leave_cmd))
app.add_handler(CommandHandler("kick",kick_cmd))
app.add_handler(CommandHandler("kill",kill_cmd))
app.add_handler(CommandHandler("stats",stats))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Ludo strict-command mode running...")
app.run_polling()

