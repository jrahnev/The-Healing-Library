from cs50 import SQL
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from tempfile import mkdtemp
from datetime import datetime,timedelta


from helpers import login_required

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

db = SQL("sqlite:///finalpr.db")

@app.route('/')
def index():
    hide = ""
    if session:
        hide = "yes"
    return render_template('index.html', hide = hide)

@app.route('/register', methods=["GET","POST"])
def register():
    if request.method == 'GET':
        if session:
            alert = 'Yes'
            return render_template('register.html', alert = alert)
        return render_template("register.html")
    if request.method == 'POST':
        if not request.form.get('username') or not request.form.get('password') or not request.form.get("confirmation"):
            title = 'MISSING USERNAME OR/AND PASSWORD'
            return render_template('register.html', title=title), 403
        elif request.form.get('password') != request.form.get('confirmation'):
            title = 'CONFIRMATION DOES NOT MATCH'
            return render_template('register.html', title = title), 403
        db.execute('INSERT INTO users (username, hash) VALUES (?,?)', request.form.get('username'), generate_password_hash((request.form.get('password')), method='pbkdf2:sha256', salt_length=8))
        return render_template("login.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    if request.method == "GET":
        if session:
            alert = "Yes"
            return render_template("login.html", alert = alert)
        session.clear()
        return render_template("login.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            title = "MUST PROVIDE USERNAME"
            return render_template('login.html', title=title), 403

        # Ensure password was submitted
        elif not request.form.get("password"):
            title = "MUST PROVIDE PASSWORD"
            return render_template('login.html', title=title), 403

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            title = "INVALID USERNAME AND/OR PASSWORD"
            return render_template('login.html', title=title), 403

        session["user_id"] = rows[0]["id"]
        db.execute("UPDATE users SET points = 0 WHERE id = ?", session['user_id'])
        return redirect('/registered')

@app.route('/registered', methods=['GET','POST'])
@login_required
def registered():
    if request.method == 'GET':
        return render_template('registered.html')
    if request.method == 'POST':
        return redirect("/quizz")

@app.route('/quizz', methods=['GET','POST'])
@login_required
def quizz():
        db.execute("UPDATE users SET points = 0 WHERE id = ?", session['user_id'])
        number = db.execute("SELECT id FROM number")[0]['id']
        if request.method == "GET":
            question = db.execute('SELECT question FROM questions WHERE id = ?', number)[0]['question']
            answer_1 = db.execute('SELECT answer FROM answers WHERE id = ?', number)[0]['answer']
            answer_2 = db.execute('SELECT answer FROM answers WHERE id = ?', number)[1]['answer']
            answer_3 = db.execute('SELECT answer FROM answers WHERE id = ?', number)[2]['answer']
            return render_template('quizz.html', question=question, answer_1=answer_1, answer_2=answer_2,
            answer_3=answer_3)
        if request.method == "POST":
            answer = request.form.get('question')
            if number < 2:
                result = db.execute("SELECT value FROM answers WHERE answer = ?", answer)[0]['value']
                db.execute("UPDATE record SET result = result + ?", result)
                db.execute("UPDATE number SET id = id + 1")
                return redirect("/quizz")
            else:
                result = db.execute("SELECT value FROM answers WHERE answer = ?", answer)[0]['value']
                db.execute("UPDATE record SET result = result + ?", result)
                db.execute("UPDATE number SET id = 1")
                final = db.execute("SELECT * FROM record")[0]['result']
                db.execute("UPDATE record SET result = 0")
                db.execute("UPDATE users SET points = ? WHERE id = ?", final, session['user_id'])
        return redirect('/account')

@app.route('/account', methods=["POST", "GET"])
@login_required
def account():
    emptylist = None;
    points = db.execute("SELECT points FROM users WHERE id = ?", session['user_id'])[0]['points']
    id_user = session["user_id"]
    if request.method == "GET":
        if points == 0:
            emptylist = 0
        books = db.execute("SELECT Title, Author, status, return, id_user, id FROM archive WHERE points = ?", points)
        return render_template('account.html', books = books, emptylist = emptylist, id_user = id_user)
    if request.method == "POST":
        if request.form.get("quizz"):
            return redirect("/quizz")
        if request.form.get("review"):
            return redirect("/review")
        period = datetime.now() + timedelta(minutes=2)
        date = period.strftime("%d-%m-%y")
        borrow = request.form.getlist('books')
        archive = db.execute("SELECT id FROM archive WHERE status = 'NOT AVAILABLE'")
        if not borrow:
            return redirect("/account")

        for i in borrow:
                if i in archive:
                        break
                else:
                    db.execute("UPDATE archive SET datetime = strftime('%s','now','+2 minute'), status = 'NOT AVAILABLE', id_user = ?, return = ? WHERE id = ?",
                    session['user_id'], date, i)

    return redirect('/mybooks')

@app.route('/mybooks', methods=["GET","POST"])
@login_required
def mybooks():
    db.execute("UPDATE archive SET return = 'EXPIRED' WHERE id_user = ? AND datetime < strftime('%s','now')", session['user_id'])
    mybooks = db.execute("SELECT * FROM archive WHERE id_user = ?", session['user_id'])
    name = db.execute("SELECT username FROM users WHERE id = ?", session['user_id'])[0]['username']
    return render_template('mybooks.html', mybooks = mybooks, name = name)

@app.route('/returning', methods=['POST'])
@login_required
def returning():
    title = request.form.get('id')
    db.execute("UPDATE archive SET datetime = NULL, status = NULL, id_user = NULL, return = NULL WHERE id = ?", title)
    return redirect('/mybooks')

@app.route("/feedback", methods=['POST'])
@login_required
def feedback():
    if request.method == "POST":
        now = datetime.now()
        date = now.strftime("%d-%m-%y")
        book_id = request.form.get("name")
        if book_id:
            book = db.execute("SELECT * FROM archive WHERE id = ?", book_id)
            return render_template("feedback.html", book = book)
        review = request.form.get("text")
        username = request.form.get("username")
        book_id = request.form.get("book_id")
        db.execute("INSERT INTO review (feedback, username, book_id, date) VALUES(?,?,?,?)", review, username, book_id, date)
        return redirect("/mybooks")


@app.route("/review", methods=["GET"])
@login_required
def review():
    if request.method=="GET":
        book_id = request.args.get("review")
        reviews = db.execute("SELECT * FROM review WHERE book_id =?", book_id)
        return render_template("review.html", reviews = reviews)

@app.route("/search", methods=["GET"])
@login_required
def search():
    if request.method == "GET":
        new_page = True;
        if not request.args.get("q"):
            q = False
            return render_template("account.html", new_page = new_page, q = q)
        id_user = session["user_id"]
        search = request.args.get("q")
        books = db.execute("SELECT Title, Author, status, return, id_user, id FROM archive WHERE Title LIKE ?", "%" + search + "%")

        return render_template('account.html', books = books, id_user = id_user, new_page = new_page)

@app.route("/logout")
def logout():
    if session:
        db.execute("UPDATE users SET points = 0 WHERE id = ?", session['user_id'])
        session.clear()
        return render_template("index.html")
    else:
        return render_template("index.html")

