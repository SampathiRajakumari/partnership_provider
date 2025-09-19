from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import razorpay

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ---------- RAZORPAY SETUP ----------
RAZORPAY_KEY_ID = "rzp_test_xxxxxxxxx"        # from Razorpay Dashboard
RAZORPAY_KEY_SECRET = "xxxxxxxxxxxxxxxx"      # from Razorpay Dashboard

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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
            return redirect(url_for('search'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == "Rajakumari" and password == "#Rajakumari2004":
            session['username'] = username
            session['is_admin'] = True
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('show_all_businesses'))
        else:
            flash('Invalid admin credentials', 'error')
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ---------- PAYMENT FLOW ----------
@app.route('/start-business')
def start_business():
    if 'username' not in session:
        return redirect(url_for('login'))

    amount = 100  # registration fee
    return redirect(url_for('upi_pay', amount=amount))

@app.route('/upi-pay')
def upi_pay():
    if 'username' not in session:
        return redirect(url_for('login'))

    amount = request.args.get('amount', 50)  # default ₹50
    upi_link = (
        f"upi://pay?pa=7207121020@axl"
        f"&pn=Sampathi%20Rajakumari"
        f"&am={amount}"
        f"&tn=Business%20Registration"
        f"&cu=INR"
    )
    return render_template('pay.html', upi_link=upi_link, amount=amount)

@app.route('/payment_success', methods=["POST"])
def payment_success():
    session['paid'] = True
    flash("✅ Payment confirmed. You can now create your business.", "success")
    return redirect(url_for('create_business'))

@app.route('/create-business', methods=['GET', 'POST'])
def create_business():
    if 'username' not in session:
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

        session.pop('paid', None)  # clear payment flag
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

# ---------- CONTACT ----------
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    business = session.get('latest_business', None)
    if request.method == 'POST':
        return redirect(url_for('thank_you'))
    return render_template('contact.html', business=business)

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

# ---------- ADMIN & BUSINESS MANAGEMENT ----------
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

@app.route('/confirm-delete/<int:business_id>', methods=['GET', 'POST'])
def confirm_delete(business_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('is_admin'):
        return redirect(url_for('delete_business', business_id=business_id))

    if request.method == 'POST':
        entered_password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE username = ?', (session['username'],))
        row = c.fetchone()
        conn.close()

        if row and entered_password == row[0]:
            return redirect(url_for('delete_business', business_id=business_id))
        else:
            flash("Incorrect password.")
            return render_template('confirm_delete.html')

    return render_template('confirm_delete.html')

@app.route('/delete-business/<int:business_id>', methods=['GET','POST'])
def delete_business(business_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if session.get('is_admin'):
        c.execute('DELETE FROM businesses WHERE id = ?', (business_id,))
    else:
        c.execute('DELETE FROM businesses WHERE id = ? AND username = ?', (business_id, session['username']))

    conn.commit()
    conn.close()

    return redirect(url_for('show_all_businesses'))

@app.route('/my_businesses')
def my_businesses():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM businesses")
    businesses = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    is_admin = session.get('is_admin', False)
    return render_template('my_businesses.html', businesses=businesses, is_admin=is_admin)

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)  # <-- debug=True

