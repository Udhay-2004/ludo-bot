import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

from PIL import Image, ImageDraw

TOKEN = os.getenv("TOKEN")

games = {}
leaderboard = {}

# ---------------- TILE MAP ----------------
# 52 tile loop (simple square path)
tiles = {i:(50+(i%13)*40,550-(i//13)*40) for i in range(52)}

safe_zones = {0,8,13,21,26,34,39,47}

# ---------------- DRAW BOARD ----------------

def draw_board(positions):
    board = Image.open("board.png").convert("RGBA")
    draw = ImageDraw.Draw(board)

    colors=["red","blue","green","yellow"]

    for i,(player,pos) in enumerate(positions.items()):
        if pos>=0 and pos in tiles:
            x,y=tiles[pos]
            draw.ellipse(
                (x-15,y-15,x+15,y+15),
                fill=colors[i%4],
                outline="black",
                width=3
            )

    board.save("current.png")


# ---------------- GAME CLASS ----------------

class LudoGame:
    def __init__(self):
        self.players=[]
        self.positions={}
        self.turn_index=0
        self.started=False

    def current_player(self):
        return self.players[self.turn_index]

    def next_turn(self):
        self.turn_index=(self.turn_index+1)%len(self.players)


# ---------------- HELP ----------------

async def help_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - lobby\n/help - help\n/rules - rules\n/stats - leaderboard"
    )

# ---------------- RULES ----------------

async def rules(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Roll 6 to enter.\nSafe tiles ⭐ can't be killed.\nReach 52 to win."
    )

# ---------------- STATS ----------------

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not leaderboard:
        await update.message.reply_text("No stats to show.")
        return

    text="🏆 Leaderboard\n"
    for i,(p,w) in enumerate(sorted(
        leaderboard.items(),
        key=lambda x:x[1],
        reverse=True
    ),1):
        text+=f"{i}. {p} - {w} wins\n"

    await update.message.reply_text(text)


# ---------------- START ----------------

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type=="private":
        await update.message.reply_text(
            "Use me in a group to play 🎲"
        )
        return

    chat_id=update.effective_chat.id
    games[chat_id]=LudoGame()

    kb=[[InlineKeyboardButton("Join",callback_data="join")],
        [InlineKeyboardButton("Start",callback_data="begin")]]

    await update.message.reply_text(
        "🎲 Ludo Lobby",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ---------------- BUTTONS ----------------

async def button(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()

    chat_id=query.message.chat.id
    user=query.from_user.first_name
    game=games.get(chat_id)

    if not game: return

    if query.data=="join":
        if user in game.players: return
        if len(game.players)>=4:
            await query.answer("Max 4 players")
            return

        game.players.append(user)
        game.positions[user]=-1

        await query.edit_message_text(
            "Players:\n"+"\n".join(game.players),
            reply_markup=query.message.reply_markup
        )

    elif query.data=="begin":
        if len(game.players)<2:
            await query.answer("Need 2 players")
            return

        game.started=True
        await query.edit_message_text(
            f"Game started!\n{game.current_player()} turn\nSend 🎲"
        )


# ---------------- DICE ----------------

async def handle_dice(update:Update,context:ContextTypes.DEFAULT_TYPE):
    msg=update.message
    if msg.dice.emoji!="🎲": return

    chat_id=msg.chat.id
    user=update.effective_user.first_name
    game=games.get(chat_id)

    if not game or not game.started: return
    if user!=game.current_player(): return

    await process_roll(msg,game,user,msg.dice.value)


# ---------------- ROLL ----------------

async def process_roll(message,game,player,dice):
    chat_id=message.chat.id
    pos=game.positions[player]

    text=f"{player} rolled {dice}\n"

    if pos==-1:
        if dice==6:
            pos=0
            text+="Entered board\n"
        else:
            text+="Need 6\n"
    else:
        pos+=dice

    # Kill logic
    for p in game.players:
        if p!=player and game.positions[p]==pos and pos not in safe_zones:
            game.positions[p]=-1
            text+=f"Killed {p}\n"

    # Win
    if pos>=52:
        leaderboard[player]=leaderboard.get(player,0)+1
        await message.reply_text(f"🏆 {player} wins!")
        del games[chat_id]
        return

    game.positions[player]=pos

    # Draw board
    draw_board(game.positions)
    await message.reply_photo(open("current.png","rb"))

    if dice!=6:
        game.next_turn()

    await message.reply_text(
        f"Next: {game.current_player()}"
    )


# ---------------- RUN ----------------

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("help",help_cmd))
app.add_handler(CommandHandler("rules",rules))
app.add_handler(CommandHandler("stats",stats))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL,handle_dice))

print("Bot running...")
app.run_polling()
