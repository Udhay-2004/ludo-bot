import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

TOKEN = os.getenv("TOKEN")

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
        return self.players[self.turn]

    def next(self):
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

# ---------------- LEADERBOARD TEXT ----------------

def leaderboard_text():

    if not leaderboard:
        return "🏆 Leaderboard\n\nNo wins yet."

    text="🏆 Leaderboard\n\n"

    sorted_lb=sorted(
        leaderboard.items(),
        key=lambda x:x[1],
        reverse=True
    )

    medals=["🥇","🥈","🥉"]

    for i,(name,wins) in enumerate(sorted_lb):
        medal = medals[i] if i<3 else "🏅"
        text+=f"{medal} {name} — {wins} wins\n"

    return text

# ---------------- STATS COMMAND ----------------

async def stats(update,context):
    await update.message.reply_text(
        leaderboard_text()
    )

# ---------------- ADMIN CHECK ----------------

async def is_admin(update,user_id):
    member=await update.effective_chat.get_member(user_id)
    return member.status in ["administrator","creator"]

# ---------------- START ----------------

async def start(update,context):

    if update.effective_chat.type=="private":
        await update.message.reply_text("Use in group 🎲")
        return

    chat=update.effective_chat.id
    creator=update.effective_user.id

    games[chat]=LudoGame(creator)

    kb=[[InlineKeyboardButton("🎮 Join",callback_data="join_btn")],
        [InlineKeyboardButton("🚀 Start",callback_data="start_game")]]

    await update.message.reply_text(
        "🎲 Ludo Lobby\nClick Join or /join",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------------- ADD PLAYER ----------------

def add_player(g,user):

    if user.id in g.players:
        return "already"

    if len(g.players)>=4:
        return "full"

    color=EMOJIS[len(g.players)]

    g.players.append(user.id)
    g.positions[user.id]=-1
    g.names[user.id]=name_of(user)
    g.colors[user.id]=color

    return "ok"

# ---------------- JOIN ----------------

async def join_cmd(update,context):

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g:
        await update.message.reply_text("Use /start first")
        return

    r=add_player(g,user)

    if r=="already":
        await update.message.reply_text("Already joined.")
    elif r=="full":
        await update.message.reply_text("Game full.")
    else:
        await update.message.reply_text(
            f"{g.colors[user.id]} {g.names[user.id]} joined!"
        )

# ---------------- LEAVE ----------------

async def leave_cmd(update,context):

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g or user.id not in g.players:
        return

    name=g.names[user.id]

    g.players.remove(user.id)
    g.positions.pop(user.id,None)
    g.names.pop(user.id,None)
    g.colors.pop(user.id,None)

    await update.message.reply_text(f"{name} left.")

# ---------------- KICK ----------------

async def kick_cmd(update,context):

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g: return

    admin=await is_admin(update,user.id)

    if not admin and user.id!=g.creator:
        await update.message.reply_text(
            "❌ Only admin or creator can kick."
        )
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to player to kick.")
        return

    target=update.message.reply_to_message.from_user.id

    if target not in g.players:
        return

    name=g.names[target]

    g.players.remove(target)
    g.positions.pop(target,None)
    g.names.pop(target,None)
    g.colors.pop(target,None)

    await update.message.reply_text(f"❌ {name} kicked.")

# ---------------- END ----------------

async def end_cmd(update,context):

    chat=update.effective_chat.id
    user=update.effective_user
    g=games.get(chat)

    if not g: return

    admin=await is_admin(update,user.id)

    if not admin and user.id!=g.creator:
        await update.message.reply_text(
            "❌ Only admin or creator can end."
        )
        return

    del games[chat]
    await update.message.reply_text("🏁 Game ended.")

# ---------------- BUTTONS ----------------

async def button(update,context):

    q=update.callback_query
    await q.answer()

    chat=q.message.chat.id
    user=q.from_user
    g=games.get(chat)

    if not g: return

    if q.data=="join_btn":
        r=add_player(g,user)
        if r=="ok":
            await q.message.reply_text(
                f"{g.colors[user.id]} {g.names[user.id]} joined!"
            )

    elif q.data=="start_game":

        if len(g.players)<2:
            await q.answer("Need 2+ players")
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
                f"👉 {g.names[g.current()]}'s turn 🎲"
            )
            return
    else:
        if pos+dice>TRACK_LENGTH:
            text+="Need exact roll\n"
            g.next()
            await msg.reply_text(text)
            await msg.reply_text(
                f"👉 {g.names[g.current()]}'s turn 🎲"
            )
            return
        pos+=dice

    # FINISH
    if pos==TRACK_LENGTH:

        name=g.names[player]
        leaderboard[name]=leaderboard.get(name,0)+1

        await msg.reply_text(f"🥇 {name} finished!")

        g.players.remove(player)
        g.positions.pop(player,None)

        # GAME END
        if len(g.players)<=1:
            await msg.reply_text("🏁 Game Over!")
            await msg.reply_text(leaderboard_text())
            del games[chat]
            return

        g.turn%=len(g.players)

        await msg.reply_text(
            f"👉 {g.names[g.current()]}'s turn 🎲"
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
app.add_handler(CommandHandler("join",join_cmd))
app.add_handler(CommandHandler("leave",leave_cmd))
app.add_handler(CommandHandler("kick",kick_cmd))
app.add_handler(CommandHandler("end",end_cmd))
app.add_handler(CommandHandler("stats",stats))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Ludo running with stats...")
app.run_polling()
