from flask import Flask, render_template, request
from flask_mysqldb import MySQL
import yaml
import hashlib
from json import dumps

app = Flask(__name__)
mysql = MySQL(app)
db = yaml.load(open('db.yaml'))

app.config['MYSQL_USER'] = db['mysql_user']
app.config['MYSQL_PASSWORD'] = db['mysql_password']
app.config['MYSQL_HOST'] = db['mysql_host']
app.config['MYSQL_DB'] = db['mysql_db']
# Default is tuples
# app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

global current_user # See who is logged in
current_user = 'none'


@app.route('/', methods=['GET', 'POST'])
def index():
    global current_user
    if request.method == 'POST':
        user_details = request.form
        try:
            # If not logged in case
            username = user_details['username']
            password = user_details['password']

            # Password hashing to 224 characters
            password_hashed = hashlib.sha224(password.encode()).hexdigest()
        except:
            if request.form['logout'] == '':
                # If logged in case (for signout form return)
                current_user = 'none'
            return render_template('/index.html', user=current_user)
        cur = mysql.connection.cursor()
        cur.execute('''select username, user_password from user_profile''')
        mysql.connection.commit()
        all_users = cur.fetchall()
        for user in all_users:
            # Check if the entered username and password is correct
            if user[0] == username and user[1] == password_hashed:
                current_user = username
                return portfolio()
        return "<h1>Username did not match!</h1>"
    else:
        return render_template('index.html', user=current_user)


@app.route('/portfolio.html')
def portfolio():

    # Check if we have logged in users
    if current_user == 'none':
        return '<h2>Please login first!</h2> <br><a href="/">Go Back</a>'

    # Query for holdings
    cur = mysql.connection.cursor()
    user = [current_user]
    query_holdings = '''select A.symbol, A.quantity, B.LTP, round(A.quantity*B.LTP, 2) as current_value from holdings_view A
inner join company_price B
on A.symbol = B.symbol
where username = %s
'''
    # Query for watchlist
    cur.execute(query_holdings, user)
    holdings = cur.fetchall()

    query_watchlist = '''select symbol, LTP, PC, round(CH, 2), round(CH_percent, 2) from watchlist
natural join company_price
where username = %s
order by(symbol);
'''
    cur.execute(query_watchlist, user)
    watchlist = cur.fetchall()

    # Query for stock suggestion
    query_suggestions = '''select symbol, EPS, ROE, book_value, rsi, adx, pe_ratio, macd from company_price
natural join fundamental_averaged
natural join technical_signals
natural join company_profile 
where 
EPS>25 and roe>13 and 
book_value > 100 and
50<rsi<70 and adx >23 and
pe_ratio < 35 and
macd = 'bull'
order by symbol;
'''
    cur.execute(query_suggestions)
    suggestions = cur.fetchall()

    # Query on EPS
    query_eps = '''select symbol, ltp, eps from fundamental_averaged
where eps > 30;'''
    cur.execute(query_eps)
    eps = cur.fetchall()

    # Query on PE Ratio
    query_pe = '''select symbol, ltp, pe_ratio from fundamental_averaged
where pe_ratio <30;'''
    cur.execute(query_pe)
    pe = cur.fetchall()

    # Query on technical signals
    query_technical = '''select * from technical_signals
where ADX > 23 and rsi>50 and rsi<70 and MACD = 'bull';'''
    cur.execute(query_technical)
    technical = cur.fetchall()

    # Query for pie chart
    query_sectors = '''select C.sector, sum(A.quantity*B.LTP) as current_value 
from holdings_view A
inner join company_price B
on A.symbol = B.symbol
inner join company_profile C
on A.symbol = C.symbol
where username = %s
group by C.sector;
'''
    cur.execute(query_sectors, user)
    sectors_total = cur.fetchall()
    # Convert list to json type having percentage and label keys
    piechart_dict = toPercentage(sectors_total)
    piechart_dict[0]['type'] = 'pie'
    piechart_dict[0]['hole'] = 0.4

    return render_template('portfolio.html', holdings=holdings, user=user[0], suggestions = suggestions, eps = eps, pe = pe, technical = technical, watchlist=watchlist, piechart = piechart_dict)

