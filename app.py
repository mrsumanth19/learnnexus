
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, send_file
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import google.generativeai as genai
import os
from werkzeug.security import generate_password_hash, check_password_hash
import io
import base64,requests
from flask_mail import Mail, Message
from twilio.rest import Client


app = Flask(__name__)
app.secret_key = os.urandom(24).hex()  # Secret key for session management
app.permanent_session_lifetime = timedelta(days=7)  # Session lasts for 7 days

# Gemini AI Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "Your_google_api_key")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
chat = model.start_chat(history=[])

# Flask-Mail Configuration (Gmail App Password needed)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'info.learnnexus@gmail.com'
app.config['MAIL_PASSWORD'] = 'vdskhazcxtxbhdvb'  # use 16-char app password
mail = Mail(app)

# Twilio Configuration
TWILIO_ACCOUNT_SID = 'AC7b51bab5d2fdf6036a0c6991c6b77153'
TWILIO_AUTH_TOKEN = '8f7235641d8187d846ff21e53bf24662'
TWILIO_PHONE_NUMBER = '+16089038159'  # your Twilio phone number
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# MySQL Database Connection Function
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="sumanth",  # Your MySQL password
            database="learnnexus"
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

# Home route
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/roadmap')
def roadmap():
    return render_template('roadmap.html')

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/javascript')
def javascript():
    return render_template('javascript.html')

@app.route('/java')
def java():
    return render_template('java.html')

@app.route('/python')
def python():
    return render_template('python.html')

@app.route('/fullstack')
def fullstack():
    return render_template('fullstack.html')

@app.route('/campus_events')
def campus_events():
    return render_template('campus_events.html')

# Add these route handlers to your existing app.py file

@app.route('/advertise_events')
def advertise_events():
    return render_template('advertise_events.html')

@app.route('/event_detail')
def event_detail():
    # Create a sample event object for the template
    sample_event = {
        "title": "Sample Event",
        "organizer": "Demo Organizer",
        "description": "This is a sample event. Please select a real event from the events page.",
        "event_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "venue": "Sample Venue",
        "event_type": "cultural",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_urgent": False
    }
    return render_template('event_detail.html', event=sample_event)

@app.route('/add_event')
def add_event():
    if "user_id" not in session:
        flash("Please login to access this page", "error")
        return redirect(url_for("login"))
    return render_template('add_event.html')

