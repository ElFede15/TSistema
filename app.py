import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pandas as pd

# Inicialización de la aplicación Flask
app = Flask(__name__)
app.secret_key = 'secret_key_here'  # Cambiar por una clave secreta real

# Ruta para conectarse a la base de datos SQLite
def get_db():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row  # Esto nos permite acceder a las filas por nombre de columna
    return conn

# Verificar si el usuario está logueado
def is_logged_in():
    return 'user_id' in session

# Función para crear el esquema de la base de datos la primera vez que se ejecuta
def init_db():
    if not os.path.exists('app.db'):
        conn = get_db()
        cursor = conn.cursor()
        
        # Crear las tablas si no existen
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE ingresosygastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingreso_gasto TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                cantidad_unidades INT NOT NULL,
                precio NUMERIC(12,2) NOT NULL,
                total NUMERIC(12,2) NOT NULL,
                dia DATE NOT NULL,
                usuario TEXT NOT NULL
            )
        ''')

        # Crear el usuario admin la primera vez
        cursor.execute('''
            SELECT * FROM users WHERE username = "admin"
        ''')
        if cursor.fetchone() is None:
            # Si el usuario admin no existe, lo creamos con una contraseña segura
            hashed_password = generate_password_hash('admin123')  # Contraseña por defecto
            cursor.execute('''
                INSERT INTO users (username, password) VALUES (?, ?)
            ''', ('admin', hashed_password))
            conn.commit()

        conn.close()

# Ruta para el login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        # Buscar el usuario en la base de datos
        cursor.execute('''
            SELECT * FROM users WHERE username = ?
        ''', (username,))
        user = cursor.fetchone()

        if user:  # Si el usuario existe
            # Verificar la contraseña
            if check_password_hash(user['password'], password):
                session['user_id'] = user['id']  # Guardamos el ID del usuario en la sesión
                flash('Login exitoso!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
        else:
            flash('Usuario o contraseña incorrectos', 'danger')

        conn.close()

    return render_template('login.html')

# Ruta para logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Has cerrado sesión', 'success')
    return redirect(url_for('login'))

# Ruta principal que muestra los datos
@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # Obtener el usuario logueado por su ID
    cursor.execute('''SELECT username FROM users WHERE id = ?''', (session['user_id'],))
    user = cursor.fetchone()

    # Obtener todos los datos de la tabla "ingresosygastos"
    cursor.execute('''
        SELECT * FROM ingresosygastos
    ''')
    data = cursor.fetchall()

    conn.close()

    return render_template('index.html', ingasto=data, username=user['username'])

# Ruta para agregar ingresos y gastos
@app.route('/add', methods=['POST'])
def add_inga():
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # Obtener el usuario logueado por su ID
    cursor.execute('''SELECT username FROM users WHERE id = ?''', (session['user_id'],))
    user = cursor.fetchone()

    ingreso_gasto = request.form['ingreso_gasto']
    descripcion = request.form['descripcion']
    descripcion2 = request.form['descripcion2']
    cantidad_unidades = request.form['cantidad_unidades']
    precio = request.form['precio']

    if descripcion == 'Personalizado':
        descripcion = descripcion2

    total = round(int(cantidad_unidades) * float(precio.replace(',', '.')), 2)

    # Insertar el nuevo ingreso o gasto en la base de datos
    cursor.execute(''' 
        INSERT INTO ingresosygastos (ingreso_gasto, descripcion, cantidad_unidades, precio, total, dia, usuario) 
        VALUES (?, ?, ?, ?, ?, (Select STRFTIME('%d/%m/%Y, %H:%M', 'now', 'localtime')), ?) 
    ''', (ingreso_gasto, descripcion, cantidad_unidades, precio, total, user['username']))

    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    # Retornar los datos del nuevo ingreso/gasto como JSON
    return jsonify({
        'id': new_id,
        'ingreso_gasto': ingreso_gasto,
        'descripcion': descripcion,
        'cantidad_unidades': cantidad_unidades,
        'precio': precio,
        'total': total,
        'dia': pd.Timestamp.now().strftime('%d/%m/%Y, %H:%M'),
        'usuario': user['username']
    })

# Ruta para editar un ingreso o gasto
@app.route('/edit/<int:inga_id>', methods=['GET', 'POST'])
def edit_inga(inga_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # Obtener el ingreso o gasto a editar
    cursor.execute('''
        SELECT * FROM ingresosygastos WHERE id = ?
    ''', (inga_id,))
    inga = cursor.fetchone()

    # Obtener el usuario logueado por su ID
    cursor.execute('''SELECT username FROM users WHERE id = ?''', (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        ingreso_gasto = request.form['ingreso_gasto']
        descripcion = request.form['descripcion']
        descripcion2 = request.form['descripcion2']
        cantidad_unidades = request.form['cantidad_unidades']
        precio = request.form['precio']

        if descripcion == 'Personalizado':
            descripcion = descripcion2

        #precio = precio.replace('.', ',')  # Reemplazar punto por coma
        total = round(int(cantidad_unidades) * float(precio.replace(',', '.')),2) # Convierte nuevamente a float con punto para el cálculo
        #total = str(total).replace('.', ',')

        # Actualizar el ingreso o gasto a en la base de datos
        cursor.execute('''
            UPDATE ingresosygastos SET ingreso_gasto = ?, descripcion = ?, cantidad_unidades = ?, precio = ?, total = ?, dia = (Select STRFTIME('%d/%m/%Y, %H:%M', 'now', 'localtime')), usuario = ?  WHERE id = ?
        ''', (ingreso_gasto, descripcion,cantidad_unidades,precio,total,user['username'],inga_id))
        conn.commit()

        conn.close()

        flash('Ingreso o gasto actualizado correctamente!', 'success')
        return redirect(url_for('index'))

    conn.close()

    return render_template('edit.html', inga=inga,username=user['username'])

# Ruta para eliminar un ingreso o gasto
@app.route('/delete/<int:inga_id>', methods=['GET', 'POST'])
def delete_inga(inga_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # Eliminar el ingreso o gasto de la base de datos
    cursor.execute('''
        DELETE FROM ingresosygastos WHERE id = ?
    ''', (inga_id,))
    conn.commit()

    conn.close()

    flash('ingreso o gasto eliminado correctamente!', 'success')
    return redirect(url_for('index'))

# Ruta para exportar datos a Excel
@app.route('/export', methods=['GET'])
def export():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # Obtener todos los usuarios, excepto el ID
    cursor.execute("SELECT ingreso_gasto, descripcion, SUM(cantidad_unidades) AS cantidad_de_unidades, FLOOR(CAST(SUM(total) AS REAL) / SUM(cantidad_unidades) * 100) / 100 AS precio_promedio, SUM(total) AS total FROM ingresosygastos GROUP BY ingreso_gasto, descripcion ORDER BY ingreso_gasto, descripcion")
    rows = cursor.fetchall()

    # Crear un DataFrame
    df = pd.DataFrame(rows, columns=['Ingreso/gasto', 'Descripcion','Cantidad de unidades', 'Precio Promedio','Total'])

    # Guardar el archivo Excel
    df.to_excel('output.xlsx', index=False)

    return send_file('output.xlsx', as_attachment=True)


if __name__ == '__main__':
    # Crear la base de datos y el primer usuario admin si es necesario
    init_db()
    app.run(debug=True)
