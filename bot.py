import requests
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import matplotlib.pyplot as plt
import io

users = {}

OPENWEATHER_API_KEY = "Secret :)"
TELEGRAM_BOT_TOKEN = "Secret :)"

FOOD_DB = {
    "банан": 90, "яблоко": 50, "картофель": 80, "рис": 130, "курица": 165,
    "говядина": 250, "хлеб": 265, "яйцо": 155, "сыр": 400, "молоко": 40
}

async def start(update, context):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {
            "weight": None,
            "height": None,
            "age": None,
            "activity": None,
            "city": None,
            "water_goal": 0,
            "calorie_goal": 0,
            "logged_water": 0,
            "logged_calories": 0,
            "burned_calories": 0,
            "setup_step": None
        }
    await update.message.reply_text(
        "Привет! Я бот для отслеживания воды, калорий и тренировок.\n"
        "Команды: /set_profile, /log_water, /log_food, /log_workout, /check_progress"
    )

async def set_profile(update, context):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {
            "weight": None,
            "height": None,
            "age": None,
            "activity": None,
            "city": None,
            "water_goal": 0,
            "calorie_goal": 0,
            "logged_water": 0,
            "logged_calories": 0,
            "burned_calories": 0,
            "setup_step": "weight"
        }
    else:
        users[user_id]["setup_step"] = "weight"
    await update.message.reply_text("Введите ваш вес (в кг):")

