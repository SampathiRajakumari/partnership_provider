from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import qrcode

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ---------- INIT DATABASE ----------
def init_db():
    if not os.path.exists('database.db'):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT,
                password TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT,
                phone_number TEXT,
                business_type TEXT,
                business_name TEXT,
                requirements TEXT,
                position TEXT,
                details TEXT
            )
        ''')
        conn.commit()
        conn.close()

init_db()

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
        conn.commit()
        conn.close()
        flash("✅ Signup successful! Please login.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['username'] = username
            session['is_admin'] = False
            flash(f"Welcome {username}!", "success")
            return redirect(url_for('search'))
        else:
            flash("Invalid credentials.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('home'))

# ---------- PAYMENT FLOW ----------
@app.route('/start-business')
def start_business():
    if 'username' not in session:
        flash("Please login first.", "error")
        return redirect(url_for('login'))

    amount = 100  # registration fee
    return redirect(url_for('upi_pay', amount=amount))

@app.route('/upi-pay')
def upi_pay():
    if 'username' not in session:
        flash("Please login first.", "error")
        return redirect(url_for('login'))

    amount = request.args.get('amount', 50)  # default ₹50
    upi_id = "sampathirajakumari@oksbi"
    upi_name = "Sampathi Rajakumari"

    # Generate UPI link
    upi_link = f"upi://pay?pa={upi_id}&pn={upi_name.replace(' ', '%20')}&am={amount}&tn=Business%20Registration&cu=INR"

    # Generate QR code
    if not os.path.exists('static'):
        os.makedirs('static')
    qr_img_path = os.path.join('static', 'qrcode.jpg')
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img.save(qr_img_path)

    return render_template('pay.html', upi_link=upi_link, amount=amount)

@app.route('/payment_success', methods=["POST"])
def payment_success():
    session['paid'] = True
    flash("✅ Payment confirmed. You can now create your business.", "success")
    return redirect(url_for('create_business'))

# ---------- CREATE BUSINESS ----------
@app.route('/create-business', methods=['GET', 'POST'])
def create_business():
    if 'username' not in session:
        flash("Please login first.", "error")
        return redirect(url_for('login'))

    if 'paid' not in session:
        flash("⚠️ Please complete the payment before creating a business.", "error")
        return redirect(url_for('start_business'))

    if request.method == 'POST':
        data = (
            session['username'],
            request.form['email'],
            request.form['phone_number'],
            request.form['business_type'],
            request.form['business_name'],
            request.form['requirements'],
            request.form['position'],
            request.form['details']
        )
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO businesses (username, email, phone_number, business_type, business_name, requirements, position, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', data)
        conn.commit()
        conn.close()
        session.pop('paid', None)
        flash("Business created successfully!", "success")
        return redirect(url_for('thank_you'))

    return render_template('create_business.html')

# ---------- SEARCH ----------
@app.route('/search', methods=['GET', 'POST'])
def search():
    businesses = []
    not_found = False
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip().lower()
        business_type = request.form.get('business_type', '').strip().lower()

        query = 'SELECT * FROM businesses WHERE 1=1'
        params = []

        if business_name:
            query += ' AND LOWER(business_name) LIKE ?'
            params.append(f'%{business_name}%')
        if business_type:
            query += ' AND LOWER(business_type) LIKE ?'
            params.append(f'%{business_type}%')

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if rows:
            businesses = [dict(row) for row in rows]
            session['latest_business'] = businesses[0]
        else:
            not_found = True

    return render_template('search.html', businesses=businesses, not_found=not_found)

# ---------- THANK YOU ----------
@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

# ---------- RUN ----------
if __name__ == "__main__":
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(host="0.0.0.0", port=5000, debug=True)