@app.route('/api/events', methods=['GET'])
def get_events():
    try:
        # Get filter parameter from request
        event_filter = request.args.get('filter', 'all')
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Base query
            query = """SELECT id, title, description, event_date, venue, organizer, 
                      contact_info, event_type, 
                      CASE WHEN image_data IS NOT NULL 
                           THEN CONCAT('data:image/jpeg;base64,', TO_BASE64(image_data)) 
                           ELSE NULL 
                      END as image_data,
                      external_link, is_featured, is_urgent, created_at
                      FROM events"""
            
            # Apply filter if not 'all'
            if event_filter != 'all':
                query += " WHERE event_type = %s"
                cursor.execute(query, (event_filter,))
            else:
                cursor.execute(query)
                
            events = cursor.fetchall()
            cursor.close()
            connection.close()
            
            # Format dates for JSON
            for event in events:
                if "event_date" in event and event["event_date"]:
                    event["event_date"] = event["event_date"].strftime("%Y-%m-%d %H:%M:%S")
                if "created_at" in event and event["created_at"]:
                    event["created_at"] = event["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    
            return jsonify(events)
        else:
            return jsonify({"error": "Database connection error"}), 500
            
    except Exception as e:
        print(f"Get events error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/add-event', methods=['POST'])
def api_add_event():
    if "user_id" not in session:
        return jsonify({"error": "You must be logged in"}), 401
    
    try:
        # Get form data
        title = request.form.get('title')
        description = request.form.get('description')
        event_date = request.form.get('event_date')
        venue = request.form.get('venue')
        organizer = request.form.get('organizer')
        contact_info = request.form.get('contact_info')
        event_type = request.form.get('event_type')
        external_link = request.form.get('external_link')
        
        # Boolean values
        is_featured = True if request.form.get('is_featured') == 'on' else False
        is_urgent = True if request.form.get('is_urgent') == 'on' else False
        
        # Validate required fields
        if not title or not description or not event_date or not venue or not organizer or not event_type:
            return jsonify({"error": "All required fields must be filled out"}), 400
        
        # Process image if uploaded
        image_data = None
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            image_data = image.read()
        
        # Store in database
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            if image_data:
                cursor.execute(
                    """INSERT INTO events 
                    (title, description, event_date, venue, organizer, contact_info, 
                    event_type, image_data, external_link, is_featured, is_urgent, user_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (title, description, event_date, venue, organizer, contact_info, 
                    event_type, image_data, external_link, is_featured, is_urgent, session["user_id"])
                )
            else:
                cursor.execute(
                    """INSERT INTO events 
                    (title, description, event_date, venue, organizer, contact_info, 
                    event_type, external_link, is_featured, is_urgent, user_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (title, description, event_date, venue, organizer, contact_info, 
                    event_type, external_link, is_featured, is_urgent, session["user_id"])
                )
                
            connection.commit()
            event_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                "success": True,
                "message": "Event added successfully!",
                "event_id": event_id
            })
            
        else:
            return jsonify({"error": "Database connection error"}), 500
            
    except Exception as e:
        print(f"Add event error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/event/<int:event_id>')
def view_event(event_id):
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, title, description, event_date, venue, organizer, 
                   contact_info, event_type, 
                   CASE WHEN image_data IS NOT NULL 
                        THEN CONCAT('data:image/jpeg;base64,', TO_BASE64(image_data)) 
                        ELSE NULL 
                   END as image_data,
                   external_link, is_featured, is_urgent, created_at
                   FROM events WHERE id = %s""",
                (event_id,)
            )
            event = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if event:
                # Format dates
                if "event_date" in event and event["event_date"]:
                    event["event_date"] = event["event_date"].strftime("%Y-%m-%d %H:%M:%S")
                if "created_at" in event and event["created_at"]:
                    event["created_at"] = event["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    
                return render_template('event_detail.html', event=event)
            else:
                flash("Event not found", "error")
                return redirect(url_for("advertise_events"))
        else:
            flash("Database connection error", "error")
            return redirect(url_for("advertise_events"))
            
    except Exception as e:
        print(f"View event error: {e}")
        flash(f"Error loading event: {e}", "error")
        return redirect(url_for("advertise_events"))

@app.route('/api/delete-event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if "user_id" not in session:
        return jsonify({"error": "You must be logged in"}), 401
    
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # First check if the event belongs to the current user
            cursor.execute("SELECT user_id FROM events WHERE id = %s", (event_id,))
            event = cursor.fetchone()
            
            if not event or event[0] != session["user_id"]:
                cursor.close()
                connection.close()
                return jsonify({"error": "You don't have permission to delete this event"}), 403
            
            # Delete the event
            cursor.execute("DELETE FROM events WHERE id = %s AND user_id = %s", (event_id, session["user_id"]))
            connection.commit()
            cursor.close()
            connection.close()
            
            return jsonify({
                "success": True,
                "message": "Event deleted successfully"
            })
        else:
            return jsonify({"error": "Database connection error"}), 500
            
    except Exception as e:
        print(f"Delete event error: {e}")
        return jsonify({"error": str(e)}), 500



# File Upload Route
@app.route('/upload_file', methods=['POST'])
def upload_file():
    if "user_id" not in session:
        return jsonify({"error": "You must be logged in"}), 401
    
    # Get form data
    file = request.files.get('fileInput')
    cover_image = request.files.get('coverInput')
    file_name = request.form.get('fileName')
    hosted_by = request.form.get('hostedBy')
    description = request.form.get('fileDescription')
    
    # Validate inputs
    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file_name or not hosted_by:
        return jsonify({"error": "File name and host are required"}), 400
    
    try:
        # Read file data
        file_data = file.read()
        file_size = len(file_data)
        
        # Read cover image if provided
        cover_data = None
        if cover_image and cover_image.filename != '':
            cover_data = cover_image.read()
        
        # Store in database
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            if cover_data:
                cursor.execute(
                    """INSERT INTO files 
                    (filename, hosted_by, description, file_data, cover_image, user_id, file_size) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (file_name, hosted_by, description, file_data, cover_data, session["user_id"], file_size)
                )
            else:
                cursor.execute(
                    """INSERT INTO files 
                    (filename, hosted_by, description, file_data, user_id, file_size) 
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                    (file_name, hosted_by, description, file_data, session["user_id"], file_size)
                )
                
            connection.commit()
            file_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                "success": True,
                "message": "File uploaded successfully!",
                "file_id": file_id,
                "file_name": file_name,
                "hosted_by": hosted_by
            })
            
        else:
            return jsonify({"error": "Database connection error"}), 500
            
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({"error": str(e)}), 500

# Get Files Route
@app.route('/get_files', methods=['GET'])
def get_files():
    if "user_id" not in session:
        return jsonify({"error": "You must be logged in"}), 401
        
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT id, filename, hosted_by, description, 
                   CASE WHEN cover_image IS NOT NULL 
                        THEN CONCAT('data:image/jpeg;base64,', TO_BASE64(cover_image)) 
                        ELSE NULL 
                   END as cover_image,
                   upload_date, file_size
                   FROM files
                   ORDER BY upload_date DESC"""
            )
            files = cursor.fetchall()
            cursor.close()
            connection.close()
            
            # Format dates for JSON
            for file in files:
                if "upload_date" in file and file["upload_date"]:
                    file["upload_date"] = file["upload_date"].strftime("%Y-%m-%d %H:%M:%S")
                    
            return jsonify({"files": files})
        else:
            return jsonify({"error": "Database connection error"}), 500
            
    except Exception as e:
        print(f"Get files error: {e}")
        return jsonify({"error": str(e)}), 500

# Download File Route
@app.route('/download/<int:file_id>', methods=['GET'])
def download_file(file_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT filename, file_data FROM files WHERE id = %s", (file_id,))
            file = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if file:
                return send_file(
                    io.BytesIO(file["file_data"]),
                    download_name=file["filename"],
                    as_attachment=True
                )
            else:
                flash("File not found", "error")
                return redirect(url_for("index"))
        else:
            flash("Database connection error", "error")
            return redirect(url_for("index"))
            
    except Exception as e:
        print(f"Download error: {e}")
        flash(f"Error downloading file: {e}", "error")
        return redirect(url_for("index"))

# Upload page route
@app.route('/upload')
def upload():
    if "user_id" not in session:
        flash("Please login to access this page", "error")
        return redirect(url_for("login"))
    return render_template('upload.html')

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm-password")

        if not fullname or not email or not phone or not password or not confirm_password:
            flash("All fields are required", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered", "error")
                return redirect(url_for("register"))

            try:
                cursor.execute(
                    "INSERT INTO users (fullname, email, phone, password) VALUES (%s, %s, %s, %s)",
                    (fullname, email, phone, hashed_password)
                )
                connection.commit()

                # ✅ Send Email
                try:
                    msg = Message(
                        "Welcome to LearnNexus!",
                        sender=app.config["MAIL_USERNAME"],
                        recipients=[email]
                    )
                    msg.body = (
                        f"Hi {fullname},\n\n"
                        f"Thanks for registering at LearnNexus!\n"
                        f"Email: {email}\n"
                        f"Password: {password}\n\n"
                        f"(Keep this safe.)\n\n"
                        f"- LearnNexus Team"
                    )
                    mail.send(msg)
                    print("✅ Email sent successfully.")
                except Exception as e:
                    print(f"❌ Email Error: {e}")

                # ✅ Send SMS via Fast2SMS
                try:
                    sms_msg = f"Hi {fullname}, welcome to LearnNexus! Email: {email}, password: {password}"
                    headers = {
                        "authorization": "q6urLy7TiHct2zuahJ1aDf4RjcuFA7lUajsqThc1Ckkx3BQt4M3qPjEEIvxh",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "route": "q",
                        "message": sms_msg,
                        "language": "english",
                        "flash": 0,
                        "numbers": phone
                    }
                    response = requests.post("https://www.fast2sms.com/dev/bulkV2", json=payload, headers=headers)
                    print("📱 SMS API Response:", response.status_code, response.text)
                except Exception as e:
                    print(f"❌ Fast2SMS Error: {e}")

                flash("Registration successful! Please login.", "success")
                return redirect(url_for("login"))

            except Error as e:
                flash(f"Registration Error: {e}", "error")
                return redirect(url_for("register"))
            finally:
                cursor.close()
                connection.close()
        else:
            flash("Database connection failed", "error")
            return redirect(url_for("register"))

    return render_template("register.html")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Get form data
        email = request.form.get("email")
        password = request.form.get("password")
        remember = request.form.get("remember")
        
        if not email or not password:
            flash("Email and password are required", "error")
            return redirect(url_for("login"))
        
        # Connect to database and verify credentials
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if user and check_password_hash(user["password"], password):
                # Create session for logged in user
                session.permanent = True if remember else False
                session["user_id"] = user["id"]
                session["user_name"] = user["fullname"]
                session["user_email"] = user["email"]
                
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                flash("Invalid email or password", "error")
                return redirect(url_for("login"))
        else:
            flash("Database connection error", "error")
            return redirect(url_for("login"))
    
    # GET request - show login form
    return render_template("login.html")

# Logout route
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "success")
    return redirect(url_for("login"))

# Main app index page (protected)
@app.route('/index')
def index():
    if "user_id" not in session:
        flash("Please login to access this page", "error")
        return redirect(url_for("login"))
    return render_template('index.html')

# TextGPT route
@app.route('/textgpt')
def textgpt():
    if "user_id" not in session:
        flash("Please login to access this page", "error")
        return redirect(url_for("login"))
    return render_template('textgpt.html')

# Chat API Route
@app.route('/api/chat', methods=['POST'])
def chat_response():
    try:
        if "user_id" not in session:
            return jsonify({"error": "You must be logged in"}), 401
            
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Get response from Gemini AI
        response_raw = chat.send_message(user_message)
        bot_response = response_raw.text
        
        # Store conversation in database (optional)
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO conversations (user_id, user_message, bot_response) VALUES (%s, %s, %s)",
                (session["user_id"], user_message, bot_response)
            )
            connection.commit()
            cursor.close()
            connection.close()
        
        return jsonify({'response': bot_response})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 
    
    
    @app.route('/api/chat-history', methods=['GET'])
    def get_chat_history():
        if "user_id" not in session:
            return jsonify({"error": "You must be logged in"}), 401
        
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT user_message, bot_response, created_at 
                FROM conversations 
                WHERE user_id = %s 
                ORDER BY created_at ASC""",
                (session["user_id"],)
            )
            history = cursor.fetchall()
            cursor.close()
            connection.close()
            
            # Format dates for JSON
            for item in history:
                if "created_at" in item and item["created_at"]:
                    item["created_at"] = item["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    
            return jsonify(history)
        else:
            return jsonify({"error": "Database connection error"}), 500
            
    except Exception as e:
        print(f"Get chat history error: {e}")
        return jsonify({"error": str(e)}), 500
    
    
    @app.route('/api/clear-chat-history', methods=['POST'])
    def clear_chat_history():
        if "user_id" not in session:
            return jsonify({"error": "You must be logged in"}), 401
        
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM conversations WHERE user_id = %s", (session["user_id"],))
            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({"success": True, "message": "Chat history cleared successfully."})
        else:
            return jsonify({"error": "Database connection error"}), 500
    except Exception as e:
        print(f"Clear chat history error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
