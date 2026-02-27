from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import uuid
import hashlib
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Предустановленные тестовые пользователи
users = {
    'Гурман': {
        'password': hashlib.sha256('gurman123'.encode()).hexdigest(),
        'online': False,
        'sid': None,
        'avatar': '🍔',
        'status': 'Ем бургер'
    },
    'Бургероман': {
        'password': hashlib.sha256('burger456'.encode()).hexdigest(),
        'online': False,
        'sid': None,
        'avatar': '🍟',
        'status': 'Жду картошку'
    },
    'Сырный': {
        'password': hashlib.sha256('cheese789'.encode()).hexdigest(),
        'online': False,
        'sid': None,
        'avatar': '🧀',
        'status': 'Люблю сыр'
    },
    'Макс': {
        'password': hashlib.sha256('max123'.encode()).hexdigest(),
        'online': False,
        'sid': None,
        'avatar': '🥤',
        'status': 'Пью колу'
    }
}

messages = []  # [{username: str, message: str, time: str, room: str}]

# Комнаты с участниками
rooms = {
    'general': {
        'name': '🍔 Общий чат',
        'description': 'Главная комната для всех гурманов',
        'users': {},  # {username: {'joined_at': time, 'role': 'member'}}
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'icon': '🍔'
    },
    'foodies': {
        'name': '🍟 Фудики',
        'description': 'Обсуждаем еду и рецепты',
        'users': {},
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'icon': '🍟'
    },
    'gaming': {
        'name': '🎮 Игровая',
        'description': 'Для любителей поиграть',
        'users': {},
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'icon': '🎮'
    },
    'music': {
        'name': '🎵 Музыкальная',
        'description': 'Делимся любимой музыкой',
        'users': {},
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'icon': '🎵'
    }
}

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    """Регистрация нового пользователя"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Имя и пароль обязательны'})
    
    if username in users:
        return jsonify({'success': False, 'error': 'Пользователь уже существует'})
    
    users[username] = {
        'password': hash_password(password),
        'online': False,
        'sid': None,
        'avatar': '👤',
        'status': 'Новый участник'
    }
    return jsonify({'success': True, 'message': 'Регистрация успешна! Теперь вы можете войти.'})

@app.route('/login', methods=['POST'])
def login():
    """Вход пользователя"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    print(f"Попытка входа: {username}")
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Имя и пароль обязательны'})
    
    if username not in users:
        return jsonify({'success': False, 'error': f'Пользователь {username} не найден'})
    
    if users[username]['password'] != hash_password(password):
        return jsonify({'success': False, 'error': 'Неверный пароль'})
    
    session['username'] = username
    print(f"Успешный вход: {username}")
    
    return jsonify({
        'success': True, 
        'username': username,
        'avatar': users[username].get('avatar', '👤'),
        'status': users[username].get('status', '')
    })

@app.route('/logout')
def logout():
    """Выход пользователя"""
    username = session.get('username')
    if username and username in users:
        users[username]['online'] = False
        users[username]['sid'] = None
        
        # Удаляем пользователя из всех комнат
        for room_name, room_data in rooms.items():
            if username in room_data['users']:
                del room_data['users'][username]
    
    session.pop('username', None)
    return jsonify({'success': True})

@app.route('/check_session')
def check_session():
    """Проверка активной сессии"""
    username = session.get('username')
    if username and username in users:
        return jsonify({
            'logged_in': True,
            'username': username,
            'avatar': users[username].get('avatar', '👤'),
            'status': users[username].get('status', '')
        })
    return jsonify({'logged_in': False})

@app.route('/get_rooms')
def get_rooms():
    """Получение списка комнат"""
    rooms_list = []
    for room_name, room_data in rooms.items():
        rooms_list.append({
            'name': room_name,
            'display_name': room_data['name'],
            'description': room_data['description'],
            'icon': room_data['icon'],
            'members_count': len(room_data['users']),
            'online_members': sum(1 for u in room_data['users'] if users.get(u, {}).get('online', False))
        })
    return jsonify({'rooms': rooms_list})

@app.route('/get_room_members/<room_name>')
def get_room_members(room_name):
    """Получение участников комнаты"""
    if room_name not in rooms:
        return jsonify({'success': False, 'error': 'Комната не найдена'})
    
    members = []
    for username in rooms[room_name]['users']:
        if username in users:
            members.append({
                'username': username,
                'avatar': users[username].get('avatar', '👤'),
                'online': users[username].get('online', False),
                'status': users[username].get('status', ''),
                'joined_at': rooms[room_name]['users'][username].get('joined_at', ''),
                'role': rooms[room_name]['users'][username].get('role', 'member')
            })
    
    # Сортируем: сначала онлайн, потом по алфавиту
    members.sort(key=lambda x: (not x['online'], x['username']))
    
    return jsonify({
        'success': True,
        'room': room_name,
        'members': members,
        'total_count': len(members),
        'online_count': sum(1 for m in members if m['online'])
    })

@socketio.on('connect')
def handle_connect():
    """Обработка подключения клиента"""
    username = session.get('username')
    print(f"Пользователь {username} подключился")
    
    if username and username in users:
        users[username]['online'] = True
        users[username]['sid'] = request.sid
        
        # Автоматически добавляем в общую комнату
        join_room('general')
        if username not in rooms['general']['users']:
            rooms['general']['users'][username] = {
                'joined_at': datetime.now().strftime('%H:%M'),
                'role': 'member'
            }
        
        # Отправляем статус всем
        emit('user_status', {
            'username': username, 
            'online': True,
            'avatar': users[username].get('avatar', '👤'),
            'status': users[username].get('status', '')
        }, broadcast=True)
        
        # Обновляем списки участников во всех комнатах
        for room_name in rooms:
            update_room_members(room_name)
        
        # Отправляем приветственное сообщение
        welcome_msg = {
            'id': str(uuid.uuid4()),
            'username': '🍔 Биг Мак',
            'message': f'👋 Добро пожаловать, {username}! Приятного общения!',
            'time': datetime.now().strftime('%H:%M'),
            'room': 'general',
            'system': True
        }
        emit('new_message', welcome_msg, room='general')

