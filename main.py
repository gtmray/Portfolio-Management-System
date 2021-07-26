from flask import Flask, render_template, request
from flask_mysqldb import MySQL
import yaml
import hashlib

app = Flask(__name__)
mysql = MySQL(app)
db = yaml.load(open('db.yaml'))

app.config['MYSQL_USER'] = db['mysql_user']
app.config['MYSQL_PASSWORD'] = db['mysql_password']
app.config['MYSQL_HOST'] = db['mysql_host']
app.config['MYSQL_DB'] = db['mysql_db']
# Default is tuples
# app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
global current_user
current_user = 'none'


@app.route('/', methods=['GET', 'POST'])
def index():
    global current_user
    if request.method == 'POST':
        user_details = request.form
        try:
            username = user_details['username']
            password = user_details['password']
            password_hashed = hashlib.sha224(password.encode()).hexdigest()
        except:
            current_user = 'none'
            return render_template('/index.html', user=current_user)
        cur = mysql.connection.cursor()
        cur.execute('''select username, user_password from user_profile''')
        mysql.connection.commit()
        all_users = cur.fetchall()
        for user in all_users:
            if user[0] == username and user[1] == password_hashed:
                current_user = username
                return portfolio()
        return "<h1>Username did not match!</h1>"
    else:
        return render_template('index.html', user=current_user)


@app.route('/portfolio.html')
def portfolio():
    if current_user == 'none':
        return '<h2>Please login first!</h2> <br><a href="/">Go Back</a>'
    cur = mysql.connection.cursor()
    user = [current_user]
    query = '''select A.symbol, A.quantity, B.LTP, round(A.quantity*B.LTP, 2) as current_value from holdings_view A
inner join company_price B
on A.symbol = B.symbol
where username = %s
'''
    cur.execute(query, user)
    holdings = cur.fetchall()

    return render_template('portfolio.html', holdings=holdings, user=user[0])


@app.route('/add_transaction.html', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'POST':
        transaction_details = request.form
        symbol = transaction_details['symbol']
        date = transaction_details['transaction_date']
        transaction_type = transaction_details['transaction_type']
        quantity = float(transaction_details['quantity'])
        rate = float(transaction_details['rate'])
        if transaction_type == 'Sell':
            quantity = -quantity

        cur = mysql.connection.cursor()
        query = '''insert into transaction_history(username, symbol, transaction_date, quantity, rate) values
(%s, %s, %s, %s, %s)'''
        values = [current_user, symbol, date, quantity, rate]
        cur.execute(query, values)
        mysql.connection.commit()

    return render_template('add_transaction.html')


@app.route('/stockprice.html')
def current_price(company='all'):
    cur = mysql.connection.cursor()
    if company == 'all':
        query = '''SELECT symbol, LTP, PC, round(CH, 2), round(CH_percent, 2) FROM company_price
        order by(symbol);
'''
        cur.execute(query)
    else:
        company = [company]
        query = '''SELECT symbol, LTP, PC, round(CH, 2), round(CH_percent, 2) FROM company_price where company = %s'''
        cur.execute(query, company)
    rv = cur.fetchall()
    return render_template('stockprice.html', values=rv)


@app.route('/fundamental.html', methods=['GET'])
def fundamental_report(company='all'):
    cur = mysql.connection.cursor()
    if company == 'all':
        query = '''SELECT Symbol, LTP, round(avg(EPS), 2), round(avg(ROE), 2), round(avg(book_value), 2), round(avg(pe_ratio), 2) FROM fundamental_report group by(Symbol)'''
        cur.execute(query)
    else:
        company = [company]
        query = '''SELECT * FROM fundamental_report where company = %s'''
        cur.execute(query, company)
    rv = cur.fetchall()
    return render_template('fundamental.html', values=rv)


@app.route('/technical.html')
def technical_analysis(company='all'):
    cur = mysql.connection.cursor()
    if company == 'all':
        query = '''select A.symbol, sector, LTP, volume, RSI, ADX, MACD from technical_signals A 
left join company_profile B
on A.symbol = B.symbol
order by (A.symbol)'''
        cur.execute(query)
    else:
        company = [company]
        query = '''SELECT * FROM technical_signals where company = %s'''
        cur.execute(query, company)
    rv = cur.fetchall()
    return render_template('technical.html', values=rv)


@app.route('/companyprofile.html')
def company_profile(company='all'):
    cur = mysql.connection.cursor()
    if company == 'all':
        query = '''select * from company_profile
order by(symbol);
'''
        cur.execute(query)
    else:
        company = [company]
        query = '''select * from company_profile where company = %s'''
        cur.execute(query, company)
    rv = cur.fetchall()
    return render_template('companyprofile.html', values=rv)


@app.route('/dividend.html')
def dividend_history(company='all'):
    cur = mysql.connection.cursor()
    if company == 'all':
        query = '''select * from dividend_history
order by(symbol);
'''
        cur.execute(query)
    else:
        company = [company]
        query = '''select * from dividend_history where company = %s'''
        cur.execute(query, company)
    rv = cur.fetchall()
    return render_template('dividend.html', values=rv)


if __name__ == '__main__':
    app.run(debug=True)
