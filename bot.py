import telebot
from telebot import types
import requests
import json
import sqlite3
from config import BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN)

def get_random_meal():
    """Получение случайного блюда через API с ингредиентами, фотографией и ссылкой на видео"""
    try:
        response = requests.get('https://www.themealdb.com/api/json/v1/1/random.php', timeout=2)
        response.raise_for_status()  # Проверка на ошибки HTTP
        data = response.json()
        
        if not data.get('meals') or not data['meals'][0]:
            return None
            
        meal = data['meals'][0]
        
        # Извлекаем ингредиенты (с перепроверкой на непустые строки)
        ingredients = []
        for i in range(1, 21):
            ingredient = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")
            if ingredient and ingredient.strip():
                ingr_text = f"{measure.strip()} {ingredient.strip()}" if measure and measure.strip() else ingredient.strip()
                ingredients.append(ingr_text)
        
        return {
            'name': meal.get('strMeal'),
            'youtube': meal.get('strYoutube') or "Ссылка на видео отсутствует",
            'thumb': meal.get('strMealThumb'),
            'ingredients': ingredients
        }
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Ошибка при получении блюда: {e}")
        return None

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('meals.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS favorite_meals
                 (user_id INTEGER, meal_name TEXT, youtube_link TEXT)''')
    conn.commit()
    conn.close()

def add_to_favorites(user_id, meal_name, youtube_link):
    """Добавление блюда в избранное"""
    conn = sqlite3.connect('meals.db')
    c = conn.cursor()
    c.execute('INSERT INTO favorite_meals (user_id, meal_name, youtube_link) VALUES (?, ?, ?)',
              (user_id, meal_name, youtube_link))
    conn.commit()
    conn.close()

def get_random_favorite(user_id):
    """Получение случайного блюда из избранного"""
    conn = sqlite3.connect('meals.db')
    c = conn.cursor()
    c.execute('SELECT meal_name, youtube_link FROM favorite_meals WHERE user_id = ? ORDER BY RANDOM() LIMIT 1',
              (user_id,))
    result = c.fetchone()
    conn.close()
    return result

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🎲 Случайное блюдо')
    btn2 = types.KeyboardButton('⭐ Случайное из избранного')
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, 
                     "Привет! Я бот, который поможет тебе найти рецепты блюд!\n"
                     "Выбери одну из опций:", 
                     reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == '🎲 Случайное блюдо':
        # Отправляем сообщение о загрузке
        loading_message = bot.send_message(message.chat.id, "🔄 Ищу случайное блюдо...")
        
        meal = get_random_meal()
        if meal is None:
            bot.edit_message_text("Извините, не удалось получить случайное блюдо. Попробуйте еще раз!", 
                                message.chat.id, 
                                loading_message.message_id)
            return
            
        # Формируем inline-клавиатуру:
        markup = types.InlineKeyboardMarkup()
        # Кнопка для добавления в избранное
        add_to_fav = types.InlineKeyboardButton('Добавить в избранное ⭐', 
                                               callback_data=f"add_{meal['name']}_{meal['youtube']}")
        markup.add(add_to_fav)
        
        # Формируем текстовый список ингредиентов с Markdown форматированием для копирования
        ingredients_text = "\n".join(f"`• {ingr}`" for ingr in meal['ingredients'])
        # Теперь ингредиенты отображаются в тексте, и их можно скопировать
        
        response = (f"🍳 Блюдо: {meal['name']}\n"
                    f"📺 Видео рецепт: {meal['youtube']}\n\n"
                    "Ингредиенты:\n" + ingredients_text)
                    
        # Удаляем сообщение о загрузке и отправляем фотографию с подписью и клавиатурой
        bot.delete_message(message.chat.id, loading_message.message_id)
        bot.send_photo(message.chat.id, meal['thumb'], caption=response, reply_markup=markup, parse_mode="Markdown")
        
    elif message.text == '⭐ Случайное из избранного':
        favorite = get_random_favorite(message.chat.id)
        if favorite:
            response = f"🍳 Блюдо: {favorite[0]}\n📺 Видео рецепт: {favorite[1]}"
            bot.send_message(message.chat.id, response)
        else:
            bot.send_message(message.chat.id, "У вас пока нет избранных блюд!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def callback_add_favorite(call):
    _, meal_name, youtube_link = call.data.split('_', 2)
    add_to_favorites(call.message.chat.id, meal_name, youtube_link)
    bot.answer_callback_query(call.id, "Блюдо добавлено в избранное! ⭐")

if __name__ == '__main__':
    init_db()
    bot.polling(none_stop=True) 