@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения клиента"""
    username = session.get('username')
    print(f"Пользователь {username} отключился")
    
    if username and username in users:
        users[username]['online'] = False
        users[username]['sid'] = None
        
        # Удаляем пользователя из всех комнат
        for room_name, room_data in rooms.items():
            if username in room_data['users']:
                del room_data['users'][username]
                # Уведомляем о выходе
                system_msg = {
                    'id': str(uuid.uuid4()),
                    'username': '🍔 Биг Мак',
                    'message': f'👋 {username} покинул чат',
                    'time': datetime.now().strftime('%H:%M'),
                    'room': room_name,
                    'system': True
                }
                emit('new_message', system_msg, room=room_name)
        
        # Отправляем статус всем
        emit('user_status', {'username': username, 'online': False}, broadcast=True)
        
        # Обновляем списки участников во всех комнатах
        for room_name in rooms:
            update_room_members(room_name)

def update_room_members(room_name):
    """Обновление списка участников комнаты"""
    if room_name not in rooms:
        return
    
    members = []
    for username in rooms[room_name]['users']:
        if username in users:
            members.append({
                'username': username,
                'avatar': users[username].get('avatar', '👤'),
                'online': users[username].get('online', False),
                'status': users[username].get('status', ''),
                'role': rooms[room_name]['users'][username].get('role', 'member')
            })
    
    members.sort(key=lambda x: (not x['online'], x['username']))
    
    emit('room_members_update', {
        'room': room_name,
        'members': members,
        'total_count': len(members),
        'online_count': sum(1 for m in members if m['online'])
    }, room=room_name)

@socketio.on('send_message')
def handle_message(data):
    """Обработка отправки сообщения"""
    username = session.get('username')
    if not username:
        return
    
    message_data = {
        'id': str(uuid.uuid4()),
        'username': username,
        'message': data['message'],
        'time': datetime.now().strftime('%H:%M'),
        'room': data.get('room', 'general'),
        'avatar': users[username].get('avatar', '👤')
    }
    
    messages.append(message_data)
    print(f"Сообщение от {username}: {data['message']}")
    emit('new_message', message_data, room=message_data['room'])

@socketio.on('join_room')
def handle_join_room(data):
    """Присоединение к комнате"""
    username = session.get('username')
    room = data['room']
    
    if not username or room not in rooms:
        return
    
    # Покидаем предыдущую комнату (кроме general)
    current_rooms = [r for r in rooms if r != 'general' and username in rooms[r]['users']]
    for old_room in current_rooms:
        leave_room(old_room)
        if username in rooms[old_room]['users']:
            del rooms[old_room]['users'][username]
            update_room_members(old_room)
    
    # Присоединяемся к новой комнате
    join_room(room)
    if username not in rooms[room]['users']:
        rooms[room]['users'][username] = {
            'joined_at': datetime.now().strftime('%H:%M'),
            'role': 'member'
        }
    
    print(f"{username} присоединился к комнате {room}")
    
    # Отправляем историю сообщений
    room_messages = [m for m in messages if m['room'] == room][-50:]
    emit('room_history', {'room': room, 'messages': room_messages})
    
    # Уведомляем о новом участнике
    system_msg = {
        'id': str(uuid.uuid4()),
        'username': '🍔 Биг Мак',
        'message': f'🔔 {username} присоединился к чату',
        'time': datetime.now().strftime('%H:%M'),
        'room': room,
        'system': True
    }
    emit('new_message', system_msg, room=room)
    
    # Обновляем список участников
    update_room_members(room)

@socketio.on('update_status')
def handle_update_status(data):
    """Обновление статуса пользователя"""
    username = session.get('username')
    if not username or username not in users:
        return
    
    users[username]['status'] = data.get('status', '')
    
    # Обновляем во всех комнатах
    for room_name in rooms:
        if username in rooms[room_name]['users']:
            update_room_members(room_name)

@socketio.on('typing')
def handle_typing(data):
    """Индикатор печатания"""
    username = session.get('username')
    if not username:
        return
    
    emit('user_typing', {
        'username': username, 
        'typing': data['typing']
    }, room=data['room'], include_self=False)

if __name__ == '__main__':
    print("🚀 ЗАПУСК БИГ МАК МЕССЕНДЖЕРА")
    print("=" * 60)
    print("📱 Тестовые пользователи:")
    print("   1. Имя: Гурман     | Пароль: gurman123 | Статус: Ем бургер")
    print("   2. Имя: Бургероман | Пароль: burger456 | Статус: Жду картошку")
    print("   3. Имя: Сырный     | Пароль: cheese789 | Статус: Люблю сыр")
    print("   4. Имя: Макс       | Пароль: max123    | Статус: Пью колу")
    print("=" * 60)
    print("🏠 Комнаты:")
    for room_name, room_data in rooms.items():
        print(f"   {room_data['icon']} {room_data['name']} - {room_data['description']}")
    print("=" * 60)
    print("🌐 Откройте браузер: http://localhost:5000")
    print("💡 Для остановки нажмите Ctrl+C")
    print("=" * 60)
    
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)