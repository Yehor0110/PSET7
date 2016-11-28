from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *


# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    id = session["user_id"] 
    cash = db.execute("SELECT cash FROM users WHERE id= :id", id = id)[0]['cash']
    home = db.execute("SELECT symbol, name, SUM(share) FROM purchases WHERE user_id = :id GROUP BY symbol HAVING SUM(share) > 0",
                        id = id)
    for entry in home:
        symbol = lookup(entry['symbol'])
        entry['price'] = symbol['price']
        entry['total'] = entry['price'] * entry['SUM(share)']
    
    total = 0
    for entry in home:
        total += entry['total']
    
    total += cash    
    
    return render_template("index.html", output = home, cash = cash, total = total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        if lookup(request.form.get("symbol")) == None:
            return apology("Wrong symbol")
        symbol=lookup(request.form.get("symbol"))
        
        if not request.form.get("shares"):
            return apology("must provide the number of shares")
        if request.form.get("shares").isalpha():
            return apology("You should write a number of shares")    
        if int(request.form.get("shares")) < 1:
            return apology("You shoul provide positive integers")
        
        id = session["user_id"] 
        sharePrice = int(request.form.get("shares")) * symbol.get('price')
        cash = db.execute("SELECT cash FROM users WHERE id= :id", id = id)[0]['cash']
        if cash < sharePrice:    
            return apology("You don't have enough money")
        
        purchases = cash - sharePrice 
        command = """INSERT INTO purchases (user_id, symbol, name, share, price)
                VALUES (:user_id, :symbol, :name, :share, :price)"""
                
        db.execute(command, user_id=id, symbol=symbol.get('symbol'), name = symbol.get('name'), 
                share = int(request.form.get("shares")), price = symbol.get('price')) 
        db.execute("UPDATE users SET cash = :cash WHERE id= :id", cash = purchases, id=id)
        return redirect(url_for("index"))
        
        
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    output = db.execute("SELECT * FROM purchases WHERE user_id = :id", id = session["user_id"])
    return render_template("history.html", output = output)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        
        if not request.form.get("quote"):
            return apology("provide symbol") 
        if lookup(request.form.get("quote")) == None:
            return apology("error")
        symbol=lookup(request.form.get("quote"))
        return render_template("quoted.html", smb = symbol)
    else:
        return render_template("quote.html")
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username")
        if not request.form.get("password"):
            return apology("must provide password")
        if not request.form.get("confirm"):
            return apology("must provide password twice")
        if request.form.get("password") != request.form.get("confirm"):
            return apology("Passwords don't match")
            
        if  db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username")):
            return apology("This user name is already taken.")
            
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"),
                    hash = pwd_context.encrypt(request.form.get("password")))
        return redirect(url_for("login"))
            
    else:
        return render_template("register.html")

    
    
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        if lookup(request.form.get("symbol")) == None:
            return apology("Wrong symbol")
        symbol=lookup(request.form.get("symbol"))
        
        if not request.form.get("shares"):
            return apology("must provide the number of shares")
        if request.form.get("shares").isalpha():
            return apology("You should write a number of shares")    
        if int(request.form.get("shares")) < 1:
            return apology("You shoul provide positive integers")
        
        id = session["user_id"]
        if not db.execute("SELECT symbol FROM purchases WHERE user_id = :id AND symbol = :symbol", 
                            id = id, symbol = symbol.get('symbol')):
            return apology("You don't have this share")
            
        amount = int(request.form.get("shares"))                   
        sharePrice = amount * symbol.get('price')
        cash = db.execute("SELECT cash FROM users WHERE id= :id", id = id)[0]['cash']
        
        shares = db.execute("SELECT SUM(share) FROM purchases WHERE user_id = :id AND symbol = :symbol", 
                            id = id, symbol = symbol.get('symbol'))[0]['SUM(share)']
        
        if shares < amount:
            return apology("error")
        

        
        balance = cash + sharePrice 
        command = """INSERT INTO purchases (user_id, symbol, name, share, price)
                VALUES (:user_id, :symbol, :name, :share, :price)"""
                
        db.execute(command, user_id=id, symbol=symbol.get('symbol'), name = symbol.get('name'), 
                share = -amount, price = symbol.get('price')) 
        db.execute("UPDATE users SET cash = :cash WHERE id= :id", cash = balance, id=id)
        
        return redirect(url_for("index"))
    else:
        return render_template("sell.html")
        
        
@app.route("/changePassword", methods=["GET", "POST"])
@login_required
def changePassword():
    if request.method == "POST":
        if not request.form.get("oldPassword"):
            return apology("must provide password")
        if not request.form.get("newPassword"):
            return apology("must provide password")
        if request.form.get("newPassword") != request.form.get("confirm"):
            return apology("Passwords don't match")
        rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"]) 
        if not pwd_context.verify(request.form.get("oldPassword"), rows[0]["hash"]):
            return apology("Wrong old password")
            
        db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash = pwd_context.encrypt(request.form.get("newPassword")),
                    id = session["user_id"])
                    
        return redirect(url_for("login"))            

    else:
        return render_template("changep.html")

    
  