async def handle_message(update, context):
    user_id = update.effective_user.id
    if user_id not in users or not users[user_id].get("setup_step"):
        return
    
    step = users[user_id]["setup_step"]
    text = update.message.text

    if step == "weight":
        weight = float(text)
        users[user_id]["weight"] = weight
        users[user_id]["setup_step"] = "height"
        await update.message.reply_text("Введите ваш рост (в см):")
    elif step == "height":
        height = float(text)
        users[user_id]["height"] = height
        users[user_id]["setup_step"] = "age"
        await update.message.reply_text("Введите ваш возраст:")
    elif step == "age":
        age = int(text)
        users[user_id]["age"] = age
        users[user_id]["setup_step"] = "activity"
        await update.message.reply_text("Сколько минут активности у вас в день?")
    elif step == "activity":
        activity = int(text)
        users[user_id]["activity"] = activity
        users[user_id]["setup_step"] = "city"
        await update.message.reply_text("В каком городе вы находитесь?")
    elif step == "city":
        city = text.strip()
        users[user_id]["city"] = city
        users[user_id]["setup_step"] = None
        
        user = users[user_id]
        water_goal = user["weight"] * 30
        water_goal += (user["activity"] // 30) * 500
        
        temp = await get_temperature(city)
        if temp > 25:
            water_goal += 500
        
        calorie_goal = 10 * user["weight"] + 6.25 * user["height"] - 5 * user["age"]
        calorie_goal += user["activity"] * 7
        
        users[user_id]["water_goal"] = round(water_goal)
        users[user_id]["calorie_goal"] = round(calorie_goal)
        
        await update.message.reply_text(f"Профиль сохранен! Вода: {water_goal} мл, Калории: {calorie_goal} ккал")

async def get_temperature(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        data = response.json()
        return data["main"]["temp"]
    return 20.0

async def log_water(update, context):
    user_id = update.effective_user.id
    if user_id not in users or users[user_id]["weight"] is None:
        await update.message.reply_text("Сначала настройте профиль командой /set_profile")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /log_water <количество в мл>")
        return
    
    amount = float(context.args[0])
    users[user_id]["logged_water"] += amount
    remaining = users[user_id]["water_goal"] - users[user_id]["logged_water"]
    if remaining < 0:
        remaining = 0
    await update.message.reply_text(f"Добавлено {amount} мл воды. Осталось: {remaining} мл")

async def log_food(update, context):
    user_id = update.effective_user.id
    if user_id not in users or users[user_id]["weight"] is None:
        await update.message.reply_text("Сначала настройте профиль командой /set_profile")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /log_food <название продукта>")
        return
    
    product_name = " ".join(context.args)
    food_info = get_food_info(product_name)
    
    if not food_info:
        await update.message.reply_text("Введите калорийность вручную: <калории на 100г> <граммы>")
        users[user_id]["waiting_for_food"] = True
        return
    
    await update.message.reply_text(f"{food_info['name']} — {food_info['calories']} ккал на 100 г. Сколько грамм вы съели?")
    users[user_id]["waiting_for_food_grams"] = True
    users[user_id]["current_food"] = food_info

async def handle_food_grams(update, context, user_id):
    grams = float(update.message.text)
    food = users[user_id]["current_food"]
    calories = (food["calories"] * grams) / 100
    users[user_id]["logged_calories"] += calories
    await update.message.reply_text(f"Записано: {round(calories, 1)} ккал")
    users[user_id]["waiting_for_food_grams"] = False

async def handle_manual_food(update, context, user_id):
    parts = update.message.text.split()
    if len(parts) != 2:
        raise ValueError
    calories_per_100g = float(parts[0])
    grams = float(parts[1])
    calories = (calories_per_100g * grams) / 100
    users[user_id]["logged_calories"] += calories
    await update.message.reply_text(f"Записано: {round(calories, 1)} ккал")
    users[user_id]["waiting_for_food"] = False

def get_food_info(product_name):
    product_name = product_name.lower()
    if product_name in FOOD_DB:
        return {"name": product_name, "calories": FOOD_DB[product_name]}
    return None

async def log_workout(update, context):
    user_id = update.effective_user.id
    if user_id not in users or users[user_id]["weight"] is None:
        await update.message.reply_text("Сначала настройте профиль командой /set_profile")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /log_workout <тип> <время в минутах>")
        return
    
    workout_type = context.args[0].lower()

    minutes = int(context.args[1])
    calorie_burn_rates = {"бег": 10, "ходьба": 5, "велосипед": 8, "плавание": 7, "силовая": 6}
    rate = calorie_burn_rates.get(workout_type, 7)
    calories_burned = rate * minutes
    water_addition = (minutes // 30) * 200
    users[user_id]["burned_calories"] += calories_burned
    users[user_id]["water_goal"] += water_addition
    await update.message.reply_text(f"{workout_type} {minutes} минут — {calories_burned} ккал. Дополнительно: выпейте {water_addition} мл воды.")

async def check_progress(update, context):
    user_id = update.effective_user.id
    if user_id not in users or users[user_id]["weight"] is None:
        await update.message.reply_text("Сначала настройте профиль командой /set_profile")
        return
    
    user = users[user_id]
    
    water_remaining = user["water_goal"] - user["logged_water"]
    if water_remaining < 0:
        water_remaining = 0
        
    calorie_balance = user["logged_calories"] - user["burned_calories"]
    calorie_remaining = user["calorie_goal"] - calorie_balance
    if calorie_remaining < 0:
        calorie_remaining = 0
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    water_data = [user["logged_water"], water_remaining]
    water_labels = [f'Выпито\n{user["logged_water"]} мл', f'Осталось\n{water_remaining} мл']
    water_colors = ['#3498db', '#ecf0f1']
    ax1.pie(water_data, labels=water_labels, colors=water_colors, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 10})
    ax1.set_title('ВОДА', fontsize=14, fontweight='bold', color='#2c3e50', pad=20)
    ax1.axis('equal')
    
    if calorie_balance > user["calorie_goal"]:
        calorie_balance = user["calorie_goal"]
    calorie_data = [calorie_balance, calorie_remaining]
    calorie_labels = [f'Баланс\n{calorie_balance} ккал', f'Осталось\n{calorie_remaining} ккал']
    calorie_colors = ['#e74c3c', '#ecf0f1']
    ax2.pie(calorie_data, labels=calorie_labels, colors=calorie_colors, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 10})
    ax2.set_title('КАЛОРИИ', fontsize=14, fontweight='bold', color='#2c3e50', pad=20)
    ax2.axis('equal')
    
    fig.suptitle('ВАШ ПРОГРЕСС', fontsize=16, fontweight='bold', color='#2c3e50', y=0.95)

    info_text = f"Всего потреблено: {user['logged_calories']} ккал | Сожжено: {user['burned_calories']} ккал"
    plt.figtext(0.5, 0.02, info_text, ha='center', fontsize=10, color='#7f8c8d')
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#f8f9fa')
    buf.seek(0)
    plt.close()
    
    text_message = (
        "📊 Прогресс:\n\n"
        "Вода:\n"
        f"- Выпито: {user['logged_water']} мл из {user['water_goal']} мл\n"
        f"- Осталось: {water_remaining} мл\n\n"
        "Калории:\n"
        f"- Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал\n"
        f"- Сожжено: {user['burned_calories']} ккал\n"
        f"- Баланс: {calorie_balance} ккал"
    )

    await update.message.reply_photo(photo=buf, caption=text_message)

async def handle_all_messages(update, context):
    user_id = update.effective_user.id
    if user_id not in users:
        return
    
    if users[user_id].get("waiting_for_food_grams"):
        await handle_food_grams(update, context, user_id)
        return
    
    if users[user_id].get("waiting_for_food"):
        await handle_manual_food(update, context, user_id)
        return
    
    if users[user_id].get("setup_step"):
        await handle_message(update, context)

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_profile", set_profile))
    application.add_handler(CommandHandler("log_water", log_water))
    application.add_handler(CommandHandler("log_food", log_food))
    application.add_handler(CommandHandler("log_workout", log_workout))
    application.add_handler(CommandHandler("check_progress", check_progress))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
    
    application.run_polling()

if __name__ == "__main__":
    main()