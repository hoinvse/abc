from flask import Flask, render_template, request, flash, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
import cv2
import face_recognition
import sqlite3
from datetime import datetime
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

conn = sqlite3.connect('attendance_db.sqlite', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS faces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        encoding TEXT NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
''')
conn.commit()

known_faces = []
known_names = []

class AddFaceForm(FlaskForm):
    name = StringField('Tên người')
    submit = SubmitField('Thêm khuôn mặt')

def load_known_faces():
    cursor.execute('SELECT name, encoding FROM faces')
    rows = cursor.fetchall()
    for row in rows:
        name, encoding_str = row
        encoding = [float(x) for x in encoding_str.split(',')]
        known_names.append(name)
        known_faces.append(encoding)

load_known_faces()

def add_face(name, encoding):
    known_names.append(name)
    known_faces.append(encoding)

    encoding_str = ','.join(map(str, encoding))
    cursor.execute('INSERT INTO faces (name, encoding) VALUES (?, ?)', (name, encoding_str))
    conn.commit()

def delete_face(name):
    index_to_remove = known_names.index(name)
    del known_faces[index_to_remove]
    del known_names[index_to_remove]

    cursor.execute('DELETE FROM faces WHERE name = ?', (name,))
    cursor.execute('DELETE FROM attendance_log WHERE name = ?', (name,))
    conn.commit()

def check_attendance(encoding):
    matches = face_recognition.compare_faces(known_faces, encoding)
    name = "Unknown"

    if True in matches:
        first_match_index = matches.index(True)
        name = known_names[first_match_index]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('INSERT INTO attendance_log (name, timestamp) VALUES (?, ?)', (name, timestamp))
        conn.commit()

        flash(f"{name} đã điểm danh thành công.")

def display_attendance_table():
    cursor.execute('SELECT name, timestamp FROM attendance_log')
    logs = cursor.fetchall()
    return render_template('attendance_log.html', logs=logs)

@app.route('/', methods=['GET', 'POST'])
def index():
    form = AddFaceForm()

    if form.validate_on_submit():
        name = form.name.data

        global show_camera
        show_camera = False

        thoi_diem_bat_dau = time.time()
        cap = cv2.VideoCapture(0)
        while time.time() - thoi_diem_bat_dau < 5:
            ret, frame = cap.read()

            vi_tri_khuon_mat = face_recognition.face_locations(frame)
            if vi_tri_khuon_mat:
                encoding = face_recognition.face_encodings(frame, vi_tri_khuon_mat)[0]
                add_face(name, encoding)
                break

            cv2.imshow("Thêm Khuôn Mặt", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        show_camera = True

    return render_template('index.html', form=form)

@app.route('/delete_face/<name>')
def delete_face_route(name):
    delete_face(name)
    flash(f"Khuôn mặt của {name} đã được xóa.")
    return redirect(url_for('index'))

@app.route('/check_attendance')
def check_attendance_route():
    global show_camera
    show_camera = False

    thoi_diem_bat_dau = time.time()
    cap = cv2.VideoCapture(0)
    while time.time() - thoi_diem_bat_dau < 5:
        ret, frame = cap.read()

        vi_tri_khuon_mat = face_recognition.face_locations(frame)
        if vi_tri_khuon_mat:
            encoding = face_recognition.face_encodings(frame, vi_tri_khuon_mat)[0]
            check_attendance(encoding)
            break

        cv2.imshow("Kiểm Tra Điểm Danh", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    show_camera = True

    return redirect(url_for('index'))

@app.route('/attendance_log')
def attendance_log_route():
    return display_attendance_table()

if __name__ == '__main__':
    show_camera = True
    cap = cv2.VideoCapture(0)

    def camera_worker():
        global show_camera
        while show_camera:
            ret, frame = cap.read()
            cv2.imshow("Camera", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    camera_thread = threading.Thread(target=camera_worker)
    camera_thread.start()

    app.run(debug=True)

    show_camera = False
    camera_thread.join()

conn.close()
