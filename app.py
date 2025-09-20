from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import razorpay

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ---------- RAZORPAY SETUP ----------
RAZORPAY_KEY_ID = "rzp_test_xxxxxxxxx"        # Replace with your key
RAZORPAY_KEY_SECRET = "xxxxxxxxxxxxxxxx"      # Replace with your secret
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ---------- INIT DATABASE ----------
def init_db():
    if not os.path.exists('database.db'):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        email TEXT,
                        password TEXT
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS businesses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        email TEXT,
                        phone_number TEXT,
                        business_type TEXT,
                        business_name TEXT,
                        requirements TEXT,
                        position TEXT,
                        details TEXT
                    )''')
        conn.commit()
        conn.close()

init_db()

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template('home.html')

# ------------------- Signup/Login -------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', 
                  (username, email, password))
        conn.commit()
        conn.close()
        flash("Signup successful. Please login.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['username'] = username
            session['is_admin'] = False
            return redirect(url_for('search'))
        else:
            flash("Invalid credentials.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ------------------- Admin -------------------
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == "Rajakumari" and password == "#Rajakumari2004":
            session['username'] = username
            session['is_admin'] = True
            flash('Welcome Admin!', 'success')
            return redirect(url_for('show_all_businesses'))
        else:
            flash('Invalid admin credentials', 'error')
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('home'))

# ------------------- Payment -------------------
@app.route('/start-business')
def start_business():
    if 'username' not in session:
        return redirect(url_for('login'))

    amount = 100  # Registration fee in INR
    return redirect(url_for('upi_pay', amount=amount))

@app.route('/pay')
def upi_pay():
    if 'username' not in session:
        return redirect(url_for('login'))

    amount = int(request.args.get('amount', 50))
    # Create Razorpay order
    order = razorpay_client.order.create(dict(amount=amount*100, currency='INR', payment_capture='1'))
    return render_template('pay.html', amount=amount, order_id=order['id'], key_id=RAZORPAY_KEY_ID)

@app.route('/payment_success', methods=['POST'])
def payment_success():
    data = request.get_json()
    if data.get('razorpay_payment_id'):
        session['paid'] = True
        flash("✅ Payment confirmed. You can now create your business.", "success")
    return jsonify({'status': 'ok'})

# ------------------- Create Business -------------------
@app.route('/create-business', methods=['GET', 'POST'])
def create_business():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'paid' not in session:
        flash("⚠️ Please complete the payment before creating a business.", "error")
        return redirect(url_for('start-business'))

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
        c.execute('''INSERT INTO businesses (username, email, phone_number, business_type, business_name, requirements, position, details)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', data)
        conn.commit()
        conn.close()
        session.pop('paid', None)
        return redirect(url_for('thank_you'))

    return render_template('create_business.html')

# ------------------- Search -------------------
@app.route('/search', methods=['GET', 'POST'])
def search():
    businesses = []
    not_found = False
    if request.method == 'POST':
        name = request.form.get('business_name', '').strip().lower()
        btype = request.form.get('business_type', '').strip().lower()
        query = 'SELECT * FROM businesses WHERE 1=1'
        params = []
        if name:
            query += ' AND LOWER(business_name) LIKE ?'
            params.append(f'%{name}%')
        if btype:
            query += ' AND LOWER(business_type) LIKE ?'
            params.append(f'%{btype}%')
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

# ------------------- Contact / Thank You -------------------
@app.route('/contact', methods=['GET','POST'])
def contact():
    business = session.get('latest_business')
    if request.method == 'POST':
        return redirect(url_for('thank_you'))
    return render_template('contact.html', business=business)

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

# ------------------- Admin / Delete -------------------
@app.route('/all-businesses')
def show_all_businesses():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM businesses')
    rows = c.fetchall()
    conn.close()
    businesses = [dict(row) for row in rows]
    return render_template('my_businesses.html', businesses=businesses, is_admin=session.get('is_admin', False))

@app.route('/delete-business/<int:business_id>')
def delete_business(business_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if session.get('is_admin'):
        c.execute('DELETE FROM businesses WHERE id=?', (business_id,))
    else:
        c.execute('DELETE FROM businesses WHERE id=? AND username=?', (business_id, session['username']))
    conn.commit()
    conn.close()
    return redirect(url_for('show_all_businesses'))

# ------------------- Run App -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
