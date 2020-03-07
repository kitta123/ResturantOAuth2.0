import datetime
import json
import sqlite3

from flask_mail import Message

from User_login_db import init_db_command
from app import app, db, login_manager, mail
from flask import render_template, flash, redirect, session, g, request, url_for, jsonify
from flask_login import current_user, login_required, login_user,logout_user

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DISCOVERY_URL
from .forms import ReservationForm, ShowReservationsOnDateForm, AddTableForm
from .controller import create_reservation
from .models import Table, Reservation, User

from oauthlib.oauth2 import WebApplicationClient
import requests



RESTAURANT_OPEN_TIME=16
RESTAURANT_CLOSE_TIME=22

@login_manager.unauthorized_handler
def unauthorized():
    return "You must be logged in to access this content.", 403


# Naive database setup
try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)
print(client)

# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/")
def index():
    if current_user.is_authenticated:
        # return (
        #     "<p>Hello, {}! You're logged in! Email: {}</p>"
        #     "<div><p>Google Profile Picture:</p>"
        #     '<img src="{}" alt="Google profile pic"></img></div>'
        #     '<a class="button" href="/logout">Logout</a>'.format(
        #         current_user.name, current_user.email, current_user.profile_pic
        #     )
        # )
        return render_template('index.html')
    else:
        return render_template('login.html')


@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    # Create a user in our db with the information provided
    # by Google
    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )

    # Doesn't exist? Add to database
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)

    # Begin user session by logging the user in
    login_user(user)

    # Send user back to homepage
    return redirect(url_for("index"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()



@app.route('/book')
def book():
    return render_template('index.html', title="My Restaurant")


def send_email(email, name):
    # Sending the email
    date_obj = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d")
    try:
        msg = Message("Reservation made successfully!",
                      sender="noreply@demo.com",
                      recipients=[email])
        msg.body = f"""Hi {name},\nYou have made a reservation successfully in our restaurant on {date_obj}. \nFeel free to contact us for any inquiries. Thank you.\nRestaurant Staff"""
        mail.send(msg)
        return (jsonify({'status': 'Reservation added successfully'}))

    except Exception as e:
        return (jsonify({'status': 'Reservation added successfully but email not sent'}))


@app.route('/make_reservation', methods=['GET', 'POST'])
@login_required
def make_reservation():
    form = ReservationForm()
    if form.validate_on_submit():
        if form.reservation_datetime.data < datetime.datetime.now():
            flash("You cannot book dates in the past")
            return redirect('/make_reservation')
        reservation_date = datetime.datetime.combine(form.reservation_datetime.data.date(), datetime.datetime.min.time())
        if form.reservation_datetime.data < reservation_date + datetime.timedelta(hours=RESTAURANT_OPEN_TIME) or \
        form.reservation_datetime.data > reservation_date + datetime.timedelta(hours=RESTAURANT_CLOSE_TIME):
            flash("The restaurant is closed at that hour!")
            return redirect('/make_reservation')
        reservation = create_reservation(form)
        if reservation:
            flash("Reservation created!")
            send_email(current_user.email, current_user.name)
            return redirect('/book')
        else:
            flash("That time is taken!  Try another time")
            return redirect('/make_reservation')
    return render_template('make_reservation.html', title="Make Reservation", form=form)


@app.route('/show_tables', methods=['GET', 'POST'])
def show_tables():
    form = AddTableForm()

    if form.validate_on_submit():
        table = Table(capacity=int(form.table_capacity.data))
        db.session.add(table)
        db.session.commit()
        flash("Table created!")
        return redirect('/show_tables')

    tables = Table.query.all()
    return render_template('show_tables.html', title="Tables", tables=tables, form=form)

@app.route('/show_reservations', methods=['GET', 'POST'])
@app.route('/show_reservations/<reservation_date>', methods=['GET', 'POST'])
def show_reservations(reservation_date = datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d")):
    form = ShowReservationsOnDateForm()
    if form.validate_on_submit():
        res_date = datetime.datetime.strftime(form.reservation_date.data, "%Y-%m-%d")
        return redirect('/show_reservations/' + res_date)
    res_date = datetime.datetime.strptime(reservation_date, "%Y-%m-%d")
    reservations = Reservation.query.filter(Reservation.reservation_time >= res_date,
                                            Reservation.reservation_time < res_date + datetime.timedelta(days=1)).all()
    total_slots = len(Table.query.all()) * (RESTAURANT_CLOSE_TIME - RESTAURANT_OPEN_TIME)
    util = (len(reservations) / float(total_slots)) * 100
    return render_template('show_reservations.html', title="Reservations", reservations=reservations, form=form, total_slots=total_slots, utilization=util)

@app.route('/admin')
def admin():
    return render_template('admin.html', title="Admin")

@app.context_processor
def utility_processor():
    def table_utilization(table):
        start_datetime = datetime.datetime.combine(datetime.datetime.date(datetime.datetime.now()), datetime.datetime.min.time())
        end_datetime = start_datetime + datetime.timedelta(days=1)
        num_reservations = len(Reservation.query.filter(Reservation.table==table, Reservation.reservation_time > start_datetime, Reservation.reservation_time < end_datetime).all())
        return (num_reservations / float(RESTAURANT_CLOSE_TIME - RESTAURANT_OPEN_TIME)) * 100

    return dict(table_utilization=table_utilization)