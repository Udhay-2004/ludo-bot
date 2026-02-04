import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

TOKEN = os.getenv("TOKEN")

games = {}

# ---------------- GAME CLASS ----------------

class LudoGame:
    def __init__(self):
        self.players = []
        self.positions = {}
        self.turn_index = 0
        self.started = False

    def current_player(self):
        return self.players[self.turn_index]

    def next_turn(self):
        self.turn_index = (self.turn_index + 1) % len(self.players)


# ---------------- HELP ----------------

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 *Ludo Help*\n\n"
        "/start — Create lobby\n"
        "/help — Show help\n"
        "/rules — Game rules\n\n"
        "On your turn send 🎲 to roll.",
        parse_mode="Markdown"
    )

# ---------------- RULES ----------------

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 *Ludo Rules*\n\n"
        "• Roll 6 to enter board\n"
        "• Landing on player sends them home\n"
        "• Roll 6 = extra turn\n"
        "• Reach 50 to win 🏆",
        parse_mode="Markdown"
    )

# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    games[chat_id] = LudoGame()

    keyboard = [
        [InlineKeyboardButton("🎮 Join", callback_data="join")],
        [InlineKeyboardButton("🚀 Start", callback_data="begin")]
    ]

    await update.message.reply_text(
        "🎲 *Welcome to Ludo Bot!*\n\n"
        "Play Ludo with real 🎲 dice.\n"
        "2–6 players supported.\n\n"
        "Click Join to enter!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- BUTTONS ----------------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user.first_name
    game = games.get(chat_id)

    if not game:
        return

# JOIN
    if query.data == "join":

        if user in game.players:
            return

        if len(game.players) >= 6:
            await query.answer("Lobby full")
            return

        game.players.append(user)
        game.positions[user] = -1

        await query.edit_message_text(
            "🎲 Lobby\n\n" + "\n".join(game.players),
            reply_markup=query.message.reply_markup
        )

# START
    elif query.data == "begin":

        if len(game.players) < 2:
            await query.answer("Need 2+ players")
            return

        game.started = True

        await query.edit_message_text(
            f"🎉 Game Started!\n"
            f"{game.current_player()} goes first\n"
            f"Send 🎲"
        )


# ---------------- DICE ----------------

async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.dice.emoji != "🎲":
        return

    chat_id = msg.chat.id
    user = update.effective_user.first_name
    game = games.get(chat_id)

    if not game or not game.started:
        return

    if user != game.current_player():
        return

    dice = msg.dice.value
    await process_roll(msg, game, user, dice)


# ---------------- ROLL ----------------

async def process_roll(message, game, player, dice):
    chat_id = message.chat.id
    pos = game.positions[player]

    text = f"🎲 {player} rolled {dice}\n"

    if pos == -1:
        if dice == 6:
            pos = 0
            text += "Entered board!\n"
        else:
            text += "Need 6\n"
    else:
        pos += dice

    for p in game.players:
        if p != player and game.positions[p] == pos:
            game.positions[p] = -1
            text += f"Sent {p} home!\n"

    if pos >= 50:
        await message.reply_text(f"🏆 {player} wins!")
        del games[chat_id]
        return

    game.positions[player] = pos

    if dice != 6:
        game.next_turn()

    text += f"Next: {game.current_player()}"

    await message.reply_text(text)


# ---------------- RUN ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("rules", rules))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL, handle_dice))

print("Bot running...")
app.run_polling()
