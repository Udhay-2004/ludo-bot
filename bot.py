from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

TOKEN = "8451916354:AAEH1BZMyK63thNfuS7scDR1q7w6Q1nWeEw"

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


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    games[chat_id] = LudoGame()

    keyboard = [
        [InlineKeyboardButton("🎮 Join", callback_data="join")],
        [InlineKeyboardButton("🚀 Start", callback_data="begin")]
    ]

    await update.message.reply_text(
        "🎲 Welcome to Ludo Bot!\n\n"
        "Play Ludo with friends using real 🎲 dice.\n\n"
        "• 2–6 players\n"
        "• First to reach 50 wins 🏆\n\n"
        "Click Join to enter the lobby!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- BUTTON HANDLER ----------------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user.first_name
    game = games.get(chat_id)

    if not game:
        return

# ----- JOIN -----
    if query.data == "join":

        if game.started:
            await query.answer("Game already started")
            return

        if user in game.players:
            await query.answer("Already joined")
            return

        if len(game.players) >= 6:
            await query.answer("Lobby full (6/6)")
            return

        game.players.append(user)
        game.positions[user] = -1

        await query.edit_message_text(
            "🎲 Ludo Lobby\n\nPlayers:\n" +
            "\n".join(game.players),
            reply_markup=query.message.reply_markup
        )

# ----- START GAME -----
    elif query.data == "begin":

        if len(game.players) < 2:
            await query.answer("Minimum 2 players needed")
            return

        game.started = True

        await query.edit_message_text(
            f"🎉 Game Started!\n\n"
            f"👉 {game.current_player()} goes first\n"
            f"Send 🎲 to roll"
        )


# ---------------- DICE HANDLER ----------------

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


# ---------------- ROLL LOGIC ----------------

async def process_roll(message, game, player, dice):
    chat_id = message.chat.id
    pos = game.positions[player]

    text = f"🎲 {player} rolled {dice}\n"

    # Enter board
    if pos == -1:
        if dice == 6:
            pos = 0
            text += "Entered board!\n"
        else:
            text += "Need 6 to enter\n"
    else:
        pos += dice

    # Kill logic
    for p in game.players:
        if p != player and game.positions[p] == pos:
            game.positions[p] = -1
            text += f"Sent {p} home!\n"

    # Win check
    if pos >= 50:
        await message.reply_text(f"🏆 {player} wins the game!")
        del games[chat_id]
        return

    game.positions[player] = pos

    # Next turn
    if dice != 6:
        game.next_turn()

    next_p = game.current_player()
    text += f"Next: {next_p}"

    await message.reply_text(text)


# ---------------- RUN ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.Dice.ALL, handle_dice))

print("Bot running...")
app.run_polling()