def toPercentage(sectors_total):
    json_format = {}
    total = 0

    for row in sectors_total:
        total += row[1]

    json_format['values'] = [round((row[1]/total)*100, 2) for row in sectors_total]
    json_format['labels'] = [row[0] for row in sectors_total]
    return [json_format]
    
def list_to_json(listToConvert):
    json_format = {}
    temp_dict = {}
    val_per = []
    for value in listToConvert:
        temp_dict[value] = listToConvert.count(value)
        
    values = [val for val in temp_dict.values()]
    for i in range(len(values)):
        per = ((values[i]/sum(values))*100)
        val_per.append(round(per, 2))
    keys = [k for k in temp_dict.keys()]
    json_format['values'] = val_per
    json_format['labels'] = keys
    return [json_format]

@app.route('/add_transaction.html', methods=['GET', 'POST'])
def add_transaction():

    # Query for all companies (for drop down menu)
    cur = mysql.connection.cursor()
    query_companies = '''select symbol from company_profile'''
    cur.execute(query_companies)
    companies = cur.fetchall()

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

    return render_template('add_transaction.html', companies=companies)


@app.route('/add_watchlist.html', methods=['GET', 'POST'])
def add_watchlist():
    
    # Query for companies (for drop down menu) excluding those which are already in watchlist
    cur = mysql.connection.cursor()
    query_companies = '''SELECT symbol from company_profile
where symbol not in
(select symbol from watchlist
where username = %s);
'''
    user = [current_user]
    cur.execute(query_companies, user)
    companies = cur.fetchall()

    if request.method == 'POST':
        watchlist_details = request.form
        symbol = watchlist_details['symbol']
        cur = mysql.connection.cursor()
        query = '''insert into watchlist(username, symbol) values
(%s, %s)'''
        values = [current_user, symbol]
        cur.execute(query, values)
        mysql.connection.commit()

    return render_template('add_watchlist.html', companies=companies)



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


@app.route('/watchlist.html')
def watchlist():
    if current_user == 'none':
            return '<h2>Please login first!</h2> <br><a href="/">Go Back</a>'
    cur = mysql.connection.cursor()
    user = current_user
    query_watchlist = '''select symbol, LTP, PC, round(CH, 2), round(CH_percent, 2) from watchlist
natural join company_price
where username = %s
order by(symbol);
'''
    cur.execute(query_watchlist, [user])
    watchlist = cur.fetchall()

    return render_template('watchlist.html', user=user, watchlist=watchlist)


@app.route('/holdings.html')
def holdings():
    if current_user == 'none':
        return '<h2>Please login first!</h2> <br><a href="/">Go Back</a>'
    cur = mysql.connection.cursor()
    user = current_user
    query_holdings = '''select A.symbol, A.quantity, B.LTP, round(A.quantity*B.LTP, 2) as current_value from holdings_view A
inner join company_price B
on A.symbol = B.symbol
where username = %s
'''
    cur.execute(query_holdings, [user])
    holdings = cur.fetchall()

    return render_template('holdings.html', user=user, holdings=holdings)

@app.route('/news.html')
def news(company='all'):
    cur = mysql.connection.cursor()
    if company == 'all':
        query = '''select date_of_news, title, related_company, C.sector, group_concat(sources) as sources 
from news N
inner join company_profile C
on N.related_company = C.symbol
group by(title);
'''
        cur.execute(query)
    else:
        company = [company]
        query = '''select date_of_news, title, related_company, related_sector, sources from news where related_company = %s'''
        cur.execute(query, company)
    rv = cur.fetchall()
    return render_template('news.html', values=rv)

if __name__ == '__main__':
    app.run(debug=True)
