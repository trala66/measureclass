import os
import time
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from psycopg2 import sql, OperationalError
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from urllib.parse import quote_plus

app = Flask(__name__)

# --- Database Konfiguration ---

# Load environment variables from .env file
load_dotenv()

# --- Secure Database Configuration ---
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
database = os.getenv('DB_NAME')
sslmode = os.getenv('DB_SSLMODE', 'require')

# Encode password in case it contains special characters
encoded_password = quote_plus(password)

# Build secure DB connection string
db_conn_str = f"postgres://{user}:{encoded_password}@{host}:{port}/{database}?sslmode={sslmode}"



# Retry konfiguration for DB-forbindelse
RETRY_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 3

def get_db_connection():
    """
    Opretter forbindelse til PostgreSQL databasen med retry-mekanisme.
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            conn = psycopg2.connect(db_conn_str)    # connect to database
            print(f"Databaseforbindelse oprettet på forsøg {attempt + 1}.")
            return conn
        except OperationalError as e:
            print(f"Forsøg {attempt + 1} mislykkedes: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                print(f"Forsøger igen om {RETRY_DELAY_SECONDS} sekunder...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print("Alle genoprettelsesforsøg mislykkedes. Afbryder.")
                raise # Re-raiser exception efter alle forsøg er brugt.

def get_average_measurements():
    """Henter og beregner gennemsnittet af alle indtastede målinger."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        measurements = {}
        cur.execute("SELECT dimension, AVG(value) FROM measurements GROUP BY dimension;")
        for row in cur.fetchall():
            measurements[row[0]] = Decimal(row[1]).quantize(Decimal('0.001')) # Afrund til 3 decimaler
        cur.close()
        return measurements
    except OperationalError as e:
        print(f"Fejl ved hentning af gennemsnitlige målinger: {e}")
        return {} # Returner en tom dictionary i tilfælde af DB-fejl
    except Exception as e:
        print(f"En uventet fejl opstod: {e}")
        return {}
    finally:
        if conn:
            conn.close()


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Formular til indtastning og beregning af resultater.
    """
    if request.method == 'POST':
        dimension = request.form['dimension']
        value_str = request.form['value'].replace(',', '.') # Erstat komma med punktum
        
        try:
            value = Decimal(value_str)
            if value <= 0:
                raise InvalidOperation("Værdi skal være positiv.")
        except InvalidOperation:
            # Hvis inputtet ikke er et gyldigt tal eller er negativt
            avg_measurements = get_average_measurements()
            length = avg_measurements.get('længde', Decimal('0.0'))
            width = avg_measurements.get('bredde', Decimal('0.0'))
            height = avg_measurements.get('højde', Decimal('0.0'))
            area = length * width
            volume = length * width * height
            return render_template('index.html',
                                   error_message="Ugyldig værdi. Indtast positivt tal.",
                                   length=length, width=width, height=height, area=area, volume=volume)

        conn = None
        try:
            conn = get_db_connection()
            if conn: # Tjek om forbindelsen blev oprettet
                cur = conn.cursor()
                cur.execute(
                    sql.SQL("INSERT INTO measurements (dimension, value) VALUES (%s, %s)"),
                    (dimension, value)
                )
                conn.commit()
                cur.close()
        except OperationalError as e:
            # Exception handling ved databaseindtastning
            if conn:
                conn.rollback()
            print(f"Fejl ved indsættelse i database: {e}")
            # Redirect med en fejlbesked til brugeren
            avg_measurements = get_average_measurements()
            length = avg_measurements.get('længde', Decimal('0.0'))
            width = avg_measurements.get('bredde', Decimal('0.0'))
            height = avg_measurements.get('højde', Decimal('0.0'))
            area = length * width
            volume = length * width * height
            return render_template('index.html',
                                   error_message="Kunne ikke oprette forbindelse til databasen. Prøv igen.",
                                   length=length, width=width, height=height, area=area, volume=volume)
        finally:
            if conn:
                conn.close()
        return redirect(url_for('index')) # Omdiriger/opdater for at vise opdaterede beregninger

    # Ved GET anmodning eller efter POST
    avg_measurements = get_average_measurements()
    length = avg_measurements.get('længde', Decimal('0.0'))
    width = avg_measurements.get('bredde', Decimal('0.0'))
    height = avg_measurements.get('højde', Decimal('0.0'))

    # Beregn areal og rumfang
    area = (length * width).quantize(Decimal('0.001'))
    volume = (length * width * height).quantize(Decimal('0.001'))

    return render_template('index.html',
                           length=length,
                           width=width,
                           height=height,
                           area=area,
                           volume=volume)

if __name__ == '__main__':
    #app.run(debug=True) # Sæt debug=False i produktion
    app.run(host='0.0.0.0', port=5000) # global access
